# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2017-2020, Science and Technology Facilities Council.
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
# Authors R. W. Ford, A. R. Porter and S. Siso, STFC Daresbury Lab
#         I. Kavcic, Met Office
#         J. Henrichs, Bureau of Meteorology
# -----------------------------------------------------------------------------

''' This module contains the implementation of the Reference and Array
nodes.'''

from __future__ import absolute_import
from psyclone.psyir.nodes.datanode import DataNode
from psyclone.psyir.nodes.node import Node
from psyclone.psyir.nodes.ranges import Range
from psyclone.core.access_info import AccessType
from psyclone.psyir.symbols import Symbol
from psyclone.errors import GenerationError


class Reference(DataNode):
    '''
    Node representing a Reference Expression.

    :param symbol: the symbol being referenced.
    :type symbol: :py:class:`psyclone.psyir.symbols.Symbol`
    :param parent: the parent node of this Reference in the PSyIR.
    :type parent: :py:class:`psyclone.psyir.nodes.Node` or NoneType

    :raises TypeError: if the symbol argument is not of type Symbol.

    '''
    # Textual representation of the valid children for this node.
    _children_valid_format = "<LeafNode>"

    def __init__(self, symbol, parent=None):
        if not isinstance(symbol, Symbol):
            raise TypeError("In Reference initialisation expecting a symbol "
                            "but found '{0}'.".format(type(symbol).__name__))
        super(Reference, self).__init__(parent=parent)
        self._symbol = symbol

    @staticmethod
    def _validate_child(position, child):
        '''
        :param int position: a position to be validated.
        :param child: a child to be validated.
        :type child: :py:class:`psyclone.psyir.nodes.node`

        :return: whether the given child and position are valid for this node.
        :rtype: bool

        '''
        # pylint: disable=unused-argument
        return False

    @property
    def symbol(self):
        ''' Return the referenced symbol.

        :returns: the referenced symbol.
        :rtype: :py:class:`psyclone.psyir.symbols.Symbol`

        '''
        return self._symbol

    @property
    def name(self):
        ''' Return the name of the referenced symbol.

        :returns: Name of the referenced symbol.
        :rtype: str

        '''
        return self._symbol.name

    def node_str(self, colour=True):
        ''' Create a text description of this node in the schedule, optionally
        including control codes for colour.

        :param bool colour: whether or not to include colour control codes.

        :return: text description of this node.
        :rtype: str
        '''
        return self.coloured_name(colour) + "[name:'" + self.name + "']"

    def __str__(self):
        return self.node_str(False)

    def math_equal(self, other):
        ''':param other: the node to compare self with.
        :type other: py:class:`psyclone.psyir.nodes.Node`

        :returns: True if the self has the same results as other.
        :rtype: bool
        '''
        if not super(Reference, self).math_equal(other):
            return False
        return self.name == other.name

    def reference_accesses(self, var_accesses):
        '''Get all variable access information from this node, i.e.
        it sets this variable to be read.

        :param var_accesses: VariablesAccessInfo instance that stores the \
            information about variable accesses.
        :type var_accesses: \
            :py:class:`psyclone.core.access_info.VariablesAccessInfo`
        '''
        var_accesses.add_access(self.name, AccessType.READ, self)


class Array(Reference):
    '''
    Node representing an Array reference. As such it has a reference and a
    subscript list as children 0 and 1, respectively.

    :param str reference_name: name of the array symbol.
    :param parent: the parent node of this Array in the PSyIR.
    :type parent: :py:class:`psyclone.psyir.nodes.Node`

    '''
    # Textual representation of the valid children for this node.
    _children_valid_format = "*[DataNode | Range]"

    def __init__(self, symbol, parent=None):
        super(Array, self).__init__(symbol, parent=parent)
        self._text_name = "ArrayReference"
        self._colour_key = "Reference"

    @staticmethod
    def _validate_child(position, child):
        '''
        :param int position: a position to be validated.
        :param child: a child to be validated.
        :type child: :py:class:`psyclone.psyir.nodes.node`

        :return: whether the given child and position are valid for this node.
        :rtype: bool

        '''
        # pylint: disable=unused-argument
        return isinstance(child, (DataNode, Range))

    @staticmethod
    def create(symbol, children):
        '''Create an Array instance given a symbol and a list of Node
        array indices.

        :param symbol: the symbol that this array is associated with.
        :type symbol: :py:class:`psyclone.psyir.symbols.DataSymbol`
        :param children: a list of Nodes describing the array indices.
        :type children: list of :py:class:`psyclone.psyir.nodes.Node`

        :returns: an Array instance.
        :rtype: :py:class:`psyclone.psyir.nodes.Array`

        :raises GenerationError: if the arguments to the create method \
            are not of the expected type.

        '''
        from psyclone.psyir.symbols import DataSymbol
        if not isinstance(symbol, DataSymbol):
            raise GenerationError(
                "symbol argument in create method of Array class should be a "
                "DataSymbol but found '{0}'.".format(type(symbol).__name__))
        if not isinstance(children, list):
            raise GenerationError(
                "children argument in create method of Array class "
                "should be a list but found '{0}'."
                "".format(type(children).__name__))
        for child in children:
            if not isinstance(child, Node):
                raise GenerationError(
                    "child of children argument in create method of "
                    "Array class should be a PSyIR Node but found '{0}'."
                    "".format(type(child).__name__))
        if not symbol.is_array:
            raise GenerationError(
                "expecting the symbol to be an array, not a scalar.")
        if len(symbol.shape) != len(children):
            raise GenerationError(
                "the symbol should have the same number of dimensions as "
                "indices (provided in the 'children' argument). "
                "Expecting '{0}' but found '{1}'.".format(
                    len(children), len(symbol.shape)))

        array = Array(symbol)
        for child in children:
            child.parent = array
        array.children = children
        return array

    def __str__(self):
        result = "Array" + super(Array, self).__str__() + "\n"
        for entity in self._children:
            result += str(entity) + "\n"
        return result

    def reference_accesses(self, var_accesses):
        '''Get all variable access information. All variables used as indices
        in the access of the array will be added as READ.

        :param var_accesses: variable access information.
        :type var_accesses: \
            :py:class:`psyclone.core.access_info.VariablesAccessInfo`
        '''

        # This will set the array-name as READ
        super(Array, self).reference_accesses(var_accesses)

        # Now add all children: Note that the class Reference
        # does not recurse to the children (which store the indices), so at
        # this stage no index information has been stored:
        list_indices = []
        for child in self._children:
            child.reference_accesses(var_accesses)
            list_indices.append(child)

        if list_indices:
            var_info = var_accesses[self.name]
            # The last entry in all_accesses is the one added above
            # in super(Array...). Add the indices to that entry.
            var_info.all_accesses[-1].indices = list_indices
