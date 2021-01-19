# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2021, Science and Technology Facilities Council.
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
# Author S. Siso, STFC Daresbury Lab

'''This module contains the GOMoveIterationBoundariesInsideKernelTrans.'''

from psyclone.psyir.transformations import TransformationError
from psyclone.psyGen import Transformation, InvokeSchedule, CodedKern
from psyclone.psyir.nodes import (BinaryOperation, Reference,
                                  Assignment, IfBlock, Return)
from psyclone.psyir.symbols import (INTEGER_TYPE, ArgumentInterface,
                                    DataSymbol)


class GOMoveIterationBoundariesInsideKernelTrans(Transformation):
    ''' Provides a ... '''
    def __str__(self):
        return "description"

    @property
    def name(self):
        '''Returns the name of this transformation as a string.'''
        return "FuseKern"

    def validate(self, kernel):
        '''Checks ...

        :raises TransformationError: if ....
         '''

        if not isinstance(kernel, CodedKern):
            raise TransformationError("Not CodedKerns")

    def apply(self, kernel):
        self.validate(kernel)

        # Update Kernel Call
        invoke_st = kernel.ancestor(InvokeSchedule).symbol_table
        inner_loop = kernel.parent.parent
        outer_loop = inner_loop.parent.parent
        cursor = outer_loop.position

        # Find names available for the boundary variables
        xstart_name = invoke_st.new_symbol_name("xstart")
        xstop_name = invoke_st.new_symbol_name("xstop")
        ystart_name = invoke_st.new_symbol_name("ystart")
        ystop_name = invoke_st.new_symbol_name("ystop")

        # Create new symbols and initialise them with
        xstart_symbol = DataSymbol(xstart_name, INTEGER_TYPE)
        xstop_symbol = DataSymbol(xstop_name, INTEGER_TYPE)
        ystart_symbol = DataSymbol(ystart_name, INTEGER_TYPE)
        ystop_symbol = DataSymbol(ystop_name, INTEGER_TYPE)
        invoke_st.add(xstart_symbol)
        invoke_st.add(xstop_symbol)
        invoke_st.add(ystart_symbol)
        invoke_st.add(ystop_symbol)
        arguments = kernel.arguments.raw_arg_list()
        arguments.extend([xstart_name, xstop_name, ystart_name, ystop_name])

        assign1 = Assignment.create(Reference(xstart_symbol),
                                    inner_loop._lower_bound())
        outer_loop.parent.children.insert(cursor, assign1)
        cursor = cursor + 1
        assign2 = Assignment.create(Reference(xstop_symbol),
                                    inner_loop._upper_bound())
        outer_loop.parent.children.insert(cursor, assign2)
        cursor = cursor + 1
        assign3 = Assignment.create(Reference(ystart_symbol),
                                    outer_loop._lower_bound())
        outer_loop.parent.children.insert(cursor, assign3)
        cursor = cursor + 1
        assign4 = Assignment.create(Reference(ystop_symbol),
                                    outer_loop._upper_bound())
        outer_loop.parent.children.insert(cursor, assign4)

        # Now that the boundaries are inside the kernel, the looping should go
        # trough all the field points
        inner_loop.field_space = "go_every"
        outer_loop.field_space = "go_every"
        inner_loop.iteration_space = "go_all_pts"
        outer_loop.iteration_space = "go_all_pts"

        # Update Kernel
        kschedule = kernel.get_kernel_schedule()
        kernel_st = kschedule.symbol_table
        iteration_indices = kernel_st.iteration_indices
        data_arguments = kernel_st.data_arguments

        # Find names available for the boundary variables
        xstart_name = kernel_st.new_symbol_name("xstart")
        xstop_name = kernel_st.new_symbol_name("xstop")
        ystart_name = kernel_st.new_symbol_name("ystart")
        ystop_name = kernel_st.new_symbol_name("ystop")

        # Create new symbols and insert them as kernel arguments after
        # the initial iteration indices
        xstart_symbol = DataSymbol(xstart_name, INTEGER_TYPE,
                                   interface=ArgumentInterface(
                                       ArgumentInterface.Access.READ))
        xstop_symbol = DataSymbol(xstop_name, INTEGER_TYPE,
                                  interface=ArgumentInterface(
                                      ArgumentInterface.Access.READ))
        ystart_symbol = DataSymbol(ystart_name, INTEGER_TYPE,
                                   interface=ArgumentInterface(
                                       ArgumentInterface.Access.READ))
        ystop_symbol = DataSymbol(ystop_name, INTEGER_TYPE,
                                  interface=ArgumentInterface(
                                      ArgumentInterface.Access.READ))
        kernel_st.add(xstart_symbol)
        kernel_st.add(xstop_symbol)
        kernel_st.add(ystart_symbol)
        kernel_st.add(ystop_symbol)
        kernel_st.specify_argument_list(
            iteration_indices +
            [xstart_symbol, xstop_symbol, ystart_symbol, ystop_symbol] +
            data_arguments)

        # Create boundaries masking condition
        condition1 = BinaryOperation.create(
            BinaryOperation.Operator.LT,
            Reference(iteration_indices[0]),
            Reference(xstart_symbol))
        condition2 = BinaryOperation.create(
            BinaryOperation.Operator.GT,
            Reference(iteration_indices[0]),
            Reference(xstop_symbol))
        condition3 = BinaryOperation.create(
            BinaryOperation.Operator.LT,
            Reference(iteration_indices[1]),
            Reference(ystart_symbol))
        condition4 = BinaryOperation.create(
            BinaryOperation.Operator.GT,
            Reference(iteration_indices[1]),
            Reference(ystop_symbol))

        condition = BinaryOperation.create(
            BinaryOperation.Operator.OR,
            BinaryOperation.create(
                BinaryOperation.Operator.OR,
                condition1,
                condition2),
            BinaryOperation.create(
                BinaryOperation.Operator.OR,
                condition3,
                condition4)
            )

        # Insert if condition masking as the kernel first statement
        if_statement = IfBlock.create(condition, [Return()])
        kschedule.children.insert(0, if_statement)
        if_statement.parent = kschedule
