# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2021, Science and Technology Facilities Council
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
# Modified by S. Siso, STFC Daresbury Lab

'''Module containing tests for the LFRicAlgorithmInvokeCall,
LFRicBuiltinFunctor and LFRicKernelFunctor LFRic
algorithm-layer-specific nodes. The tests include translation of PSyIR
to LFRic Algorithm PSyIR and from LFRic Algorithm PSyIR to processed
PSyIR.

'''
from __future__ import absolute_import
import pytest

from fparser.two.parser import ParserFactory
from fparser.common.readfortran import FortranStringReader

from psyclone.psyir.frontend.fparser2 import Fparser2Reader
from psyclone.psyir.frontend.fortran import FortranReader
from psyclone.psyir.nodes import Node, Reference
from psyclone.psyir.symbols import RoutineSymbol, TypeSymbol, \
    StructureType, REAL_TYPE
from psyclone.domain.lfric.algorithm import \
    LFRicAlgorithmInvokeCall, LFRicKernelFunctor, \
    LFRicBuiltinFunctor
from psyclone.domain.lfric.transformations import LFRicAlgTrans
from psyclone.errors import GenerationError


def create_alg_psyir(code):
    '''Utility to create an LFRic Algorithm PSyIR tree from Fortran
    code.

    :param str code: Fortran algorithm code encoded as a string.

    :returns: LFRic Algorithm PSyIR tree representing the Fortran \
        code.
    :rtype: :py:class:`psyclone.psyir.nodes.Node`

    '''
    fortran_reader = FortranReader()
    psyir = fortran_reader.psyir_from_source(code)
    alg_trans = LFRicAlgTrans()
    alg_trans.apply(psyir)

    return psyir


def test_lfricalgorithminvokecall():
    '''Check that an instance of LFRicAlgorithmInvokeCall can be
    created.

    '''
    routine = RoutineSymbol("hello")
    index = 2
    call = LFRicAlgorithmInvokeCall(routine, index)
    assert call.routine is routine
    assert call._index == index
    assert (call._children_valid_format ==
            "[LFRicKernelFunctor|LFRicBuiltinFunctor]*")
    assert call._text_name == "LFRicAlgorithmInvokeCall"


def test_validate_child():
    '''Check that the _validate_child method behaves as expected.'''

    lfric_kernel_functor = LFRicKernelFunctor(TypeSymbol("dummy1", REAL_TYPE))
    lfric_builtin_functor = LFRicBuiltinFunctor(
        TypeSymbol("dummy2", REAL_TYPE))
    assert LFRicAlgorithmInvokeCall._validate_child(0, lfric_kernel_functor)
    assert LFRicAlgorithmInvokeCall._validate_child(1, lfric_builtin_functor)
    assert not LFRicAlgorithmInvokeCall._validate_child(0, "Invalid")


def test_lfricalgorithminvoke_call_root_name():
    '''Check that an LFRicAlgorithmInvokeCall node is translated into the
    expected PSyIR call node when the lower_to_language_level() method
    is called. This test exercises the _def_routine_root_name(). The
    rest of the functionality is in the parent class.

    '''
    code = (
        "subroutine alg1()\n"
        "  use kern_mod, only : kern\n"
        "  use field_mod, only : field_type\n"
        "  type(field_type) :: field1\n"
        "  call invoke(kern(field1))\n"
        "  call invoke(kern(field1), name=\"test 1\")\n"
        "end subroutine alg1\n")

    psyir = create_alg_psyir(code)

    assert len(psyir.walk(LFRicAlgorithmInvokeCall)) == 2
    assert len(psyir.walk(LFRicKernelFunctor)) == 2

    psyir.lower_to_language_level()

    assert len(psyir.walk(LFRicAlgorithmInvokeCall)) == 0
    assert len(psyir.walk(LFRicKernelFunctor)) == 0
    call0 = psyir.children[0][0]
    assert call0.routine.name == "invoke_0_kern"
    assert call0.routine.is_global
    assert call0.routine.interface.container_symbol.name == "invoke_0_kern_mod"
    args = call0.children
    assert len(args) == 1
    assert isinstance(args[0], Reference)
    assert args[0].symbol.name == "field1"
    call1 = psyir.children[0][1]
    assert call1.routine.name == "test_1"
    assert call1.routine.is_global
    assert call1.routine.interface.container_symbol.name == "test_1_mod"
    args = call1.children
    assert len(args) == 1
    assert isinstance(args[0], Reference)
    assert args[0].symbol.name == "field1"


def test_lfricalgorithminvokecall_node_str():
    '''Check that the LFRicAlgorithmInvokeCall node_str  method creates the
    expected object.

    '''
    routine = RoutineSymbol("hello")
    call = LFRicAlgorithmInvokeCall(routine, 0)
    with pytest.raises(GenerationError) as info:
        call.children = ["invalid"]
    assert ("Item 'str' can't be child 0 of 'LFRicAlgorithmInvokeCall'. The "
            "valid format is: '[LFRicKernelFunctor|LFRicBuiltinFunctor]*'."
            in str(info.value))
    call.children = [lfric_kernel_functor, lfric_builtin_functor]


def test_lfricbuiltinfunctor():
    '''test that an instance of LFRicBuiltinFunctor class can be created.

    '''
    routine = TypeSymbol("hello", StructureType())
    lbc = LFRicBuiltinFunctor(routine)
    assert isinstance(lbc, LFRicBuiltinFunctor)
    assert lbc._text_name == "LFRicBuiltinFunctor"


def test_lfrickernelfunctor():
    '''test that an instance of LFRicKernelFunctor class can be created.

    '''
    routine = TypeSymbol("hello", StructureType())
    lbc = LFRicKernelFunctor(routine)
    assert isinstance(lbc, LFRicKernelFunctor)
    assert lbc._text_name == "LFRicKernelFunctor"
