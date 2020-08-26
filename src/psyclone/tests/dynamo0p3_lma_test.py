# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2019-2020 Science and Technology Facilities Council.
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
# Authors R. W. Ford and A. R. Porter, STFC Daresbury Lab
# Modified I. Kavcic, Met Office
# Modified J. Henrichs, Bureau of Meteorology

''' This module tests the support for LMA operators in the Dynamo 0.3 API
using pytest. '''

# imports
from __future__ import absolute_import, print_function
import os
import pytest
from fparser import api as fpapi
from psyclone.configuration import Config
from psyclone.core.access_type import AccessType
from psyclone.parse.algorithm import parse
from psyclone.parse.utils import ParseError
from psyclone.psyGen import PSyFactory
from psyclone.errors import GenerationError, InternalError
from psyclone.domain.lfric import LFRicArgDescriptor
from psyclone.dynamo0p3 import DynKernMetadata, DynKern, FunctionSpace
from psyclone.tests.lfric_build import LFRicBuild

# constants
BASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "test_files", "dynamo0p3")

TEST_API = "dynamo0.3"

CODE = '''
module testkern_qr
  type, extends(kernel_type) :: testkern_qr_type
     type(arg_type), meta_args(6) =                     &
          (/ arg_type(gh_scalar,   gh_real,  gh_read),  &
             arg_type(gh_field,    gh_inc, w1),         &
             arg_type(gh_field,    gh_read, w2),        &
             arg_type(gh_operator, gh_read, w2, w2),    &
             arg_type(gh_field,    gh_read, w3),        &
             arg_type(gh_scalar,   gh_integer, gh_read) &
           /)
     type(func_type), dimension(3) :: meta_funcs =   &
          (/ func_type(w1, gh_basis),                &
             func_type(w2, gh_diff_basis),           &
             func_type(w3, gh_basis, gh_diff_basis)  &
           /)
     integer :: iterates_over = cells
     integer :: gh_shape = gh_quadrature_XYoZ
   contains
     procedure, nopass :: code => testkern_qr_code
  end type testkern_qr_type
contains
  subroutine testkern_qr_code(a, b ,c, d)
  end subroutine testkern_qr_code
end module testkern_qr
'''


@pytest.fixture(scope="module", autouse=True)
def setup():
    '''Make sure that all tests here use Dynamo0.3 as API.'''
    Config.get().api = "dynamo0.3"


def test_get_op_wrong_name():
    ''' Tests that the get_operator_name() utility raises an error
    if passed the name of something that is not a valid operator '''
    with pytest.raises(GenerationError) as err:
        FunctionSpace("w3", None).get_operator_name("not_an_op")
    assert "Unsupported name 'not_an_op' found" in str(err.value)


def test_ad_op_type_too_few_args():
    ''' Tests that an error is raised when the operator descriptor
    metadata has fewer than 4 args. '''
    code = CODE.replace("arg_type(gh_operator, gh_read, w2, w2)",
                        "arg_type(gh_operator, gh_read, w2)", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert ("'meta_arg' entry must have 4 arguments if its first "
            "argument is an operator (one of {0})".
            format(LFRicArgDescriptor.VALID_OPERATOR_NAMES) in
            str(excinfo.value))


def test_ad_op_type_too_many_args():
    ''' Tests that an error is raised when the operator descriptor
    metadata has more than 4 args. '''
    code = CODE.replace("arg_type(gh_operator, gh_read, w2, w2)",
                        "arg_type(gh_operator, gh_read, w2, w2, w2)", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert "'meta_arg' entry must have 4 arguments" in str(excinfo.value)


def test_ad_op_type_wrong_3rd_arg():
    ''' Tests that an error is raised when the 3rd entry in the operator
    descriptor metadata is invalid. '''
    code = CODE.replace("arg_type(gh_operator, gh_read, w2, w2)",
                        "arg_type(gh_operator, gh_read, woops, w2)", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert ("LFRic API the 3rd argument of a 'meta_arg' operator entry "
            "must be a valid function space name" in str(excinfo.value))


def test_ad_op_type_1st_arg_not_space():
    ''' Tests that an error is raised when the operator descriptor
    metadata contains something that is not a valid space. '''
    code = CODE.replace("arg_type(gh_operator, gh_read, w2, w2)",
                        "arg_type(gh_operator, gh_read, wbroke, w2)", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert ("'meta_arg' operator entry must be a valid function space" in
            str(excinfo.value))


def test_no_vector_operator():
    ''' Test that we raise an error when kernel metadata erroneously
    specifies a vector operator argument. '''
    code = CODE.replace("arg_type(gh_operator, gh_read, w2, w2)",
                        "arg_type(gh_operator*3, gh_read, w2, w2)", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert ("vector notation is only supported for ['gh_field'] "
            "argument types but found 'gh_operator * 3'" in
            str(excinfo.value))


def test_ad_op_type_validate_wrong_type():
    ''' Test that an error is raised if something other than an operator
    is passed to the LFRicArgDescriptor._init_operator() method. '''
    ast = fpapi.parse(CODE, ignore_comments=False)
    name = "testkern_qr_type"
    metadata = DynKernMetadata(ast, name=name)
    # Get an argument which is not an operator
    wrong_arg = metadata._inits[1]
    with pytest.raises(InternalError) as excinfo:
        LFRicArgDescriptor(wrong_arg)._init_operator(wrong_arg)
    assert ("LFRicArgDescriptor._init_operator(): Expected an "
            "operator argument but got an argument of type 'gh_field'."
            in str(excinfo.value))


def test_ad_op_type_wrong_access():
    ''' Test that an error is raised if an operator has 'gh_inc' access. '''
    code = CODE.replace("arg_type(gh_operator, gh_read, w2, w2)",
                        "arg_type(gh_operator, gh_inc, w2, w2)", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert ("In the LFRic API, allowed accesses for operators are "
            "['gh_read', 'gh_write', 'gh_readwrite'] because they behave "
            "as discontinuous quantities, but found 'gh_inc'" in
            str(excinfo.value))


def test_arg_descriptor_op():
    ''' Test that the LFRicArgDescriptor argument representation works
    as expected when we have an operator. '''
    ast = fpapi.parse(CODE, ignore_comments=False)
    name = "testkern_qr_type"
    metadata = DynKernMetadata(ast, name=name)
    operator_descriptor = metadata.arg_descriptors[3]

    # Assert correct string representation from LFRicArgDescriptor
    result = str(operator_descriptor)
    expected_output = (
        "LFRicArgDescriptor object\n"
        "  argument_type[0]='gh_operator'\n"
        "  data_type[1]='gh_real'\n"
        "  access_descriptor[2]='gh_read'\n"
        "  function_space_to[3]='w2'\n"
        "  function_space_from[4]='w2'\n")
    assert expected_output in result

    # Check LFRicArgDescriptor argument properties
    assert operator_descriptor.argument_type == "gh_operator"
    assert operator_descriptor.data_type == "gh_real"
    assert operator_descriptor.function_space_to == "w2"
    assert operator_descriptor.function_space_from == "w2"
    assert operator_descriptor.function_space == "w2"
    assert operator_descriptor.function_spaces == ['w2', 'w2']
    assert str(operator_descriptor.access) == "READ"
    assert operator_descriptor.mesh is None
    assert operator_descriptor.stencil is None
    assert operator_descriptor.vector_size == 1


def test_fs_descriptor_wrong_type():
    ''' Tests that an error is raised when the function space descriptor
    metadata is not of type func_type. '''
    code = CODE.replace("func_type(w2", "funced_up_type(w2", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert ("'meta_funcs' metadata must consist of an array of structure "
            "constructors, all of type 'func_type'" in str(excinfo.value))
    # Check that the DynFuncDescriptor03 rejects it too
    from psyclone.dynamo0p3 import DynFuncDescriptor03

    class FakeCls(object):
        ''' Class that just has a name property (which is not "func_type") '''
        name = "not-func-type"

    with pytest.raises(ParseError) as excinfo:
        DynFuncDescriptor03(FakeCls())
    assert ("each meta_func entry must be of type 'func_type' but found "
            in str(excinfo.value))


def test_fs_descriptor_too_few_args():
    ''' Tests that an error is raised when there are two few arguments in
    the function space descriptor metadata (must be at least 2). '''
    code = CODE.replace("w1, gh_basis", "w1", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert 'meta_func entry must have at least 2 args' in str(excinfo.value)


def test_fs_desc_invalid_fs_type():
    ''' Tests that an error is raised when an invalid function space name
    is provided as the first argument. '''
    code = CODE.replace("w3, gh_basis", "w4, gh_basis", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert '1st argument of a meta_func entry should be a valid function ' + \
        'space name' in str(excinfo.value)


def test_fs_desc_replicated_fs_type():
    ''' Tests that an error is raised when a function space name
    is replicated. '''
    code = CODE.replace("w3, gh_basis", "w1, gh_basis", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert 'function spaces specified in meta_funcs must be unique' \
        in str(excinfo.value)


def test_fs_desc_invalid_op_type():
    ''' Tests that an error is raised when an invalid function space
    operator name is provided as an argument. '''
    code = CODE.replace("w2, gh_diff_basis", "w2, gh_dif_basis", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert '2nd argument and all subsequent arguments of a meta_func ' + \
        'entry should be one of' in str(excinfo.value)


def test_fs_desc_replicated_op_type():
    ''' Tests that an error is raised when a function space
    operator name is replicated as an argument. '''
    code = CODE.replace("w3, gh_basis, gh_diff_basis",
                        "w3, gh_basis, gh_basis", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert 'error to specify an operator name more than once' \
        in str(excinfo.value)


def test_fsdesc_fs_not_in_argdesc():
    ''' Tests that an error is raised when a function space
    name is provided that has not been used in the arg descriptor. '''
    code = CODE.replace("w3, gh_basis", "w0, gh_basis", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    name = "testkern_qr_type"
    with pytest.raises(ParseError) as excinfo:
        _ = DynKernMetadata(ast, name=name)
    assert 'function spaces specified in meta_funcs must exist in ' + \
        'meta_args' in str(excinfo.value)


def test_operator(tmpdir):
    ''' Tests that an LMA operator is implemented correctly in the PSy
    layer. '''
    _, invoke_info = parse(os.path.join(BASE_PATH, "10_operator.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API, distributed_memory=True).create(invoke_info)
    generated_code = str(psy.gen)

    assert LFRicBuild(tmpdir).code_compiles(psy)

    assert (
        "SUBROUTINE invoke_0_testkern_operator_type(mm_w0, coord, a, qr)"
        in generated_code)
    assert "TYPE(operator_type), intent(in) :: mm_w0" in generated_code
    assert "TYPE(operator_proxy_type) mm_w0_proxy" in generated_code
    assert "mm_w0_proxy = mm_w0%get_proxy()" in generated_code
    assert ("CALL testkern_operator_code(cell, nlayers, mm_w0_proxy%ncell_3d, "
            "mm_w0_proxy%local_stencil, coord_proxy(1)%data, "
            "coord_proxy(2)%data, coord_proxy(3)%data, a, ndf_w0, undf_w0, "
            "map_w0(:,cell), basis_w0_qr, diff_basis_w0_qr, np_xy_qr, "
            "np_z_qr, weights_xy_qr, weights_z_qr)") in generated_code


def test_operator_different_spaces(tmpdir):
    ''' Tests that an operator with different to and from spaces is
    implemented correctly in the PSy layer.

    '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "10.3_operator_different_spaces.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API, distributed_memory=True).create(invoke_info)
    generated_code = str(psy.gen)

    assert LFRicBuild(tmpdir).code_compiles(psy)

    decl_output = (
        "    SUBROUTINE invoke_0_assemble_weak_derivative_w3_w2_kernel_type"
        "(mapping, coord, qr)\n"
        "      USE assemble_weak_derivative_w3_w2_kernel_mod, ONLY: "
        "assemble_weak_derivative_w3_w2_kernel_code\n"
        "      USE quadrature_xyoz_mod, ONLY: quadrature_xyoz_type, "
        "quadrature_xyoz_proxy_type\n"
        "      USE function_space_mod, ONLY: BASIS, DIFF_BASIS\n"
        "      USE mesh_mod, ONLY: mesh_type\n"
        "      TYPE(field_type), intent(in) :: coord(3)\n"
        "      TYPE(operator_type), intent(in) :: mapping\n"
        "      TYPE(quadrature_xyoz_type), intent(in) :: qr\n"
        "      INTEGER(KIND=i_def) cell\n"
        "      REAL(KIND=r_def), allocatable :: diff_basis_w0_qr(:,:,:,:), "
        "basis_w3_qr(:,:,:,:), diff_basis_w2_qr(:,:,:,:)\n"
        "      INTEGER(KIND=i_def) diff_dim_w0, dim_w3, diff_dim_w2\n"
        "      REAL(KIND=r_def), pointer :: weights_xy_qr(:) => null(), "
        "weights_z_qr(:) => null()\n"
        "      INTEGER(KIND=i_def) np_xy_qr, np_z_qr\n"
        "      INTEGER(KIND=i_def) nlayers\n"
        "      TYPE(operator_proxy_type) mapping_proxy\n"
        "      TYPE(field_proxy_type) coord_proxy(3)\n"
        "      TYPE(quadrature_xyoz_proxy_type) qr_proxy\n"
        "      INTEGER(KIND=i_def), pointer :: map_w0(:,:) => null()\n"
        "      INTEGER(KIND=i_def) ndf_w3, ndf_w2, ndf_w0, undf_w0\n"
        "      TYPE(mesh_type), pointer :: mesh => null()\n"
        "      INTEGER(KIND=i_def), pointer :: orientation_w2(:) => null()\n")
    assert decl_output in generated_code
    output = (
        "      !\n"
        "      ! Initialise field and/or operator proxies\n"
        "      !\n"
        "      mapping_proxy = mapping%get_proxy()\n"
        "      coord_proxy(1) = coord(1)%get_proxy()\n"
        "      coord_proxy(2) = coord(2)%get_proxy()\n"
        "      coord_proxy(3) = coord(3)%get_proxy()\n"
        "      !\n"
        "      ! Initialise number of layers\n"
        "      !\n"
        "      nlayers = mapping_proxy%fs_from%get_nlayers()\n"
        "      !\n"
        "      ! Create a mesh object\n"
        "      !\n"
        "      mesh => mapping_proxy%fs_from%get_mesh()\n"
        "      !\n"
        "      ! Look-up dofmaps for each function space\n"
        "      !\n"
        "      map_w0 => coord_proxy(1)%vspace%get_whole_dofmap()\n"
        "      !\n"
        "      ! Initialise number of DoFs for w3\n"
        "      !\n"
        "      ndf_w3 = mapping_proxy%fs_to%get_ndf()\n"
        "      !\n"
        "      ! Initialise number of DoFs for w2\n"
        "      !\n"
        "      ndf_w2 = mapping_proxy%fs_from%get_ndf()\n"
        "      !\n"
        "      ! Initialise number of DoFs for w0\n"
        "      !\n"
        "      ndf_w0 = coord_proxy(1)%vspace%get_ndf()\n"
        "      undf_w0 = coord_proxy(1)%vspace%get_undf()\n"
        "      !\n"
        "      ! Look-up quadrature variables\n"
        "      !\n"
        "      qr_proxy = qr%get_quadrature_proxy()\n"
        "      np_xy_qr = qr_proxy%np_xy\n"
        "      np_z_qr = qr_proxy%np_z\n"
        "      weights_xy_qr => qr_proxy%weights_xy\n"
        "      weights_z_qr => qr_proxy%weights_z\n"
        "      !\n"
        "      ! Allocate basis/diff-basis arrays\n"
        "      !\n"
        "      diff_dim_w0 = coord_proxy(1)%vspace%get_dim_space_diff()\n"
        "      dim_w3 = mapping_proxy%fs_to%get_dim_space()\n"
        "      diff_dim_w2 = mapping_proxy%fs_from%get_dim_space_diff()\n"
        "      ALLOCATE (diff_basis_w0_qr(diff_dim_w0, ndf_w0, np_xy_qr, "
        "np_z_qr))\n"
        "      ALLOCATE (basis_w3_qr(dim_w3, ndf_w3, np_xy_qr, np_z_qr))\n"
        "      ALLOCATE (diff_basis_w2_qr(diff_dim_w2, ndf_w2, np_xy_qr, "
        "np_z_qr))\n"
        "      !\n"
        "      ! Compute basis/diff-basis arrays\n"
        "      !\n"
        "      CALL qr%compute_function(DIFF_BASIS, coord_proxy(1)%vspace, "
        "diff_dim_w0, ndf_w0, diff_basis_w0_qr)\n"
        "      CALL qr%compute_function(BASIS, mapping_proxy%fs_to, "
        "dim_w3, ndf_w3, basis_w3_qr)\n"
        "      CALL qr%compute_function(DIFF_BASIS, mapping_proxy%fs_from, "
        "diff_dim_w2, ndf_w2, diff_basis_w2_qr)\n"
        "      !\n"
        "      ! Call kernels and communication routines\n"
        "      !\n"
        "      IF (coord_proxy(1)%is_dirty(depth=1)) THEN\n"
        "        CALL coord_proxy(1)%halo_exchange(depth=1)\n"
        "      END IF\n"
        "      !\n"
        "      IF (coord_proxy(2)%is_dirty(depth=1)) THEN\n"
        "        CALL coord_proxy(2)%halo_exchange(depth=1)\n"
        "      END IF\n"
        "      !\n"
        "      IF (coord_proxy(3)%is_dirty(depth=1)) THEN\n"
        "        CALL coord_proxy(3)%halo_exchange(depth=1)\n"
        "      END IF\n"
        "      !\n"
        "      DO cell=1,mesh%get_last_halo_cell(1)\n"
        "        !\n"
        "        orientation_w2 => mapping_proxy%fs_from%get_cell_orientation("
        "cell)\n"
        "        !\n"
        "        CALL assemble_weak_derivative_w3_w2_kernel_code(cell, "
        "nlayers, mapping_proxy%ncell_3d, mapping_proxy%local_stencil, "
        "coord_proxy(1)%data, coord_proxy(2)%data, coord_proxy(3)%data, "
        "ndf_w3, basis_w3_qr, ndf_w2, diff_basis_w2_qr, orientation_w2, "
        "ndf_w0, undf_w0, map_w0(:,cell), diff_basis_w0_qr, "
        "np_xy_qr, np_z_qr, weights_xy_qr, weights_z_qr)\n"
        "      END DO\n"
        "      !\n"
        "      ! Deallocate basis arrays\n"
        "      !\n"
        "      DEALLOCATE (basis_w3_qr, diff_basis_w0_qr, diff_basis_w2_qr)\n"
        "      !\n"
        "    END SUBROUTINE invoke_0_assemble_weak_derivative_w3_w2_kernel_"
        "type")
    assert output in generated_code


def test_operator_nofield(tmpdir):
    ''' Tests that an operator with no field on the same space is
    implemented correctly in the PSy layer. '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "10.1_operator_nofield.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API, distributed_memory=True).create(invoke_info)
    gen_code_str = str(psy.gen)

    assert LFRicBuild(tmpdir).code_compiles(psy)

    assert (
        "SUBROUTINE invoke_0_testkern_operator_nofield_type(mm_w2, coord, qr)"
        in gen_code_str)
    assert "TYPE(operator_type), intent(in) :: mm_w2" in gen_code_str
    assert "TYPE(operator_proxy_type) mm_w2_proxy" in gen_code_str
    assert "mm_w2_proxy = mm_w2%get_proxy()" in gen_code_str
    assert "undf_w2" not in gen_code_str
    assert "map_w2" not in gen_code_str
    assert ("CALL testkern_operator_nofield_code(cell, nlayers, "
            "mm_w2_proxy%ncell_3d, mm_w2_proxy%local_stencil, "
            "coord_proxy(1)%data, coord_proxy(2)%data, coord_proxy(3)%data, "
            "ndf_w2, basis_w2_qr, ndf_w0, undf_w0, "
            "map_w0(:,cell), diff_basis_w0_qr, np_xy_qr, np_z_qr, "
            "weights_xy_qr, weights_z_qr)" in gen_code_str)


def test_operator_nofield_different_space(tmpdir):
    ''' Tests that an operator with no field on different spaces is
    implemented correctly in the PSy layer. '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "10.5_operator_no_field_different_"
                                        "space.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API, distributed_memory=True).create(invoke_info)
    gen = str(psy.gen)

    assert LFRicBuild(tmpdir).code_compiles(psy)

    assert "mesh => my_mapping_proxy%fs_from%get_mesh()" in gen
    assert "nlayers = my_mapping_proxy%fs_from%get_nlayers()" in gen
    assert "ndf_w3 = my_mapping_proxy%fs_from%get_ndf()" in gen
    assert "ndf_w2 = my_mapping_proxy%fs_to%get_ndf()" in gen
    # We compute operators redundantly (out to the L1 halo)
    assert "DO cell=1,mesh%get_last_halo_cell(1)" in gen
    assert ("(cell, nlayers, my_mapping_proxy%ncell_3d, my_mapping_proxy%"
            "local_stencil, ndf_w2, ndf_w3)" in gen)


def test_operator_nofield_scalar(tmpdir):
    ''' Tests that an operator with no field and a
    scalar argument is implemented correctly in the PSy layer '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "10.6_operator_no_field_scalar.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API, distributed_memory=True).create(invoke_info)
    gen = str(psy.gen)

    assert LFRicBuild(tmpdir).code_compiles(psy)
    assert "mesh => my_mapping_proxy%fs_from%get_mesh()" in gen
    assert "nlayers = my_mapping_proxy%fs_from%get_nlayers()" in gen
    assert "ndf_w2 = my_mapping_proxy%fs_from%get_ndf()" in gen
    assert "DO cell=1,mesh%get_last_halo_cell(1)" in gen
    assert ("(cell, nlayers, my_mapping_proxy%ncell_3d, my_mapping_proxy%"
            "local_stencil, b, ndf_w2, basis_w2_qr, np_xy_qr, np_z_qr, "
            "weights_xy_qr, weights_z_qr)" in gen)


def test_operator_nofield_scalar_deref(tmpdir, dist_mem):
    ''' Tests that an operator with no field and a
    scalar argument is implemented correctly in the PSy layer when both
    are obtained by dereferencing derived type objects. '''
    _, invoke_info = parse(
        os.path.join(BASE_PATH,
                     "10.6.1_operator_no_field_scalar_deref.f90"),
        api=TEST_API)
    psy = PSyFactory(TEST_API,
                     distributed_memory=dist_mem).create(invoke_info)
    gen = str(psy.gen)

    assert LFRicBuild(tmpdir).code_compiles(psy)

    if dist_mem:
        assert "mesh => opbox_my_mapping_proxy%fs_from%get_mesh()" in gen
    assert "nlayers = opbox_my_mapping_proxy%fs_from%get_nlayers()" in gen
    assert "ndf_w2 = opbox_my_mapping_proxy%fs_from%get_ndf()" in gen
    assert ("qr_init_quadrature_symmetrical%compute_function(BASIS, "
            "opbox_my_mapping_proxy%fs_from, dim_w2, ndf_w2, "
            "basis_w2_qr_init_quadrature_symmetrical)" in gen)
    if dist_mem:
        assert "DO cell=1,mesh%get_last_halo_cell(1)" in gen
    else:
        assert (
            "DO cell=1,opbox_my_mapping_proxy%fs_from%get_ncell()" in gen)
    assert (
        "(cell, nlayers, opbox_my_mapping_proxy%ncell_3d, "
        "opbox_my_mapping_proxy%local_stencil, box_b, ndf_w2, "
        "basis_w2_qr_init_quadrature_symmetrical, "
        "np_xy_qr_init_quadrature_symmetrical, "
        "np_z_qr_init_quadrature_symmetrical, "
        "weights_xy_qr_init_quadrature_symmetrical, "
        "weights_z_qr_init_quadrature_symmetrical)" in gen)


def test_operator_orientation(tmpdir):
    ''' Tests that an operator requiring orientation information is
    implemented correctly in the PSy layer. '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "10.2_operator_orient.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API, distributed_memory=True).create(invoke_info)
    gen_str = str(psy.gen)

    assert LFRicBuild(tmpdir).code_compiles(psy)

    assert (
        "SUBROUTINE invoke_0_testkern_operator_orient_type(mm_w1, coord, qr)"
        in gen_str)
    assert "TYPE(operator_type), intent(in) :: mm_w1" in gen_str
    assert "TYPE(operator_proxy_type) mm_w1_proxy" in gen_str
    assert "mm_w1_proxy = mm_w1%get_proxy()" in gen_str
    assert (
        "orientation_w1 => mm_w1_proxy%fs_from%get_cell_orientation"
        "(cell)" in gen_str)
    assert ("CALL testkern_operator_orient_code(cell, nlayers, "
            "mm_w1_proxy%ncell_3d, mm_w1_proxy%local_stencil, "
            "coord_proxy(1)%data, coord_proxy(2)%data, coord_proxy(3)%data, "
            "ndf_w1, basis_w1_qr, orientation_w1, ndf_w0, undf_w0, "
            "map_w0(:,cell), diff_basis_w0_qr, np_xy_qr, np_z_qr, "
            "weights_xy_qr, weights_z_qr)" in gen_str)


def test_op_orient_different_space(tmpdir):
    ''' Tests that an operator on different spaces requiring orientation
    information is implemented correctly in the PSy layer. '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "10.4_operator_orient_different_"
                                        "space.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API, distributed_memory=True).create(invoke_info)
    gen_str = str(psy.gen)

    assert LFRicBuild(tmpdir).code_compiles(psy)

    assert (
        "INTEGER(KIND=i_def), pointer :: orientation_w1(:) => null(), "
        "orientation_w2(:) => null()" in gen_str)
    assert "ndf_w2 = my_mapping_proxy%fs_from%get_ndf()" in gen_str
    assert "ndf_w1 = my_mapping_proxy%fs_to%get_ndf()" in gen_str
    assert "dim_w1 = my_mapping_proxy%fs_to%get_dim_space()" in gen_str
    assert ("CALL qr%compute_function(BASIS, my_mapping_proxy%fs_to, "
            "dim_w1, ndf_w1, basis_w1_qr)" in gen_str)
    assert (
        "orientation_w2 => my_mapping_proxy%fs_from%get_cell_orientation("
        "cell)" in gen_str)
    assert (
        "orientation_w1 => my_mapping_proxy%fs_to%get_cell_orientation(cell)"
        in gen_str)
    assert ("(cell, nlayers, my_mapping_proxy%ncell_3d, "
            "my_mapping_proxy%local_stencil, coord_proxy(1)%data, "
            "coord_proxy(2)%data, coord_proxy(3)%data, ndf_w1, basis_w1_qr, "
            "orientation_w1, ndf_w2, orientation_w2, ndf_w0, undf_w0, "
            "map_w0(:,cell), diff_basis_w0_qr, np_xy_qr, np_z_qr, "
            "weights_xy_qr, weights_z_qr)" in gen_str)


def test_operator_deref(tmpdir, dist_mem):
    ''' Tests that we generate correct names for an operator in the PSy
    layer when obtained by de-referencing a derived type in the Algorithm
    layer. '''
    _, invoke_info = parse(os.path.join(BASE_PATH, "10.8_operator_deref.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API,
                     distributed_memory=dist_mem).create(invoke_info)
    generated_code = str(psy.gen)

    assert LFRicBuild(tmpdir).code_compiles(psy)

    assert (
        "SUBROUTINE invoke_0_testkern_operator_type(mm_w0_op, coord, a, qr)"
        in generated_code)
    assert "TYPE(operator_type), intent(in) :: mm_w0_op" in generated_code
    assert "TYPE(operator_proxy_type) mm_w0_op_proxy" in generated_code
    assert "mm_w0_op_proxy = mm_w0_op%get_proxy()" in generated_code
    assert (
        "CALL testkern_operator_code(cell, nlayers, "
        "mm_w0_op_proxy%ncell_3d, mm_w0_op_proxy%local_stencil, "
        "coord_proxy(1)%data, coord_proxy(2)%data, coord_proxy(3)%data, a, "
        "ndf_w0, undf_w0, map_w0(:,cell), basis_w0_qr, "
        "diff_basis_w0_qr, np_xy_qr, np_z_qr, weights_xy_qr, "
        "weights_z_qr)" in generated_code)


def test_operator_no_dofmap_lookup():
    ''' Check that we use a field rather than an operator to look-up
    a dofmap, even when the operator precedes the field in the argument
    list. '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "10.9_operator_first.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API, distributed_memory=True).create(invoke_info)
    gen_code = str(psy.gen)
    # Check that we use the field and not the operator to look-up the dofmap
    assert "theta_proxy%vspace%get_whole_dofmap()" in gen_code
    assert gen_code.count("get_whole_dofmap") == 1


def test_operator_read_level1_halo(tmpdir):
    ''' Check that we raise an error if a kernel attempts to read from an
    operator beyond the level-1 halo. '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "10.7_operator_read.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API, distributed_memory=True).create(invoke_info)

    assert LFRicBuild(tmpdir).code_compiles(psy)

    schedule = psy.invokes.invoke_list[0].schedule
    loop = schedule.children[0]
    # Modify the loop bound so that we attempt to read from the L2 halo
    # (of the operator)
    loop.set_upper_bound("cell_halo", index=2)
    # Attempt to generate the code
    with pytest.raises(GenerationError) as excinfo:
        _ = psy.gen
    assert ("Kernel 'testkern_operator_read_code' reads from an operator and "
            "therefore cannot be used for cells beyond the level 1 halo. "
            "However the containing loop goes out to level 2"
            in str(excinfo.value))


def test_operator_bc_kernel(tmpdir):
    ''' Tests that a kernel with a particular name is recognised as
    a kernel that applies boundary conditions to operators and that
    appropriate code is added to support this.

    '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "12.4_enforce_op_bc_kernel.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API, distributed_memory=True).create(invoke_info)
    generated_code = str(psy.gen)
    output1 = (
        "INTEGER(KIND=i_def), pointer :: boundary_dofs_op_a(:,:) => null()")
    assert output1 in generated_code
    output2 = "boundary_dofs_op_a => op_a_proxy%fs_to%get_boundary_dofs()"
    assert output2 in generated_code
    output3 = (
        "CALL enforce_operator_bc_code(cell, nlayers, op_a_proxy%ncell_3d, "
        "op_a_proxy%local_stencil, ndf_aspc1_op_a, ndf_aspc2_op_a, "
        "boundary_dofs_op_a)")
    assert output3 in generated_code

    assert LFRicBuild(tmpdir).code_compiles(psy)


def test_operator_bc_kernel_fld_err(monkeypatch, dist_mem):
    ''' Test that we reject the recognised operator boundary conditions
    kernel if its argument is not an operator '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "12.4_enforce_op_bc_kernel.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API,
                     distributed_memory=dist_mem).create(invoke_info)
    schedule = psy.invokes.invoke_list[0].schedule
    loop = schedule.children[0]
    call = loop.loop_body[0]
    arg = call.arguments.args[0]
    # Monkeypatch the argument object so that it thinks it is a
    # field rather than an operator
    monkeypatch.setattr(arg, "_argument_type", value="gh_field")
    with pytest.raises(GenerationError) as excinfo:
        _ = psy.gen
    assert ("Expected an LMA operator from which to look-up boundary dofs "
            "but kernel enforce_operator_bc_code has argument gh_field") \
        in str(excinfo.value)


def test_operator_bc_kernel_multi_args_err(dist_mem):
    ''' Test that we reject the recognised operator boundary conditions
    kernel if it has more than one argument '''
    import copy
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "12.4_enforce_op_bc_kernel.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API,
                     distributed_memory=dist_mem).create(invoke_info)
    schedule = psy.invokes.invoke_list[0].schedule
    loop = schedule.children[0]
    call = loop.loop_body[0]
    arg = call.arguments.args[0]
    # Make the list of arguments invalid by duplicating (a copy of)
    # this argument. We take a copy because otherwise, when we change
    # the type of arg 1 below, we change it for both.
    call.arguments.args.append(copy.copy(arg))
    with pytest.raises(GenerationError) as excinfo:
        _ = psy.gen
    assert ("Kernel enforce_operator_bc_code has 2 arguments when it "
            "should only have 1 (an LMA operator)") in str(excinfo.value)
    # And again but make the second argument a field this time
    call.arguments.args[1]._argument_type = "gh_field"
    with pytest.raises(GenerationError) as excinfo:
        _ = psy.gen
    assert ("Kernel enforce_operator_bc_code has 2 arguments when it "
            "should only have 1 (an LMA operator)") in str(excinfo.value)


def test_operator_bc_kernel_wrong_access_err(dist_mem):
    ''' Test that we reject the recognised operator boundary conditions
    kernel if its operator argument has the wrong access type '''
    _, invoke_info = parse(os.path.join(BASE_PATH,
                                        "12.4_enforce_op_bc_kernel.f90"),
                           api=TEST_API)
    psy = PSyFactory(TEST_API,
                     distributed_memory=dist_mem).create(invoke_info)
    schedule = psy.invokes.invoke_list[0].schedule
    loop = schedule.children[0]
    call = loop.loop_body[0]
    arg = call.arguments.args[0]
    arg._access = AccessType.READ
    with pytest.raises(GenerationError) as excinfo:
        _ = psy.gen
    assert ("applies boundary conditions to an operator. However its "
            "operator argument has access gh_read rather than "
            "gh_readwrite") in str(excinfo.value)


# Operators : spaces and intent (except for Wchi space as the fields on
# this space are read-only).
OPERATORS = '''
module dummy_mod
  type, extends(kernel_type) :: dummy_type
     type(arg_type), meta_args(13) =                                        &
          (/ arg_type(gh_operator, gh_write,     w0, w0),                   &
             arg_type(gh_operator, gh_readwrite, w1, w1),                   &
             arg_type(gh_operator, gh_read,      w2, w2),                   &
             arg_type(gh_operator, gh_read,      w2h, w2h),                 &
             arg_type(gh_operator, gh_readwrite, w2v, w2v),                 &
             arg_type(gh_operator, gh_write,     w2broken, w2broken),       &
             arg_type(gh_operator, gh_read,      w2trace, w2trace),         &
             arg_type(gh_operator, gh_read,      w2htrace, w2htrace),       &
             arg_type(gh_operator, gh_readwrite, w2vtrace, w2vtrace),       &
             arg_type(gh_operator, gh_write,     w3, w3),                   &
             arg_type(gh_operator, gh_write,     wtheta, wtheta),           &
             arg_type(gh_operator, gh_read,      any_space_1, any_space_1), &
             arg_type(gh_operator, gh_read,      any_discontinuous_space_1, &
                                                 any_discontinuous_space_1) &
           /)
     integer :: iterates_over = cells
   contains
     procedure, nopass :: code => dummy_code
  end type dummy_type
contains
  subroutine dummy_code()
  end subroutine dummy_code
end module dummy_mod
'''


def test_operators():
    ''' Test that operators are handled correctly for kernel stubs (except
    for Wchi space as the fields on this space are read-only).

    '''
    ast = fpapi.parse(OPERATORS, ignore_comments=False)
    metadata = DynKernMetadata(ast)
    kernel = DynKern()
    kernel.load_meta(metadata)
    generated_code = str(kernel.gen_stub)
    output = (
        "  MODULE dummy_mod\n"
        "    IMPLICIT NONE\n"
        "    CONTAINS\n"
        "    SUBROUTINE dummy_code(cell, nlayers, op_1_ncell_3d, op_1, "
        "op_2_ncell_3d, op_2, op_3_ncell_3d, op_3, op_4_ncell_3d, op_4, "
        "op_5_ncell_3d, op_5, op_6_ncell_3d, op_6, op_7_ncell_3d, op_7, "
        "op_8_ncell_3d, op_8, op_9_ncell_3d, op_9, op_10_ncell_3d, op_10, "
        "op_11_ncell_3d, op_11, op_12_ncell_3d, op_12, op_13_ncell_3d, "
        "op_13, ndf_w0, ndf_w1, ndf_w2, ndf_w2h, ndf_w2v, ndf_w2broken, "
        "ndf_w2trace, ndf_w2htrace, ndf_w2vtrace, ndf_w3, ndf_wtheta, "
        "ndf_aspc1_op_12, ndf_adspc1_op_13)\n"
        "      USE constants_mod, ONLY: r_def, i_def\n"
        "      IMPLICIT NONE\n"
        "      INTEGER(KIND=i_def), intent(in) :: nlayers\n"
        "      INTEGER(KIND=i_def), intent(in) :: ndf_w0, ndf_w1, ndf_w2, "
        "ndf_w2h, ndf_w2v, ndf_w2broken, ndf_w2trace, ndf_w2htrace, "
        "ndf_w2vtrace, ndf_w3, ndf_wtheta, ndf_aspc1_op_12, ndf_adspc1_op_13\n"
        "      INTEGER(KIND=i_def), intent(in) :: cell\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_1_ncell_3d\n"
        "      REAL(KIND=r_def), intent(out), dimension(ndf_w0,ndf_w0,"
        "op_1_ncell_3d) :: op_1\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_2_ncell_3d\n"
        "      REAL(KIND=r_def), intent(inout), dimension(ndf_w1,ndf_w1,"
        "op_2_ncell_3d) :: op_2\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_3_ncell_3d\n"
        "      REAL(KIND=r_def), intent(in), dimension(ndf_w2,ndf_w2,"
        "op_3_ncell_3d) :: op_3\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_4_ncell_3d\n"
        "      REAL(KIND=r_def), intent(in), dimension(ndf_w2h,ndf_w2h,"
        "op_4_ncell_3d) :: op_4\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_5_ncell_3d\n"
        "      REAL(KIND=r_def), intent(inout), dimension(ndf_w2v,ndf_w2v,"
        "op_5_ncell_3d) :: op_5\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_6_ncell_3d\n"
        "      REAL(KIND=r_def), intent(out), dimension(ndf_w2broken,"
        "ndf_w2broken,op_6_ncell_3d) :: op_6\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_7_ncell_3d\n"
        "      REAL(KIND=r_def), intent(in), dimension(ndf_w2trace,"
        "ndf_w2trace,op_7_ncell_3d) :: op_7\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_8_ncell_3d\n"
        "      REAL(KIND=r_def), intent(in), dimension(ndf_w2htrace,"
        "ndf_w2htrace,op_8_ncell_3d) :: op_8\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_9_ncell_3d\n"
        "      REAL(KIND=r_def), intent(inout), dimension(ndf_w2vtrace,"
        "ndf_w2vtrace,op_9_ncell_3d) :: op_9\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_10_ncell_3d\n"
        "      REAL(KIND=r_def), intent(out), dimension(ndf_w3,ndf_w3,"
        "op_10_ncell_3d) :: op_10\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_11_ncell_3d\n"
        "      REAL(KIND=r_def), intent(out), dimension(ndf_wtheta,ndf_wtheta,"
        "op_11_ncell_3d) :: op_11\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_12_ncell_3d\n"
        "      REAL(KIND=r_def), intent(in), dimension(ndf_aspc1_op_12,"
        "ndf_aspc1_op_12,op_12_ncell_3d) :: op_12\n"
        "      INTEGER(KIND=i_def), intent(in) :: op_13_ncell_3d\n"
        "      REAL(KIND=r_def), intent(in), dimension(ndf_adspc1_op_13,"
        "ndf_adspc1_op_13,op_13_ncell_3d) :: op_13\n"
        "    END SUBROUTINE dummy_code\n"
        "  END MODULE dummy_mod")
    assert output in generated_code


OPERATOR_DIFFERENT_SPACES = '''
module dummy_mod
  type, extends(kernel_type) :: dummy_type
     type(arg_type), meta_args(1) =                  &
          (/ arg_type(gh_operator, gh_write, w0, w1) &
           /)
     integer :: iterates_over = cells
   contains
     procedure, nopass :: code => dummy_code
  end type dummy_type
contains
  subroutine dummy_code()
  end subroutine dummy_code
end module dummy_mod
'''


def test_stub_operator_different_spaces():
    ''' Test that the correct function spaces are provided in the
    correct order when generating a kernel stub with an operator on
    different spaces.

    '''
    # Check the original code (to- and from- spaces both continuous)
    ast = fpapi.parse(OPERATOR_DIFFERENT_SPACES, ignore_comments=False)
    metadata = DynKernMetadata(ast)
    kernel = DynKern()
    kernel.load_meta(metadata)
    result = str(kernel.gen_stub)
    assert "(cell, nlayers, op_1_ncell_3d, op_1, ndf_w0, ndf_w1)" in result
    assert "dimension(ndf_w0,ndf_w1,op_1_ncell_3d)" in result
    # Check for discontinuous to- and from- spaces
    code = OPERATOR_DIFFERENT_SPACES.replace(
        "(gh_operator, gh_write, w0, w1)",
        "(gh_operator, gh_write, w3, any_discontinuous_space_2)", 1)
    ast = fpapi.parse(code, ignore_comments=False)
    metadata = DynKernMetadata(ast)
    kernel = DynKern()
    kernel.load_meta(metadata)
    result = str(kernel.gen_stub)
    assert ("(cell, nlayers, op_1_ncell_3d, op_1, ndf_w3, ndf_adspc2_op_1)"
            in result)
    assert "dimension(ndf_w3,ndf_adspc2_op_1,op_1_ncell_3d)" in result
    field_descriptor = metadata.arg_descriptors[0]
    result = str(field_descriptor)
    assert "function_space_to[3]='w3'" in result
    assert "function_space_from[4]='any_discontinuous_space_2'" in result
