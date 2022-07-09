# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2022, Science and Technology Facilities Council.
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
# Author R. W. Ford STFC Daresbury Lab

'''Raise generic PSyIR representing a kernel-layer routine to
PSyclone kernel-layer-specific PSyIR which uses specialised classes.

'''
from psyclone.domain.gocean.kernel import GOceanKernelMetadata, GOceanContainer
from psyclone.psyGen import Transformation
from psyclone.psyir.nodes import Container, ScopingNode, FileContainer
from psyclone.psyir.transformations import TransformationError


class KernTrans(Transformation):
    '''Raise a generic PSyIR representation of a kernel-layer routine
    to a PSyclone version with specialised domain-specific nodes and
    symbols. This is currently limited to the specialisation of kernel
    metadata.

    '''
    def __init__(self):
        super().__init__()
        self._metadata_name = None

    def validate(self, node, options=None):
        '''Validate the supplied PSyIR tree.

        :param node: a PSyIR node that is the root of a PSyIR tree.
        :type node: Union[:py:class:`psyclone.psyir.node.Routine`, \
            :py:class:`psyclone.psyir.node.Container`]
        :param options: a dictionary with options for transformations.
        :type options: Optional[Dict[str: str]]

        :raises TransformationError: if the metadata name has not been \
            set or does not exist in the code.
        :raises TransformationError: if the supplied node argument is \
            not a Routine or a Container.
        :raises TransformationError: if the supplied node argument has \
            a parent.

        '''
        if not isinstance(node, Container):
            raise TransformationError(
                f"Error in {self.name} transformation. The supplied call "
                f"argument should be a Container node but found "
                f"'{type(node).__name__}'.")

        if node.parent:
            raise TransformationError(
                f"Error in {self.name} transformation. The supplied node "
                f"should be the root of a PSyIR tree but this node has a "
                f"parent.")

        if not self._metadata_name:
            raise TransformationError(
                f"Error in {self.name} transformation. The kern_trans "
                f"transformation requires the metadata name to "
                f"be set before applying the transformation.")

        metadata_symbol = None
        scoping_node = None
        for test_node in node.walk(ScopingNode):
            try:
                metadata_symbol = test_node.symbol_table.lookup(
                    self._metadata_name)
                scoping_node = test_node
                break
            except KeyError:
                pass
        else:
            raise TransformationError(
                f"Error in {self.name} transformation. The metadata name "
                f"({self._metadata_name}) provided to the transformation "
                f"does not correspond to a symbol in the supplied PSyIR.")

        # Check that scoping node is a container or has an ancestor
        # that is a container.
        container = scoping_node
        if not isinstance(container, Container):
            container = scoping_node.ancestor(Container)
        if not container:
            raise TransformationError(
                f"Error in {self.name} transformation. The metadata symbol "
                f"should reside within a Container but none was found.")
        if isinstance(container, FileContainer):
            raise TransformationError(
                f"Error in {self.name} transformation. The Container in "
                f"which the metadata symbol resides is a FileContainer, "
                f"but should be a generic Container")

        # Check that the metadata can be generated without any errors.
        _ = GOceanKernelMetadata.create_from_psyir(metadata_symbol)

    @property
    def metadata_name(self):
        '''
        :returns: the name of the metadata that determines what will be \
            specialised to kernel-specific PSyIR.
        :rtype: str

        '''
        return self._metadata_name

    @metadata_name.setter
    def metadata_name(self, value):
        '''
        :param str value: sets the name of the metadata that \
            determines what will be specialised to kernel-specific PSyIR.
        '''
        if not isinstance(value, str):
            raise TypeError(
                f"Error in {self.name} transformation. The kern_trans "
                f"transformation requires the metadata name to be a string, "
                f"but found '{type(value).__name__}'.")

        self._metadata_name = value

    def apply(self, node, options=None):
        ''' Apply transformation to the supplied PSyIR.

        :param node: a kernel represented in generic PSyIR.
        :type node: Union[:py:class:`psyclone.psyir.node.Routine`, \
            :py:class:`psyclone.psyir.node.Container`]
        :param options: a dictionary with options for transformations.
        :type options: Optional[Dict[str: str]]

        '''

        self.validate(node, options=options)

        # Find the metadata symbol based on the supplied name.
        metadata_symbol = None
        scoping_node = None
        for test_node in node.walk(ScopingNode):
            try:
                metadata_symbol = test_node.symbol_table.lookup(
                    self._metadata_name)
                scoping_node = test_node
                break
            except KeyError:
                pass

        # Find the container in which this metadata resides.
        container = scoping_node
        if not isinstance(container, Container):
            container = scoping_node.ancestor(Container)

        # Create metadata
        metadata = GOceanKernelMetadata.create_from_psyir(metadata_symbol)

        # Remove metadata symbol.
        symbol_table = scoping_node.symbol_table
        norm_name = symbol_table._normalize(metadata_symbol.name)
        symbol_table._symbols.pop(norm_name)

        # Replace container
        children = container.pop_all_children()
        gocean_container = GOceanContainer.create(
            container.name, metadata, container.symbol_table.detach(),
            children)
        container.replace_with(gocean_container)


__all__ = ['KernTrans']
