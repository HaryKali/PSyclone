# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2022, Science and Technology Facilities Council
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
# -----------------------------------------------------------------------------
# Author R. W. Ford, STFC Daresbury Lab

'''Module containing tests for the KernelMetadataSymbol
kernel-layer-specific symbol. The tests include
translation of PSyIR to PSyclone Kernel PSyIR and PSyclone
Kernel PSyIR to processed PSyIR.

'''
import pytest

from fparser.common.readfortran import FortranStringReader
from fparser.two import Fortran2003
from fparser.two.utils import walk

from psyclone.domain.gocean.kernel import KernelMetadataSymbol
from psyclone.errors import InternalError
from psyclone.parse.utils import ParseError
from psyclone.psyir.symbols import INTEGER_TYPE

METADATA = (
    "  type, extends(kernel_type) :: compute_cu\n"
    "     type(go_arg), dimension(4) :: meta_args =                 &\n"
    "          (/ go_arg(GO_WRITE, GO_CU, GO_POINTWISE),            &\n"
    "             go_arg(GO_READ,  GO_CT, GO_STENCIL(000,011,000)), &\n"
    "             go_arg(GO_READ,  GO_GRID_AREA_T),                 &\n"
    "             go_arg(GO_READ,  GO_R_SCALAR, GO_POINTWISE)       &\n"
    "           /)\n"
    "     integer :: ITERATES_OVER = GO_ALL_PTS\n"
    "     integer :: index_offset = GO_OFFSET_SW\n"
    "  contains\n"
    "    procedure, nopass :: code => compute_cu_code\n"
    "  end type compute_cu\n")

PROGRAM = (
    f"program dummy\n"
    f"  use random ! avoid any missing declaration errors\n"
    f"{METADATA}"
    f"end program dummy\n")


# Class KernelMetadataSymbol

def test_kernelmetadatasymbol_init(fortran_reader):
    '''Test we can create a KernelMetadataSymbol'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    kernel_metadata_symbol = KernelMetadataSymbol("name", datatype)
    assert isinstance(kernel_metadata_symbol, KernelMetadataSymbol)
    assert kernel_metadata_symbol.name == "name"
    # Try one of the metadata values to make sure setup() is called
    # correctly from the constructor.
    assert kernel_metadata_symbol.iterates_over == "GO_ALL_PTS"


def test_kernelmetadatasymbol_setup_unknownfortrantype():
    '''Test that setup raises an exception if the datatype is not an
    UnknownFortranType.

    '''
    with pytest.raises(InternalError) as info:
        _ = KernelMetadataSymbol("name", INTEGER_TYPE)
    assert ("Expected kernel metadata to be stored in the PSyIR as an "
            "UnknownFortranType, but found ScalarType." in str(info.value))


def test_kernelmetadatasymbol_setup_derivedtype(fortran_reader):
    '''Test that setup raises an exception if the datatype is not a
    derived type.

    '''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    datatype.declaration = "integer :: compute_cu"
    with pytest.raises(InternalError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert ("Expected kernel metadata to be a derived type, but found "
            "'integer :: compute_cu'." in str(info.value))


def test_kernelmetadatasymbol_setup_iteratesover(fortran_reader):
    '''Test that the setup method raises an exception if iterates_over
    does not exist or has an invalid value. Also test that it works as
    expected if the value is valid.

    '''
    # Does not exist
    modified_program = PROGRAM.replace("ITERATES_OVER", "ignored")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert ("'iterates_over' was not found in TYPE, EXTENDS(kernel_type) "
            ":: compute_cu" in str(info.value))
    # invalid value
    modified_program = PROGRAM.replace("GO_ALL_PTS", "invalid")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    with pytest.raises(ValueError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert ("Expected one of ['go_all_pts', 'go_internal_pts', "
            "'go_external_pts'] for 'iterates_over' metadata, but found "
            "'invalid'." in str(info.value))
    # OK
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    metadata = KernelMetadataSymbol("name", datatype)
    assert metadata.iterates_over == "GO_ALL_PTS"


def test_kernelmetadatasymbol_setup_indexoffset(fortran_reader):
    '''Test that the setup method raises an exception if index_offset
    does not exist or has an invalid value. Also test that it works as
    expected if the value is valid.

    '''
    # Does not exist
    modified_program = PROGRAM.replace("index_offset", "ignored")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert ("'index_offset' was not found in TYPE, EXTENDS(kernel_type) "
            ":: compute_cu" in str(info.value))
    # invalid value
    modified_program = PROGRAM.replace("GO_OFFSET_SW", "invalid")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    with pytest.raises(ValueError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert ("Expected one of ['go_offset_se', 'go_offset_sw', 'go_offset_ne', "
            "'go_offset_nw', 'go_offset_any'] for 'index_offset' metadata, "
            "but found 'invalid'." in str(info.value))
    # OK
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    metadata = KernelMetadataSymbol("name", datatype)
    assert metadata.index_offset == "GO_OFFSET_SW"


def test_kernelmetadatasymbol_setup_code(fortran_reader):
    '''Test that the setup method raises an exception if the required type
    bound procedure does not exist or has an invalid value. Also test
    that it works as expected if the value is valid. Also test that it
    works when the procedure name is specified with and without 'code
    =>'.

    '''
    # no contains
    modified_program = PROGRAM.replace(
        "  contains\n    procedure, nopass :: code => compute_cu_code\n", "")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert ("No type-bound procedure 'contains' section was found in 'TYPE, "
            "EXTENDS(kernel_type) :: compute_cu" in str(info.value))

    # no type-bound procedure
    modified_program = PROGRAM.replace(
        "    procedure, nopass :: code => compute_cu_code\n", "")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert ("Expecting a single type-bound procedure, but found 'TYPE, "
            "EXTENDS(kernel_type) :: compute_cu" in str(info.value))

    # not specific binding
    modified_program = PROGRAM.replace(
        "    procedure, nopass :: code => compute_cu_code\n",
        "    generic :: code => compute_cu_code\n")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert ("Expecting a specific binding for the type-bound procedure, but "
            "found 'GENERIC :: code => compute_cu_code' in 'TYPE, "
            "EXTENDS(kernel_type) :: compute_cu" in str(info.value))

    # binding name not 'code'
    modified_program = PROGRAM.replace(
        "    procedure, nopass :: code => compute_cu_code\n",
        "    procedure, nopass :: ignore => compute_cu_code\n")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert ("Expecting the type-bound procedure binding-name to be 'code' "
            "if there is a procedure name, but found 'ignore' in 'TYPE, "
            "EXTENDS(kernel_type) :: compute_cu" in str(info.value))

    # OK
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    metadata = KernelMetadataSymbol("name", datatype)
    assert metadata.code == "compute_cu_code"

    # OK, no procedure name
    modified_program = PROGRAM.replace(
        "    procedure, nopass :: code => compute_cu_code\n",
        "    procedure, nopass :: code\n")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    metadata = KernelMetadataSymbol("name", datatype)
    assert metadata.code == "code"


# metaargs does not exist, len different to nargs, wrong num args,
# type go_arg, each entry go_arg.
def test_kernelmetadatasymbol_setup_metaargs(fortran_reader):
    '''Test that the setup method raises an exception if the required
    meta_args information does not exist or contains inconsistent
    information. Also test that it works as expected if the values are
    valid.

    '''
    # does not exist
    modified_program = PROGRAM.replace(
        "meta_args", "ignore")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert("'meta_args' was not found in TYPE, EXTENDS(kernel_type) :: "
           "compute_cu" in str(info.value))

    # not an array
    modified_program = PROGRAM.replace(
        "meta_args", "ignore")
    modified_program = modified_program.replace(
        "  contains", "    integer :: meta_args = hello\n  contains")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert("meta_args should be a list, but found 'hello' in 'TYPE, "
           "EXTENDS(kernel_type) :: compute_cu" in str(info.value))

    # nargs is 3 but not field or scalar
    modified_program = PROGRAM.replace(
        "GO_R_SCALAR", "INVALID")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    print(str(info.value))
    assert("Expected a 'meta_arg' entry with 3 arguments to either be a field "
           "or a scalar, but found 'invalid' as the second argument instead "
           "of '['go_cu', 'go_cv', 'go_ct', 'go_cf', 'go_every']' (fields) or "
           "'['go_i_scalar', 'go_r_scalar']' (scalars)."
           in str(info.value))

    # nargs not 2 or 3
    modified_program = PROGRAM.replace(
        ",  GO_GRID_AREA_T", "")
    kernel_psyir = fortran_reader.psyir_from_source(modified_program)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert("'meta_args' should have either 2 or 3 arguments, but found 1 in "
           "go_arg(GO_READ)." in str(info.value))

    # OK
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    metadata = KernelMetadataSymbol("name", datatype)
    assert len(metadata.args) == 4
    assert isinstance(metadata.args[0], KernelMetadataSymbol.FieldArg)
    assert isinstance(metadata.args[1], KernelMetadataSymbol.FieldArg)
    assert isinstance(metadata.args[2], KernelMetadataSymbol.GridArg)
    assert isinstance(metadata.args[3], KernelMetadataSymbol.ScalarArg)


def test_kernelmetadatasymbol_writefortranstring(fortran_reader):
    '''Test that the write_fortran_string method writes out the expected
    Fortran type information.

    '''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    symbol = kernel_psyir.children[0].symbol_table.lookup("compute_cu")
    datatype = symbol.datatype
    kernel_metadata_symbol = KernelMetadataSymbol("name", datatype)
    result = kernel_metadata_symbol.write_fortran_string()
    assert result == (
        "TYPE, EXTENDS(kernel_type) :: name\n"
        "TYPE(go_arg), DIMENSION(4) :: meta_args = ("
        "/go_arg(GO_WRITE, GO_CU, GO_POINTWISE), "
        "go_arg(GO_READ, GO_CT, GO_STENCIL(000, 011, 000)), "
        "go_arg(GO_READ, GO_GRID_AREA_T), "
        "go_arg(GO_READ, GO_R_SCALAR, GO_POINTWISE)/)\n"
        "  INTEGER :: ITERATES_OVER = GO_ALL_PTS\n"
        "  INTEGER :: index_offset = GO_OFFSET_SW\n"
        "  CONTAINS\n"
        "  PROCEDURE, NOPASS :: code => compute_cu_code\n"
        "END TYPE name\n")


def test_kernelmetadatasymbol_getproperty(fortran_reader):
    '''Test utility function that takes metadata in an fparser2 tree and
    returns the value associated with the supplied property name.

    '''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0].symbol_table.lookup(
        "compute_cu").datatype
    symbol = KernelMetadataSymbol("name", datatype)
    reader = FortranStringReader(datatype.declaration)
    spec_part = Fortran2003.Derived_Type_Def(reader)
    assert symbol._get_property(spec_part, "code").string == "compute_cu_code"
    assert symbol._get_property(spec_part, "iterates_over").string == \
        "GO_ALL_PTS"
    with pytest.raises(ParseError) as info:
        symbol._get_property(spec_part, "not_found")
    assert ("'not_found' was not found in TYPE, EXTENDS(kernel_type) :: "
            "compute_cu" in str(info.value))


def test_kernelmetadatasymbol_iteratesover(fortran_reader):
    '''Test that get, set and validate work for iterates_over metadata.'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    assert kernel_metadata.iterates_over == "GO_ALL_PTS"
    with pytest.raises(ValueError) as info:
        kernel_metadata.iterates_over = "hello"
    assert ("Expected one of ['go_all_pts', 'go_internal_pts', "
            "'go_external_pts'] for 'iterates_over' metadata, but found "
            "'hello'." in str(info.value))
    assert "GO_INTERNAL_PTS" not in kernel_metadata.datatype.declaration
    assert "GO_ALL_PTS" in kernel_metadata.datatype.declaration
    kernel_metadata.iterates_over = "GO_INTERNAL_PTS"
    assert kernel_metadata.iterates_over == "GO_INTERNAL_PTS"
    assert "GO_INTERNAL_PTS" in kernel_metadata.datatype.declaration
    assert "GO_ALL_PTS" not in kernel_metadata.datatype.declaration


def test_kernelmetadatasymbol_indexoffset(fortran_reader):
    '''Test that get, set and validate work for index_offset metadata.'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    assert kernel_metadata.index_offset == "GO_OFFSET_SW"
    with pytest.raises(ValueError) as info:
        kernel_metadata.index_offset = "hello"
    assert ("Expected one of ['go_offset_se', 'go_offset_sw', 'go_offset_ne', "
            "'go_offset_nw', 'go_offset_any'] for 'index_offset' metadata, "
            "but found 'hello'." in str(info.value))
    assert "GO_OFFSET_NE" not in kernel_metadata.datatype.declaration
    assert "GO_OFFSET_SW" in kernel_metadata.datatype.declaration
    kernel_metadata.index_offset = "GO_OFFSET_NE"
    assert kernel_metadata.index_offset == "GO_OFFSET_NE"
    assert "GO_OFFSET_NE" in kernel_metadata.datatype.declaration
    assert "GO_OFFSET_SW" not in kernel_metadata.datatype.declaration


def test_kernelmetadatasymbol_args(fortran_reader):
    '''Test that get works for args metadata.'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    assert len(kernel_metadata.args) == 4
    assert isinstance(kernel_metadata.args[0], KernelMetadataSymbol.FieldArg)
    assert isinstance(kernel_metadata.args[1], KernelMetadataSymbol.FieldArg)
    assert isinstance(kernel_metadata.args[2], KernelMetadataSymbol.GridArg)
    assert isinstance(kernel_metadata.args[3], KernelMetadataSymbol.ScalarArg)


def test_kernelmetadatasymbol_code(fortran_reader):
    '''Test that get and set work for code metadata.'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    assert kernel_metadata.code == "compute_cu_code"
    assert "new_code" not in kernel_metadata.datatype.declaration
    assert "compute_cu_code" in kernel_metadata.datatype.declaration
    kernel_metadata.code = "new_code"
    assert kernel_metadata.code == "new_code"
    assert "new_code" in kernel_metadata.datatype.declaration
    assert "compute_cu_code" not in kernel_metadata.datatype.declaration


# internal GridArg class

def test_gridarg_init():
    '''Test that a instance of the GridArg class can be created
    succesfully.

    '''
    reader = FortranStringReader(METADATA)
    spec_part = Fortran2003.Derived_Type_Def(reader)
    arg_list = walk(spec_part, Fortran2003.Ac_Value_List)[0]
    grid_arg = KernelMetadataSymbol.GridArg(arg_list.children[2], None)
    assert isinstance(grid_arg, KernelMetadataSymbol.GridArg)
    assert grid_arg.access == "GO_READ"


def test_gridarg_error():
    '''Test that the expected exception is raised if the number of
    metadata arguments passed info the constructor is incorrect.

    '''
    reader = FortranStringReader(METADATA)
    spec_part = Fortran2003.Derived_Type_Def(reader)
    arg_list = walk(spec_part, Fortran2003.Ac_Value_List)[0]
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol.GridArg(arg_list.children[0], None)
    assert ("There should be 2 kernel metadata arguments for a grid property "
            "but found 3 in go_arg(GO_WRITE, GO_CU, GO_POINTWISE)"
            in str(info.value))


def test_gridarg_writefortranstring(fortran_reader):
    '''Test that the write_fortran_string method in a GridArg instance
    works as expected.

    '''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    grid_arg = kernel_metadata.args[2]
    result = grid_arg.write_fortran_string()
    assert result == "go_arg(GO_READ, GO_GRID_AREA_T)"


def test_gridarg_access(fortran_reader):
    '''Test that get, set and validate work for access metadata.'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    grid_arg = kernel_metadata.args[2]
    assert grid_arg.access == "GO_READ"
    with pytest.raises(ValueError) as info:
        grid_arg.access = "hello"
    assert ("The first metadata entry for a grid property argument should "
            "be one of ['go_read', 'go_write', 'go_readwrite'], but found "
            "'hello'." in str(info.value))
    assert ("GO_WRITE, GO_GRID_AREA_T" not in
            kernel_metadata.datatype.declaration)
    assert "GO_READ, GO_GRID_AREA_T" in kernel_metadata.datatype.declaration
    grid_arg.access = "GO_WRITE"
    assert grid_arg.access == "GO_WRITE"
    assert "GO_WRITE, GO_GRID_AREA_T" in kernel_metadata.datatype.declaration
    assert ("GO_READ, GO_GRID_AREA_T" not in
            kernel_metadata.datatype.declaration)


def test_gridarg_name(fortran_reader):
    '''Test that get, set and validate work for name metadata.'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    grid_arg = kernel_metadata.args[2]
    assert grid_arg.name == "GO_GRID_AREA_T"
    with pytest.raises(ValueError) as info:
        grid_arg.name = "hello"
    print(str(info.value))
    assert ("The second meadata entry for a grid property argument should be "
            "one of ['go_grid_xstop', 'go_grid_ystop', 'go_grid_data', "
            "'go_grid_internal_inner_stop', 'go_grid_internal_outer_stop', "
            "'go_grid_whole_inner_stop', 'go_grid_whole_outer_stop', "
            "'go_grid_internal_inner_start', 'go_grid_internal_outer_start', "
            "'go_grid_whole_inner_start', 'go_grid_whole_outer_start', "
            "'go_grid_area_t', 'go_grid_area_u', 'go_grid_area_v', "
            "'go_grid_mask_t', 'go_grid_dx_t', 'go_grid_dx_u', "
            "'go_grid_dx_v', 'go_grid_dy_t', 'go_grid_dy_u', 'go_grid_dy_v', "
            "'go_grid_lat_u', 'go_grid_lat_v', 'go_grid_dx_const', "
            "'go_grid_dy_const', 'go_grid_nx', 'go_grid_ny', "
            "'go_grid_x_min_index', 'go_grid_x_max_index', "
            "'go_grid_y_min_index', 'go_grid_y_max_index'], but found "
            "'hello'." in str(info.value))
    assert "GO_GRID_XSTOP" not in kernel_metadata.datatype.declaration
    assert "GO_GRID_AREA_T" in kernel_metadata.datatype.declaration
    grid_arg.name = "GO_GRID_XSTOP"
    assert grid_arg.name == "GO_GRID_XSTOP"
    assert "GO_GRID_XSTOP" in kernel_metadata.datatype.declaration
    assert "GO_GRID_AREA_T" not in kernel_metadata.datatype.declaration


# internal FieldArg class

def test_fieldarg_init():
    '''Test that a instance of the FieldArg class can be created
    succesfully.

    '''
    reader = FortranStringReader(METADATA)
    spec_part = Fortran2003.Derived_Type_Def(reader)
    arg_list = walk(spec_part, Fortran2003.Ac_Value_List)[0]
    field_arg = KernelMetadataSymbol.FieldArg(arg_list.children[0], None)
    assert isinstance(field_arg, KernelMetadataSymbol.FieldArg)
    assert field_arg.access == "GO_WRITE"


def test_fieldarg_error():
    '''Test that the expected exception is raised if the number of
    metadata arguments passed info the constructor is incorrect.

    '''
    reader = FortranStringReader(METADATA)
    spec_part = Fortran2003.Derived_Type_Def(reader)
    arg_list = walk(spec_part, Fortran2003.Ac_Value_List)[0]
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol.FieldArg(arg_list.children[2], None)
    print(str(info.value))
    assert ("There should be 3 kernel metadata entries for a field argument, "
            "but found 2 in go_arg(GO_READ, GO_GRID_AREA_T)."
            in str(info.value))


def test_fieldarg_writefortranstring(fortran_reader):
    '''Test that the write_fortran_string method in a FieldArg instance
    works as expected. Test when there is and there is not a stencil.

    '''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    # no stencil
    field_arg = kernel_metadata.args[0]
    result = field_arg.write_fortran_string()
    assert result == "go_arg(GO_WRITE, GO_CU, GO_POINTWISE)"
    # stencil
    field_arg = kernel_metadata.args[1]
    result = field_arg.write_fortran_string()
    assert result == "go_arg(GO_READ, GO_CT, GO_STENCIL(000, 011, 000))"


def test_fieldarg_access(fortran_reader):
    '''Test that get, set and validate work for access metadata.'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    field_arg = kernel_metadata.args[0]
    assert field_arg.access == "GO_WRITE"
    with pytest.raises(ValueError) as info:
        field_arg.access = "hello"
    assert ("The first metadata entry for a field argument should be one of "
            "['go_read', 'go_write', 'go_readwrite'], but found 'hello'."
            in str(info.value))
    assert "GO_READ, GO_CU" not in kernel_metadata.datatype.declaration
    assert "GO_WRITE, GO_CU" in kernel_metadata.datatype.declaration
    field_arg.access = "GO_READ"
    assert field_arg.access == "GO_READ"
    assert "GO_READ, GO_CU" in kernel_metadata.datatype.declaration
    assert "GO_WRITE, GO_CU" not in kernel_metadata.datatype.declaration


def test_fieldarg_stagger(fortran_reader):
    '''Test that get, set and validate work for stagger metadata.'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    field_arg = kernel_metadata.args[0]
    assert field_arg.stagger == "GO_CU"
    with pytest.raises(ValueError) as info:
        field_arg.stagger = "hello"
    assert ("The second metadata entry for a field argument should be one of "
            "['go_cu', 'go_cv', 'go_ct', 'go_cf', 'go_every'], but found "
            "'hello'." in str(info.value))
    assert "GO_CF" not in kernel_metadata.datatype.declaration
    assert "GO_CU" in kernel_metadata.datatype.declaration
    field_arg.stagger = "GO_CF"
    assert field_arg.stagger == "GO_CF"
    assert "GO_CF" in kernel_metadata.datatype.declaration
    assert "GO_CU" not in kernel_metadata.datatype.declaration


def test_fieldarg_form(fortran_reader):
    '''Test that get, set and validate work for form metadata.'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    field_arg = kernel_metadata.args[0]
    assert field_arg.form == "GO_POINTWISE"
    with pytest.raises(ValueError) as info:
        field_arg.form = "hello"
    assert ("The third metadata entry for a field should be one of "
            "['go_pointwise'] or 'go_stencil(...)', but found 'hello'."
            in str(info.value))
    assert "GO_CU, go_pointwise" not in kernel_metadata.datatype.declaration
    assert "GO_CU, GO_POINTWISE" in kernel_metadata.datatype.declaration
    field_arg.form = "go_pointwise"
    assert field_arg.form == "go_pointwise"
    assert "GO_CU, go_pointwise" in kernel_metadata.datatype.declaration
    assert "GO_CU, GO_POINTWISE" not in kernel_metadata.datatype.declaration


def test_fieldarg_stencil(fortran_reader):
    '''Test that get, set and validate work for stencil metadata.'''
    my_program = PROGRAM.replace("GO_STENCIL", "GO_PENCIL")
    kernel_psyir = fortran_reader.psyir_from_source(my_program)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    with pytest.raises(ValueError) as info:
        _ = KernelMetadataSymbol("name", datatype)
    assert ("The third metadata entry for a field should be go_stencil(...) "
            "if it contains arguments, but found 'GO_PENCIL'."
            in str(info.value))
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    field_arg = kernel_metadata.args[1]
    assert field_arg.form == "GO_STENCIL"
    assert len(field_arg.stencil) == 3
    assert field_arg.stencil == ["000", "011", "000"]
    with pytest.raises(TypeError) as info:
        field_arg.stencil = "hello"
    assert ("Stencil entries should be provided as a list, but found 'str'."
            in str(info.value))
    with pytest.raises(ValueError) as info:
        field_arg.stencil = ["hello"]
    assert ("If the third metadata entry is a stencil, it should contain 3 "
            "arguments, but found 1." in str(info.value))
    with pytest.raises(TypeError) as info:
        field_arg.stencil = [0, "hello", "hello"]
    assert ("Stencil entries should be strings, but found 'int'."
            in str(info.value))
    with pytest.raises(ValueError) as info:
        field_arg.stencil = ["000", "011", "00"]
    assert ("Stencil entries should follow the pattern [01]{3:3}, but "
            "found '00'." in str(info.value))

    field_arg = kernel_metadata.args[0]
    assert field_arg.form == "GO_POINTWISE"
    assert field_arg.stencil is None
    assert "GO_CU, GO_POINTWISE" in kernel_metadata.datatype.declaration
    assert ("GO_STENCIL(000, 111, 000)" not in
            kernel_metadata.datatype.declaration)
    field_arg.stencil = ["000", "111", "000"]
    assert field_arg.form == "GO_STENCIL"
    assert field_arg.stencil == ["000", "111", "000"]
    assert "GO_CU, GO_POINTWISE" not in kernel_metadata.datatype.declaration
    assert "GO_STENCIL(000, 111, 000)" in kernel_metadata.datatype.declaration


# internal ScalarArg class

def test_scalararg_init():
    '''Test that a instance of the ScalarArg class can be created
    succesfully.

    '''
    reader = FortranStringReader(METADATA)
    spec_part = Fortran2003.Derived_Type_Def(reader)
    arg_list = walk(spec_part, Fortran2003.Ac_Value_List)[0]
    scalar_arg = KernelMetadataSymbol.ScalarArg(arg_list.children[3], None)
    assert isinstance(scalar_arg, KernelMetadataSymbol.ScalarArg)
    assert scalar_arg.access == "GO_READ"


def test_scalararg_error():
    '''Test that the expected exception is raised if the number of
    metadata arguments passed info the constructor is incorrect.

    '''
    reader = FortranStringReader(METADATA)
    spec_part = Fortran2003.Derived_Type_Def(reader)
    arg_list = walk(spec_part, Fortran2003.Ac_Value_List)[0]
    with pytest.raises(ParseError) as info:
        _ = KernelMetadataSymbol.ScalarArg(arg_list.children[2], None)
    assert ("There should be 3 kernel metadata entries for a scalar argument, "
            "but found 2 in go_arg(GO_READ, GO_GRID_AREA_T)."
            in str(info.value))


def test_scalararg_writefortranstring(fortran_reader):
    '''Test that the write_fortran_string method in a ScalarArg instance
    works as expected.

    '''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    scalar_arg = kernel_metadata.args[3]
    result = scalar_arg.write_fortran_string()
    assert result == "go_arg(GO_READ, GO_R_SCALAR, GO_POINTWISE)"


def test_scalararg_access(fortran_reader):
    '''Test that get, set and validate work for access metadata.'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    scalar_arg = kernel_metadata.args[3]
    assert scalar_arg.access == "GO_READ"
    with pytest.raises(ValueError) as info:
        scalar_arg.access = "hello"
    assert ("The first metadata entry for a scalar argument should be one of "
            "['go_read', 'go_write', 'go_readwrite'], but found 'hello'."
            in str(info.value))
    assert "GO_WRITE, GO_R_SCALAR" not in kernel_metadata.datatype.declaration
    assert "GO_READ, GO_R_SCALAR" in kernel_metadata.datatype.declaration
    scalar_arg.access = "GO_WRITE"
    assert scalar_arg.access == "GO_WRITE"
    assert "GO_WRITE, GO_R_SCALAR" in kernel_metadata.datatype.declaration
    assert "GO_READ, GO_R_SCALAR" not in kernel_metadata.datatype.declaration


def test_scalararg_datatype(fortran_reader):
    '''Test that get, set and validate work for datatype metadata.'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    scalar_arg = kernel_metadata.args[3]
    assert scalar_arg.datatype == "GO_R_SCALAR"
    with pytest.raises(ValueError) as info:
        scalar_arg.datatype = "hello"
    assert ("The second metadata entry for a scalar argument should be "
            "one of ['go_i_scalar', 'go_r_scalar'], but found 'hello'."
            in str(info.value))
    assert "GO_I_SCALAR" not in kernel_metadata.datatype.declaration
    assert "GO_R_SCALAR" in kernel_metadata.datatype.declaration
    scalar_arg.datatype = "GO_I_SCALAR"
    assert scalar_arg.datatype == "GO_I_SCALAR"
    assert "GO_I_SCALAR" in kernel_metadata.datatype.declaration
    assert "GO_R_SCALAR" not in kernel_metadata.datatype.declaration


def test_scalararg_form(fortran_reader):
    '''Test that get, set and validate work for form metadata.'''
    kernel_psyir = fortran_reader.psyir_from_source(PROGRAM)
    datatype = kernel_psyir.children[0]. \
        symbol_table.lookup("compute_cu").datatype
    kernel_metadata = KernelMetadataSymbol("name", datatype)
    scalar_arg = kernel_metadata.args[3]
    assert scalar_arg.form == "GO_POINTWISE"
    with pytest.raises(ValueError) as info:
        scalar_arg.form = "hello"
    assert ("The third metadata entry for a scalar should be one of "
            "['go_pointwise'], but found 'hello'." in str(info.value))
    assert "SCALAR, go_pointwise" not in kernel_metadata.datatype.declaration
    assert "SCALAR, GO_POINTWISE" in kernel_metadata.datatype.declaration
    scalar_arg.form = "go_pointwise"
    assert scalar_arg.form == "go_pointwise"
    assert "SCALAR, go_pointwise" in kernel_metadata.datatype.declaration
    assert "SCALAR, GO_POINTWISE" not in kernel_metadata.datatype.declaration
