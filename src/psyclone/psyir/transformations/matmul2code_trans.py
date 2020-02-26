# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2020, Science and Technology Facilities Council
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
# Author: R. W. Ford, STFC Daresbury Lab

'''Module providing a NEMO-API-specific transformation from a PSyIR
MATMUL operator to PSyIR code. This could be useful if the
MATMULoperator is not supported by the back-end or if the performance
in the inline code is better than the intrinsic. MATMUL supports both
matrix multiply and matrix vector multiply. At the moment this
transformation is limited to matrix vector multiply.

'''
from psyclone.undoredo import Memento
from psyclone.psyir.nodes import BinaryOperation, NaryOperation, Assignment, \
        Reference, IfBlock, Loop, Literal, Array
from psyclone.psyir.symbols import DataType, DataSymbol
from psyclone.psyGen import Transformation

class Matmul2CodeTrans(Transformation):
    '''Provides a transformation from a PSyIR MATMUL Operator node to
    equivalent code in a PSyIR tree. Validity checks are also
    performed. Currently only the vector LHS version of MATMUL is
    supported.

    If the dimensions of R, A, and B are R(M), A(M,L), B(L), 
    The transformation replaces `R=MATMUL(A,B)` with the following code:
    
    ```loop i=1,N
           loop j=1,M
             R(i) += A(i,j) * B(k)```

    '''
    def __str__(self):
        return ("Convert the PSyIR MATMUL intrinsic to equivalent PSyIR "
                "code.")

    @property
    def name(self):
        '''
        :returns: the name of the transformation as a string.
        :rtype:str

        '''
        return "Matmul2CodeTrans"

    def validate(self, node):
        '''Perform checks to ensure that it is valid to apply the
        Matmul2CodeTran transformation to the supplied node.

        :param node: the node that is being checked.
        :type node: :py:class:`psyclone.psyGen.Operation`

        :raises TransformationError: if the node argument is not the \
        expected type.
        :raises TransformationError: if the parent of the MATMUL \
        operation is not an assignment.
        :raises TransformationError: if the 2nd argument of the MATMUL \
        operation is an array that is not 1 dimensional.

        '''
        # Check the supplied argument is a matvec node
        if not isinstance(node, BinaryOperation):
            raise TransformationError(
                "The supplied node should be a MATMUL BinaryOperation but "
                "found '{0}'.".format(type(node).__name__))
        if node.operator != BinaryOperation.Operator.MATMUL:
            raise TransformationError(
                "The supplied node should be a MATMUL BinaryOperation but "
                "found '{0}'.".format(node.operator))
        # Check the matmul is the only code on the rhs of an assignment
        # i.e. ... = matvec(a,b)
        if not isinstance(node.parent, Assignment):
            raise TransformationError(
                "Matmul2CodeTrans only supports the transformation of a "
                "MATMUL operation when it is the only operation on the rhs "
                "of an assignment.")
        # The dimension of the 2nd argument should be 1 as we only
        # support the matvec version of matmul.
        # This can't be properly tested until #688 is complete. For
        # the moment perform the check only if the child is an array.
        array = node.children[1]
        if isinstance(array, Array) and not len(array.children) == 1:
            raise TransformationError(
                "Matmul2CodeTrans only supports the matrix vector form of "
                "matmul which requires the 2nd argument to be a "
                "one-dimensional array, but found {0} dimensions."
                "".format(len(array.children)))

    def apply(self, node, options=None):
        '''Apply the MATMUL intrinsic conversion transformation to the
        specified node. This node must be a MATMUL
        BinaryOperation. Currently only the vector LHS version of
        MATMUL is supported.  BinaryOperation is converted to the
        following equivalent inline code:

        R=MATMUL(A,B)
        to:

        ```loop i=1,N
             R(i) = 0.0
             loop j=1,M
               R(i) = R(i) + A(i,j) * B(k)```

        :param node: a MATMUL Binary-Operation node.
        :type node: :py:class:`psyclone.psyGen.BinaryOperation`
        :param options: a dictionary with options for transformations.
        :type options: dictionary of string:values or None

        '''
        self.validate(node)

        assignment = node.parent

        matrix = node.children[0]
        matrix_symbol = matrix.symbol
        # TODO: does this assume the bound is a symbol????
        matrix_bound = matrix_symbol.shape[0]
        # TODO: Check shape[1] should be the same as vector_bound?

        vector = node.children[1]
        vector_symbol=vector.symbol
        # TODO: does this assume the bound is a symbol????
        vector_bound = vector_symbol.shape[0]

        result_symbol = node.parent.lhs.symbol

        # TODO: Find nearest ancestor symbol table (is there an issue for this?)
        current = node
        while current and not hasattr(current, "symbol_table"):
            current=current.parent
        symbol_table = current.symbol_table

        i_loop_name = symbol_table.new_symbol_name("i")
        i_loop_symbol = DataSymbol(i_loop_name, DataType.INTEGER)
        symbol_table.add(i_loop_symbol)
        j_loop_name = symbol_table.new_symbol_name("j")
        j_loop_symbol = DataSymbol(j_loop_name, DataType.INTEGER)
        symbol_table.add(j_loop_symbol)

        result = Array.create(result_symbol, [Reference(i_loop_symbol)])
        vector_array_reference = Array.create(
            vector.symbol, [Reference(j_loop_symbol)])
        # TODO: Third dimension is a hack as we don't yet support ":"
        # so the first 2 dims are in a code block. So it should be
        # children[2]!!
        matrix_array_reference = Array.create(
            matrix.symbol, [Reference(i_loop_symbol), Reference(j_loop_symbol),
            matrix.children[1]])
        multiply = BinaryOperation.create(
            BinaryOperation.Operator.MUL, matrix_array_reference,
            vector_array_reference)
        rhs = BinaryOperation.create(
            BinaryOperation.Operator.ADD, result, multiply)
        assign = Assignment.create(result, rhs)
        jloop = Loop.create(
            j_loop_name, Literal("1", DataType.INTEGER),
            Reference(vector_bound), Literal("1", DataType.INTEGER), [assign])
        assign = Assignment.create(result, Literal("0.0", DataType.REAL))
        iloop = Loop.create(
            i_loop_name, Literal("1", DataType.INTEGER),
            Reference(matrix_bound), Literal("1", DataType.INTEGER),
            [assign, jloop])
        iloop.parent = assignment.parent
        assignment.parent.children.insert(assignment.position, iloop)
        # remove original matmul
        assignment.parent.children.remove(assignment)
