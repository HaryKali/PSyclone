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
# Author: A. R. Porter, STFC Daresbury Lab

''' pytest tests for the LFRic-specifc algorithm-generation functionality. '''

import os
import pytest

from psyclone.domain.lfric import KernCallInvokeArgList
from psyclone.domain.lfric.algorithm import alg_gen
from psyclone.errors import InternalError
from psyclone.psyir.nodes import Routine
from psyclone.psyir.symbols import (ContainerSymbol, DataSymbol, DeferredType,
                                    DataTypeSymbol, ImportInterface, ArrayType,
                                    ScalarType, INTEGER_TYPE)
# Constants
BASE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "test_files", "dynamo0p3")


@pytest.fixture(name="prog", scope="function")
def create_prog_fixture():
    '''
    :returns: a PSyIR Routine node representing a program.
    :rtype: :py:class:`psyclone.psyir.nodes.Routine`
    '''
    return Routine("test_prog", is_program=True)


def test_create_alg_driver_wrong_arg_type():
    '''
    Test that _create_alg_driver() rejects arguments of the wrong type.
    '''
    with pytest.raises(TypeError) as err:
        alg_gen._create_alg_driver(5, None)
    assert ("Supplied program name must be a str but got 'int'" in
            str(err.value))
    with pytest.raises(TypeError) as err:
        alg_gen._create_alg_driver("my_test", "5")
    assert ("Supplied number of vertical levels must be an int but got "
            "'str'" in str(err.value))


def test_create_alg_driver(fortran_writer):
    ''' Test the correct operation of _create_alg_driver(). '''
    psyir = alg_gen._create_alg_driver("my_prog", 8)
    assert isinstance(psyir, Routine)
    assert psyir.symbol_table.lookup("r_def")
    # TODO #284 ideally we'd test that the generated code compiles.
    gen = fortran_writer(psyir)
    assert "program my_prog" in gen
    assert "uniform_extrusion_type(0.0_r_def, 100.0_r_def, 8)" in gen


def test_create_function_spaces_no_spaces(prog, fortran_writer):
    ''' Check that a Routine is populated as expected, even when there
    are no actual function spaces. '''
    prog.symbol_table.new_symbol("fs_continuity_mod",
                                 symbol_type=ContainerSymbol)
    alg_gen._create_function_spaces(prog, [])
    assert prog.symbol_table.lookup("element_order")
    assert prog.symbol_table.lookup("ndata_sz")
    gen = fortran_writer(prog)
    assert f"ndata_sz = {alg_gen.NDATA_SIZE}" in gen


def test_create_function_spaces_invalid_space(prog):
    ''' Check that the expected error is raised if an invalid function-space
    name is supplied. '''
    prog.symbol_table.new_symbol("fs_continuity_mod",
                                 symbol_type=ContainerSymbol)
    with pytest.raises(InternalError) as err:
        alg_gen._create_function_spaces(prog, ["w3", "wwrong", "w1"])
    assert ("Function space 'wwrong' is not a valid LFRic function space "
            "(one of [" in str(err.value))


def test_create_function_spaces(prog, fortran_writer):
    ''' Check that a Routine is populated correctly when valid function-space
    names are supplied. '''
    fs_mod_sym = prog.symbol_table.new_symbol("fs_continuity_mod",
                                              symbol_type=ContainerSymbol)
    alg_gen._create_function_spaces(prog, ["w3", "w1"])
    gen = fortran_writer(prog)
    for space in ["w1", "w3"]:
        sym = prog.symbol_table.lookup(space)
        assert sym.interface.container_symbol is fs_mod_sym
        assert (f"TYPE(function_space_type), TARGET :: vector_space_{space}"
                in gen)
        assert (f"TYPE(function_space_type), POINTER :: "
                f"vector_space_{space}_ptr" in gen)
        assert (f"vector_space_{space} = function_space_type(mesh, "
                f"element_order, {space}, ndata_sz)" in gen)
        assert f"vector_space_{space}_ptr => vector_space_{space}" in gen


def test_initialise_field(prog, fortran_writer):
    ''' Test that the initialise_field() function works as expected for both
    individual fields and field vectors. '''
    table = prog.symbol_table
    fmod = table.new_symbol("field_mod", symbol_type=ContainerSymbol)
    ftype = table.new_symbol("field_type", symbol_type=DataTypeSymbol,
                             datatype=DeferredType(),
                             interface=ImportInterface(fmod))
    # First - a single field argument.
    sym = table.new_symbol("field1", symbol_type=DataSymbol, datatype=ftype)
    alg_gen.initialise_field(prog, sym, "w3")
    gen = fortran_writer(prog)
    assert ("CALL field1 % initialise(vector_space = vector_space_w3_ptr, "
            "name = 'field1')" in gen)
    # Second - a field vector.
    dtype = ArrayType(ftype, [3])
    sym = table.new_symbol("fieldv2", symbol_type=DataSymbol, datatype=dtype)
    alg_gen.initialise_field(prog, sym, "w2")
    gen = fortran_writer(prog)
    for idx in range(1, 4):
        assert (f"CALL fieldv2({idx}) % initialise(vector_space = "
                f"vector_space_w2_ptr, name = 'fieldv2')" in gen)
    # Third - invalid type.
    sym._datatype = ScalarType(ScalarType.Intrinsic.INTEGER, 4)
    with pytest.raises(InternalError) as err:
        alg_gen.initialise_field(prog, sym, "w2")
    assert ("Expected a field symbol to either be of ArrayType or have a type "
            "specified by a DataTypeSymbol but found Scalar" in str(err.value))


def test_initialise_quadrature(prog, fortran_writer):
    ''' Tests for the initialise_quadrature function with the supported
    XYoZ shape. '''
    table = prog.symbol_table
    table.new_symbol("element_order", tag="element_order",
                     symbol_type=DataSymbol, datatype=INTEGER_TYPE)
    # Setup symbols that would normally be created in KernCallInvokeArgList.
    quad_container = table.new_symbol(
        "quadrature_xyoz_mod", symbol_type=ContainerSymbol)
    quad_type = table.new_symbol(
        "quadrature_xyoz_type", symbol_type=DataTypeSymbol,
        datatype=DeferredType(), interface=ImportInterface(quad_container))
    sym = table.new_symbol("qr", symbol_type=DataSymbol, datatype=quad_type)

    alg_gen.initialise_quadrature(prog, sym, "gh_quadrature_xyoz")
    # Check that new symbols have been added.
    assert table.lookup("quadrature_rule_gaussian_mod")
    qtype = table.lookup("quadrature_rule_gaussian_type")
    qrule = table.lookup("quadrature_rule")
    assert qrule.datatype is qtype
    # Check that the constructor is called in the generated code.
    gen = fortran_writer(prog)
    assert ("qr = quadrature_xyoz_type(element_order + 3, quadrature_rule)"
            in gen)


def test_initialise_quadrature_unsupported_shape(prog):
    ''' Test that the initialise_quadrature function raises the expected error
    for an unsupported quadrature shape. '''
    table = prog.symbol_table
    table.new_symbol("element_order", tag="element_order",
                     symbol_type=DataSymbol, datatype=INTEGER_TYPE)
    # Setup symbols that would normally be created in KernCallInvokeArgList.
    quad_container = table.new_symbol(
        "quadrature_xyz_mod", symbol_type=ContainerSymbol)
    quad_type = table.new_symbol(
        "quadrature_xyz_type", symbol_type=DataTypeSymbol,
        datatype=DeferredType(), interface=ImportInterface(quad_container))
    sym = table.new_symbol("qr", symbol_type=DataSymbol, datatype=quad_type)

    with pytest.raises(NotImplementedError) as err:
        alg_gen.initialise_quadrature(prog, sym, "gh_quadrature_xyz")
    assert ("Initialisation for quadrature of type 'gh_quadrature_xyz' is "
            "not yet implemented." in str(err.value))


def test_construct_kernel_args(prog, dynkern, fortran_writer):
    ''' Tests for the construct_kernel_args() function. Since this function
    primarily calls _create_function_spaces(), initialise_field(),
    KernCallInvokeArgList.generate() and initialise_quadrature(), all of which
    have their own tests, there isn't a lot to test here. '''
    prog.symbol_table.new_symbol("fs_continuity_mod",
                                 symbol_type=ContainerSymbol)
    field_mod = prog.symbol_table.new_symbol("field_mod",
                                             symbol_type=ContainerSymbol)
    prog.symbol_table.new_symbol("r_def", symbol_type=DataSymbol,
                                 datatype=INTEGER_TYPE)
    prog.symbol_table.new_symbol("i_def", symbol_type=DataSymbol,
                                 datatype=INTEGER_TYPE)
    prog.symbol_table.new_symbol("field_type", symbol_type=DataTypeSymbol,
                                 datatype=DeferredType(),
                                 interface=ImportInterface(field_mod))
    kargs = alg_gen.construct_kernel_args(prog, dynkern)

    assert isinstance(kargs, KernCallInvokeArgList)
    gen = fortran_writer(prog)
    spaces = ["w0", "w1", "w2", "w3", "wtheta"]
    assert f"use fs_continuity_mod, only : {', '.join(spaces)}" in gen
    for space in spaces:
        assert (f"vector_space_{space} = function_space_type(mesh, "
                f"element_order, {space}, ndata_sz)" in gen)
        assert f"vector_space_{space}_ptr => vector_space_{space}" in gen
    for idx in range(2, 7):
        assert f"CALL field_{idx}" in gen
    assert ("qr_xyoz = quadrature_xyoz_type(element_order + 3, "
            "quadrature_rule)" in gen)
    # TODO #240 - test for compilation.


def test_generate_invalid_kernel(tmpdir):
    ''' Check that the generate() function raises NotImplementedError if the
    supplied kernel file does not follow LFRic naming conventions. '''
    kern_file = os.path.join(tmpdir, "fake_kern.f90")
    with open(kern_file, "w", encoding='utf-8') as ffile:
        print('''module my_mod_wrong
end module my_mod_wrong''', file=ffile)
    with pytest.raises(NotImplementedError) as err:
        alg_gen.generate(kern_file)
    assert ("fake_kern.f90) contains a module named 'my_mod_wrong' which does "
            "not follow " in str(err.value))


def test_generate_invalid_field_type(monkeypatch):
    ''' Check that we get the expected internal error if a field object of
    the wrong type is encountered. '''
    # This requires that we monkeypatch the KernCallInvokeArgList class so
    # that it returns an invalid field symbol.

    monkeypatch.setattr(KernCallInvokeArgList, "fields",
                        [(DataSymbol("fld", DeferredType()), None)])
    with pytest.raises(InternalError) as err:
        alg_gen.generate(os.path.join(BASE_PATH, "testkern_mod.F90"))
    assert ("field symbol to either be of ArrayType or have a type specified "
            "by a DataTypeSymbol but found DeferredType for field 'fld'" in
            str(err.value))


def test_generate(fortran_writer):
    ''' Test that the generate() method returns the expected Fortran for a
    valid LFRic kernel that takes a field vector. '''
    code = alg_gen.generate(os.path.join(BASE_PATH,
                                         "testkern_anyw2_vector_mod.f90"))
    print(code)
    assert 0
