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
# Authors: A. R. Porter, R. W. Ford and A. Chalk, STFC Daresbury Lab

'''
This module contains the InlineTrans transformation.

'''

from psyclone.errors import InternalError, LazyString
from psyclone.psyGen import Transformation
from psyclone.psyir.backend.fortran import FortranWriter
from psyclone.psyir.nodes import (
    ArrayReference, ArrayOfStructuresReference, Call, Range, Routine,
    Reference, CodeBlock, Return, Literal, Assignment,
    StructureReference)
from psyclone.psyir.nodes.array_mixin import ArrayMixin
from psyclone.psyir.symbols import (ContainerSymbol, DataSymbol, ScalarType,
                                    RoutineSymbol, ImportInterface)
from psyclone.psyir.transformations.transformation_error import (
    TransformationError)


class InlineTrans(Transformation):
    '''
    This transformation takes a Call (which may have a return value)
    and replaces it with the body of the target routine. It is used as
    follows:

    >>> from psyclone.psyir.backend.fortran import FortranWriter
    >>> from psyclone.psyir.frontend.fortran import FortranReader
    >>> from psyclone.psyir.nodes import Call, Routine
    >>> from psyclone.psyir.transformations import InlineTrans
    >>> code = """
    ... module test_mod
    ... contains
    ...   subroutine run_it()
    ...     integer :: i
    ...     real :: a(10)
    ...     do i=1,10
    ...       a(i) = 1.0
    ...       call sub(a(i))
    ...     end do
    ...   end subroutine run_it
    ...   subroutine sub(x)
    ...     real, intent(inout) :: x
    ...     x = 2.0*x
    ...   end subroutine sub
    ... end module test_mod"""
    >>> psyir = FortranReader().psyir_from_source(code)
    >>> call = psyir.walk(Call)[0]
    >>> inline_trans = InlineTrans()
    >>> inline_trans.apply(call)
    >>> # Uncomment the following line to see a text view of the schedule
    >>> # print(psyir.walk(Routine)[0].view())
    >>> print(FortranWriter()(psyir.walk(Routine)[0]))
    subroutine run_it()
      integer :: i
      real, dimension(10) :: a
    <BLANKLINE>
      do i = 1, 10, 1
        a(i) = 1.0
        a(i) = 2.0 * a(i)
      enddo
    <BLANKLINE>
    end subroutine run_it
    <BLANKLINE>

    .. warning::
        Routines/calls with any of the following characteristics are not
        supported and will result in a TransformationError:

        * the routine is not in the same file as the call;
        * the routine contains an early Return statement;
        * the routine has a named argument;
        * the call to the routine passes array subsections;
        * the shape of any array arguments as declared inside the routine does
          not match the shape of the arrays being passed as arguments;
        * the routine accesses an un-resolved symbol;
        * the routine accesses a symbol declared in the Container to which it
          belongs.

        Some of these restrictions will be lifted by #924.

    '''
    def apply(self, node, options=None):
        '''
        Takes the body of the routine that is the target of the supplied
        call and replaces the call with it.

        :param node: target PSyIR node.
        :type node: :py:class:`psyclone.psyir.nodes.Routine`
        :param options: a dictionary with options for transformations.
        :type options: Optional[Dict[str, Any]]

        '''
        self.validate(node, options)

        # The table we will copy symbols into.
        table = node.scope.symbol_table
        # Find the routine to be inlined.
        orig_routine = self._find_routine(node)

        if not orig_routine.children or isinstance(orig_routine.children[0],
                                                   Return):
            # Called routine is empty so just remove the call.
            node.detach()
            return

        # Ensure we don't modify the original Routine by working with a
        # copy of it.
        routine = orig_routine.copy()
        routine_table = routine.symbol_table

        # Construct lists of the nodes that will be inserted and all of the
        # References that they contain.
        new_stmts = []
        refs = []
        # Map from name of precision symbol to those Literals that use it.
        precision_map = {}
        for child in routine.children:
            new_stmts.append(child.copy())
            refs.extend(new_stmts[-1].walk(Reference))
            for lit in new_stmts[-1].walk(Literal):
                if isinstance(lit.datatype.precision, DataSymbol):
                    name = lit.datatype.precision.name
                    if name not in precision_map:
                        precision_map[name] = []
                    precision_map[name].append(lit)

        # Deal with any Container symbols first.
        self._inline_container_symbols(table, routine_table)

        # Copy each Symbol from the Routine into the symbol table associated
        # with the call site, excluding those that represent dummy arguments
        # or containers.
        self._inline_symbols(table, routine_table, precision_map)

        # Replace any references to dummy arguments with copies of the
        # actual arguments.
        dummy_args = routine_table.argument_list
        for ref in refs:
            # Check the parent is not None as some references are replaced
            # during previous calls if they are array accesses
            if ref.parent is not None:
                self.replace_dummy_arg(ref, node, dummy_args)

        # Copy the nodes from the Routine into the call site.
        if isinstance(new_stmts[-1], Return):
            # If the final statement of the routine is a return then
            # remove it from the list.
            del new_stmts[-1]

        if routine.return_symbol:
            # This is a function
            assignment = node.ancestor(Assignment)
            parent = assignment.parent
            idx = assignment.position-1
            for child in new_stmts:
                idx += 1
                parent.addchild(child, idx)
            table = parent.scope.symbol_table
            # Avoid a potential name clash with the original function
            table.rename_symbol(
                routine.return_symbol, table.next_available_name(
                    f"inlined_{routine.return_symbol.name}"))
            node.replace_with(Reference(routine.return_symbol))
        else:
            # This is a call
            parent = node.parent
            idx = node.position
            node.replace_with(new_stmts[0])
            for child in new_stmts[1:]:
                idx += 1
                parent.addchild(child, idx)

    def replace_dummy_arg(self, ref, call_node, dummy_args):
        '''
        Combines a Reference to a dummy argument with the corresponding
        Reference from the call site to make a new Reference for use in the
        inlined code. If the supplied Reference is not to a dummy argument
        then it is returned unchanged.

        :param ref: the reference to update.
        :type ref: :py:class:`psyclone.psyir.nodes.Reference`
        :param call_node: the call site.
        :type call_node: :py:class:`psyclone.psyir.nodes.Call`
        :param dummy_args: the dummy arguments of the called routine.
        :type dummy_args: List[:py:class:`psyclone.psyir.nodes.Reference`]

        :returns: the replacement reference.
        :rtype: :py:class:`psyclone.psyir.nodes.Reference`

        :raises InternalError: if the actual and dummy references both \
                               represent array-element accessors.
        '''
        if ref.symbol not in dummy_args:
            # The supplied reference is not to a dummy argument.
            return ref

        actual_arg = call_node.children[dummy_args.index(ref.symbol)]

        # If the local reference is a simple Reference then we can just
        # replace it with the actual argument.
        # pylint: disable=unidiomatic-typecheck
        if type(ref) is Reference:
            # call my_sub(my_struc%data(i,j))
            #
            # subroutine my_sub(var)
            #   ...
            #   var = 0.0
            ref.replace_with(actual_arg.copy())
            return ref

        # Local reference is not simple but the actual argument is, e.g.:
        #
        # call my_sub(my_struc)
        #
        # subroutine my_sub(var)
        #   ...
        #   var%data(i,j) = 0.0
        if type(actual_arg) is Reference:
            ref.symbol = actual_arg.symbol
            return ref

        # Neither the actual or local references are simple, e.g.:
        #
        # call my_sub(my_struc%grid(:,2,:), 10)
        #
        # subroutine my_sub(grid, ngrids)
        #   ...
        #   do igrid = 1, ngrids
        #     do jgrid = ...
        #     do i = 1, 10
        #       do j = 1, 10
        #         grid(igrid, jgrid)%data(i,j) = 0.0
        #
        # The assignment in the inlined code should become:
        #
        #         my_struc%grid(igrid,2,jgrid)%data(i,j) = 0.0

        # So, the head of the local reference needs to be replaced by the
        # head of the actual reference (e.g. grid => my_struc%grid) and then
        # any ranges in the actual reference need to be replaced by the
        # corresponding index expressions in the local reference.

        top_indices = None
        local_indices = None
        if isinstance(actual_arg, ArrayMixin):
            top_indices = [idx.copy() for idx in actual_arg.indices]
        if isinstance(ref, ArrayMixin):
            local_indices = ref.indices

        members = []
        local_idx_posn = 0
        for cursor in (actual_arg, ref):
            while hasattr(cursor, "member"):
                cursor = cursor.member
                if hasattr(cursor, "indices"):
                    new_indices = []
                    for idx in cursor.indices:
                        # TODO - this handling of a Range is duplicated.
                        if isinstance(idx, Range):
                            new_idx = local_indices[local_idx_posn].copy()
                            new_indices.append(self.replace_dummy_arg(
                                new_idx, call_node, dummy_args))
                            local_idx_posn += 1
                        else:
                            new_indices.append(idx.copy())
                    members.append((cursor.name, new_indices))
                else:
                    members.append(cursor.name)

        if members:
            if top_indices:
                new_ref = ArrayOfStructuresReference.create(actual_arg.symbol,
                                                            top_indices,
                                                            members)
            else:
                new_ref = StructureReference.create(actual_arg.symbol,
                                                    members)
        else:
            # One or both must be just array accesses. This means that the
            # actual argument contains a slice. (The PSyIR does not explicitly
            # support pointers and in Fortran, an array of pointers to arrays
            # can only be achieved through having an array of structures.)
            local_idx_posn = 0
            ranges = call_node.walk(Range)
            if ranges:
                new_indices = []
                for idx in top_indices:
                    # TODO - this handling of a Range is duplicated.
                    if isinstance(idx, Range):
                        new_idx = local_indices[local_idx_posn].copy()
                        new_indices.append(self.replace_dummy_arg(
                            new_idx, call_node,
                            dummy_args))
                        local_idx_posn += 1
                    else:
                        new_indices.append(idx.copy())
            else:
                if top_indices and local_indices:
                    raise InternalError(
                        f"The reference to '{ref.symbol.name}' in the call to "
                        f"'{call_node.name}' is an array access but there is "
                        f"also an array access to the corresponding dummy "
                        f"argument in that routine. This should not be "
                        f"possible.")
                # The local index expressions must be inlined at the call site.
                new_indices = []
                for idx in new_indices:
                    new_indices.append(
                        self.replace_dummy_arg(idx, call_node, dummy_args))
                # Call-site index expressions can just be copied.
                for idx in top_indices:
                    new_indices.append(idx.copy())
            new_ref = ArrayReference.create(actual_arg.symbol, new_indices)
        ref.replace_with(new_ref)
        return new_ref

    @staticmethod
    def _inline_container_symbols(table, routine_table):
        '''
        Takes container symbols from the symbol table of the routine being
        inlined and adds them to the table of the call site. All references
        to each container symbol are also updated.

        :param table: the symbol table at the call site.
        :type table: :py:class:`psyclone.psyir.symbols.SymbolTable`
        :param routine_table: the symbol table of the routine being inlined.
        :type routine_table: :py:class:`psyclone.psyir.symbols.SymbolTable`

        '''
        for csym in routine_table.containersymbols:
            if csym.name in table:
                # We have a clash with another symbol at the call site.
                other_csym = table.lookup(csym.name)
                if not isinstance(other_csym, ContainerSymbol):
                    # The symbol at the call site is not a Container so we
                    # can rename it.
                    table.rename_symbol(
                            other_csym,
                            table.next_available_name(
                                csym.name, other_table=routine_table))
                    # We can then add an import from the Container.
                    table.add(csym)
                else:
                    # If there is a wildcard import from this container in the
                    # routine then we'll need that at the call site.
                    if csym.wildcard_import:
                        other_csym.wildcard_import = True
            else:
                table.add(csym)
            # We must update all references to this ContainerSymbol
            # so that they point to the one in the call site instead.
            imported_syms = routine_table.symbols_imported_from(csym)
            for isym in imported_syms:
                if isym.name in table:
                    # We have a potential clash with a symbol imported
                    # into the routine.
                    callsite_sym = table.lookup(isym.name)
                    if not callsite_sym.is_import:
                        # The validate() method has already checked that we
                        # don't have a clash between symbols of the same name
                        # imported from different containers.
                        # We don't support renaming an imported symbol but the
                        # symbol at the call site can be renamed so we do that.
                        table.rename_symbol(
                            callsite_sym,
                            table.next_available_name(
                                callsite_sym.name, other_table=routine_table))
                isym.interface = ImportInterface(table.lookup(csym.name))

    @staticmethod
    def _inline_symbols(table, routine_table, precision_map):
        '''
        Takes symbols from the symbol table of the routine and adds
        them to the table of the call site. Any literals that refer to
        precision symbols are updated to refer to the appropriate symbol in
        the table at the call site.

        :param table: the symbol table at the call site.
        :type table: :py:class:`psyclone.psyir.symbols.SymbolTable`
        :param routine_table: the symbol table of the routine being inlined.
        :type routine_table: :py:class:`psyclone.psyir.symbols.SymbolTable`
        :param precision_map: Lists of literals, indexed by the name of the \
            precision symbol that they use.
        :type precision_map: Dict[str, \
            List[:py:class:`psyclone.psyir.nodes.Literal`]]

        :raises InternalError: if an imported symbol is found that has not \
            been updated to refer to a Container at the call site.

        '''
        routine_name = routine_table.node.name
        dummy_args = routine_table.argument_list

        for old_sym in routine_table.symbols:

            if old_sym in dummy_args or isinstance(old_sym, ContainerSymbol):
                # We've dealt with Container symbols in
                # _inline_container_symbols() and we deal with dummy arguments
                # in apply().
                continue

            if old_sym.name == routine_name and isinstance(old_sym,
                                                           RoutineSymbol):
                # We don't want or need the symbol representing the routine
                # that is being inlined.
                continue

            old_name = old_sym.name
            try:
                table.add(old_sym)

            except KeyError:
                # We have a clash with a symbol at the call site.
                if old_sym.is_import:
                    # This symbol is imported from a Container so should
                    # already have been updated so as to be imported from the
                    # corresponding container in scope at the call site.
                    callsite_csym = table.lookup(
                        old_sym.interface.container_symbol.name)
                    if old_sym.interface.container_symbol is not callsite_csym:
                        # pylint: disable=raise-missing-from
                        raise InternalError(
                            f"Symbol '{old_sym.name}' imported from "
                            f"'{callsite_csym.name}' has not been updated to "
                            f"refer to that container at the call site.")
                else:
                    # A Symbol with the same name already exists so we rename
                    # the one that we are adding.
                    new_name = table.next_available_name(
                        old_sym.name, other_table=routine_table)
                    routine_table.rename_symbol(old_sym, new_name)
                    table.add(old_sym)

            # Check whether this symbol is used to specify the precision of
            # any literals.
            if old_name in precision_map:
                for lit in precision_map[old_name]:
                    # A literal is immutable so create a new one with the
                    # updated symbol as its precision.
                    dtype = ScalarType(lit.datatype.intrinsic, old_sym)
                    lit.replace_with(Literal(lit.value, dtype))

    def validate(self, node, options=None):
        '''
        Checks that the supplied node is a valid target for inlining.

        :param node: target PSyIR node.
        :type node: subclass of :py:class:`psyclone.psyir.nodes.Routine`
        :param options: a dictionary with options for transformations.
        :type options: Optional[Dict[str, Any]]

        :raises TransformationError: if the supplied node is not a Call.
        :raises TransformationError: if the routine has a return value.
        :raises TransformationError: if the routine body contains a Return \
            that is not the first or last statement.
        :raises TransformationError: if the routine body contains a CodeBlock.
        :raises TransformationError: if the called routine has a named \
            argument.
        :raises TransformationError: if a symbol of a given name is imported \
            from different containers at the call site and within the routine.
        :raises TransformationError: if the routine accesses an un-resolved \
            symbol.
        :raises TransformationError: if a symbol declared in the parent \
            container is accessed in the target routine.
        :raises TransformationError: if any of the actual arguments represent \
            an array subsection.
        :raises TransformationError: if the shape of an array dummy argument \
            does not match that of the corresponding actual argument.

        '''
        super().validate(node, options=options)

        # The node should be a Call.
        if not isinstance(node, Call):
            raise TransformationError(
                f"The target of the InlineTrans transformation "
                f"should be a Call but found '{type(node).__name__}'.")

        name = node.routine.name

        # Check that we can find the source of the routine being inlined.
        routine = self._find_routine(node)

        if not routine.children or isinstance(routine.children[0], Return):
            # An empty routine is fine.
            return

        return_stmts = routine.walk(Return)
        if return_stmts:
            if len(return_stmts) > 1 or not isinstance(routine.children[-1],
                                                       Return):
                # Either there is more than one Return statement or there is
                # just one but it isn't the last statement of the Routine.
                raise TransformationError(
                    f"Routine '{name}' contains one or more "
                    f"Return statements and therefore cannot be inlined.")

        if routine.walk(CodeBlock):
            raise TransformationError(
                f"Routine '{name}' contains one or more "
                f"CodeBlocks and therefore cannot be inlined.")

        # Support for routines with named arguments is not yet implemented.
        # TODO #924.
        for arg in node.argument_names:
            if arg:
                raise TransformationError(
                    f"Routine '{routine.name}' cannot be inlined because it "
                    f"has a named argument '{arg}' (TODO #924).")

        # Check for symbol-naming clashes that we can't handle.
        table = node.scope.symbol_table
        routine_table = routine.symbol_table

        # We can't handle a clash between (apparently) different symbols that
        # share a name but are imported from different containers.
        callsite_imports = table.imported_symbols
        routine_imports = routine_table.imported_symbols
        routine_import_names = [sym.name for sym in routine_imports]
        for sym in callsite_imports:
            if sym.name in routine_import_names:
                routine_sym = routine_table.lookup(sym.name)
                if (routine_sym.interface.container_symbol.name !=
                        sym.interface.container_symbol.name):
                    raise TransformationError(
                        f"Routine '{routine.name}' imports '{sym.name}' from "
                        f"Container "
                        f"'{routine_sym.interface.container_symbol.name}' but "
                        f"the call site has an import of a symbol with the "
                        f"same name from Container "
                        f"'{sym.interface.container_symbol.name}'.")

        # Check for unresolved symbols or for any accessed from the Container
        # containing the target routine.
        refs = routine.walk(Reference)
        for ref in refs:
            if ref.symbol.name not in routine_table:
                sym = routine_table.lookup(ref.symbol.name)
                if sym.is_unresolved:
                    raise TransformationError(
                        f"Routine '{routine.name}' cannot be inlined because "
                        f"it accesses an un-resolved variable "
                        f"'{ref.symbol.name}'.")
                if not sym.is_import:
                    raise TransformationError(
                        f"Routine '{routine.name}' cannot be inlined because "
                        f"it accesses variable '{ref.symbol.name}' from its "
                        f"parent container.")

        # Check that the shape of any dummy array arguments are the same as
        # those at the call site.
        visitor = FortranWriter()
        for dummy_arg, actual_arg in zip(routine_table.argument_list,
                                         node.children):
            dummy_rank = 0
            actual_rank = 0
            if not isinstance(actual_arg, Reference):
                # TODO #1799 this really needs the `datatype` method to be
                # extended to support all nodes. For now we have to skip
                # anything that's not a Reference.
                continue

            if hasattr(dummy_arg.datatype, "shape"):
                dummy_rank = len(dummy_arg.datatype.shape)
            if hasattr(actual_arg.datatype, "shape"):
                actual_rank = len(actual_arg.datatype.shape)
            if dummy_rank != actual_rank:
                # It's OK to use the loop variable in the lambda definition
                # because if we get to this point then we're going to quit
                # the loop.
                # pylint: disable=cell-var-from-loop
                raise TransformationError(LazyString(
                        lambda: f"Cannot inline routine '{routine.name}' "
                        f"because it reshapes an argument: actual argument "
                        f"'{visitor(actual_arg)}' has rank {actual_rank} but "
                        f"the corresponding dummy argument, '{dummy_arg.name}'"
                        f", has rank {dummy_rank}"))
            if actual_rank:
                ranges = actual_arg.walk(Range)
                for rge in ranges:
                    if rge.parent is actual_arg:
                        if not actual_arg.is_full_range(
                                actual_arg.indices.index(rge)):
                            raise TransformationError(LazyString(
                                lambda: f"Cannot inline routine "
                                f"'{routine.name}' because argument "
                                f"'{visitor(actual_arg)}' is "
                                f"an array subsection (TODO #924)."))
                    else:
                        # Have a range in an indirect access.
                        raise TransformationError("TODO")

    @staticmethod
    def _find_routine(call_node):
        '''
        Searches for the definition of the routine that is being called by
        the supplied Call.

        Currently only supports routines that are present in the
        same source file - TODO #924.

        :param call_node: the Call that is to be inlined.
        :type call_node: :py:class:`psyclone.psyir.nodes.Call`

        :returns: the PSyIR for the target routine.
        :rtype: :py:class:`psyclone.psyir.nodes.Routine`

        :raises TransformationError: if the RoutineSymbol is not local.
        :raises TransformationError: if the routine symbol is local but the \
            definition cannot be found.
        '''
        name = call_node.routine.name
        routine_sym = call_node.scope.symbol_table.lookup(name)
        if not routine_sym.is_local:
            raise TransformationError(
                f"Routine '{name}' is imported and therefore cannot currently "
                f"be inlined - TODO #924.")
        table = routine_sym.find_symbol_table(call_node)
        for routine in table.node.walk(Routine):
            if routine.name == name:
                return routine

        raise TransformationError(
            f"Failed to find the source for routine '{name}' and "
            f"therefore cannot inline it.")


# For AutoAPI auto-documentation generation.
__all__ = ["InlineTrans"]
