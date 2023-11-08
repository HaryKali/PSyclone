# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2023, Science and Technology Facilities Council.
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
# Author J. Henrichs, Bureau of Meteorology

'''This module contains the ModuleInfo class, which is used to store
and cache information about a module: the filename, source code (if requested)
and the fparser tree (if requested), and information about routine it
includes, and external symbol usage.
'''

import os

from fparser.common.readfortran import FortranStringReader
from fparser.two.Fortran2003 import (Function_Subprogram, Interface_Block,
                                     Interface_Stmt, Procedure_Stmt,
                                     Subroutine_Subprogram, Use_Stmt)
from fparser.two.parser import ParserFactory
from fparser.two.utils import FortranSyntaxError, walk

from psyclone.errors import InternalError, PSycloneError
from psyclone.psyir.nodes import Container, FileContainer, Routine
from psyclone.psyir.frontend.fparser2 import Fparser2Reader
from psyclone.psyir.symbols import SymbolError


# ============================================================================
class ModuleInfoError(PSycloneError):
    '''
    PSyclone-specific exception for use when an error with the module manager
    happens - typically indicating that some module information cannot be
    found.

    :param str value: the message associated with the error.

    '''
    def __init__(self, value):
        PSycloneError.__init__(self, value)
        self.value = "ModuleInfo error: "+str(value)


# ============================================================================
class ModuleInfo:
    # pylint: disable=too-many-instance-attributes
    '''This class stores mostly cached information about modules: it stores
    the original filename, if requested it will read the file and then caches
    the plain text file, and if required it will parse the file, and then
    cache the fparser AST.

    :param str name: the module name.
    :param str filename: the name of the source file that stores this module \
        (including path).

    '''

    def __init__(self, name, filename):
        self._name = name
        self._filename = filename
        # A cache for the source code:
        self._source_code = None

        # A cache for the fparser tree
        self._parse_tree = None

        # A cache for the PSyIR representation
        self._psyir = None

        # A cache for the module dependencies: this is just a set
        # of all modules used by this module. Type: Set[str]
        self._used_modules = None

        # This is a dictionary containing the sets of symbols imported from
        # each module, indexed by the module names: Dict[str, Set(str)].
        self._used_symbols_from_module = None

        # This variable will be a set that stores the name of all routines
        # (based on fparser), # so we can test is a routine is defined
        # without having to convert the AST to PSyIR. It is initialised with
        # None so we avoid trying to parse a file more than once (parsing
        # errors would cause routine_names to be empty, so we can test
        # if routine_name is None vs if routine_names is empty)
        self._routine_names = None

        # This dictionary stores the mapping of routine name to the list
        # of PSyIR Routine nodes. It is a list since in case of a generic
        # interface several Routine nodes are required.
        self._psyir_of_routines = None

        # This map contains the list of routine names that are part
        # of the same generic interface.
        self._generic_interfaces = {}

        # This is a dictionary that will cache non-local symbols used in
        # each routine. The key is the lowercase routine name, and the
        # value is a list of triplets:
        # - the type ('subroutine', 'function', 'reference', 'unknown').
        #   The latter is used for array references or function calls,
        #   which we cannot distinguish till #1314 is done.
        # - the name of the module (lowercase)
        # - the name of the symbol (lowercase)
        self._routine_non_locals = None

        self._processor = Fparser2Reader()

    # ------------------------------------------------------------------------
    @property
    def name(self):
        ''':returns: the name of this module.
        :rtype: str

        '''
        return self._name

    # ------------------------------------------------------------------------
    @property
    def filename(self):
        ''':returns: the filename that contains the source code for this \
            module.
        :rtype: str

        '''
        return self._filename

    # ------------------------------------------------------------------------
    def get_source_code(self):
        '''Returns the source code for the module. The first time, it
        will be read from the file, but the data is then cached.

        :returns: the source code.
        :rtype: str

        :raises ModuleInfoError: when the file cannot be read.

        '''
        if self._source_code is None:
            try:
                with open(self._filename, "r", encoding='utf-8') as file_in:
                    self._source_code = file_in.read()
            except FileNotFoundError as err:
                raise ModuleInfoError(
                    f"Could not find file '{self._filename}' when trying to "
                    f"read source code for module '{self._name}'") from err

        return self._source_code

    # ------------------------------------------------------------------------
    def get_parse_tree(self):
        '''Returns the fparser AST for this module. The first time, the file
        will be parsed by fparser using the Fortran 2008 standard. The AST is
        then cached for any future uses.

        :returns: the fparser AST for this module.
        :rtype: :py:class:`fparser.two.Fortran2003.Program`

        '''
        if self._parse_tree is None:
            # Set routine_names to be an empty set (it was None before).
            # This way we avoid that any other function might trigger to
            # parse this file again (in case of parsing errors).
            self._routine_names = set()

            reader = FortranStringReader(self.get_source_code())
            parser = ParserFactory().create(std="f2008")
            self._parse_tree = parser(reader)

            # First collect information about all subroutines/functions.
            # Store information about generic interface to be handled later
            # (so we only walk the tree once):
            all_generic_interfaces = []
            for routine in walk(self._parse_tree, (Function_Subprogram,
                                                   Subroutine_Subprogram,
                                                   Interface_Block)):
                if isinstance(routine, Interface_Block):
                    all_generic_interfaces.append(routine)
                else:
                    routine_name = str(routine.content[0].items[1])
                    self._routine_names.add(routine_name)

            # Then handle all generic interfaces and add them to
            # _generic_interfaces:
            for interface in all_generic_interfaces:
                # Get the name of the interface from the Interface_Stmt:
                name = str(walk(interface, Interface_Stmt)[0].items[0]).lower()
                self._routine_names.add(name)

                # Collect all specific functions for this generic interface
                routine_names = []
                for proc_stmt in walk(interface, Procedure_Stmt):
                    # Convert the items to strings:
                    routine_names.extend([str(i) for i in
                                          proc_stmt.items[0].items])
                self._generic_interfaces[name] = routine_names

        return self._parse_tree

    # ------------------------------------------------------------------------
    def contains_routine(self, routine_name):
        ''':returns: whether the specified routine name is part of this
            module or not. It will also return False if the file could
            not be parsed.
        :rtype: bool

        '''
        if self._routine_names is None:
            # This will trigger adding routine information
            try:
                self.get_parse_tree()
            except FortranSyntaxError:
                return False

        return routine_name.lower() in self._routine_names

    # ------------------------------------------------------------------------
    def _extract_import_information(self):
        '''This internal function analyses a given module source file and
        caches which modules are imported (in self._used_modules), and which
        symbol is imported from each of these modules (in
        self._used_symbols_from_module).

        '''
        # Initialise the caches:
        self._used_modules = set()
        self._used_symbols_from_module = {}

        try:
            parse_tree = self.get_parse_tree()
        except FortranSyntaxError:
            # Hide syntax errors
            return
        for use in walk(parse_tree, Use_Stmt):
            # Ignore intrinsic modules:
            if str(use.items[0]) == "INTRINSIC":
                continue

            mod_name = str(use.items[2])
            self._used_modules.add(mod_name)
            all_symbols = set()

            only_list = use.items[4]
            # If there is no only_list, then the set of symbols
            # will stay empty
            if only_list:
                # Parse the only list:
                for symbol in only_list.children:
                    all_symbols.add(str(symbol))

            self._used_symbols_from_module[mod_name] = all_symbols

    # ------------------------------------------------------------------------
    def get_used_modules(self):
        '''This function returns a set of all modules `used` in this
        module. Fortran `intrinsic` modules will be ignored. The information
        is based on the fparser parse tree of the module (since fparser can
        handle more files than PSyir, like LFRic's `constants_mod` which has
        pre-processor directives).

        :returns: a set with all imported module names.
        :rtype: Set[str]

        '''
        if self._used_modules is None:
            self._extract_import_information()

        return self._used_modules

    # ------------------------------------------------------------------------
    def get_used_symbols_from_modules(self):
        '''This function returns information about which modules are used by
        this module, and also which symbols are imported. The return value is
        a dictionary with the used module name as key, and a set of all
        imported symbol names as value.

        :returns: a dictionary that gives for each module name the set \
            of symbols imported from it.
        :rtype: Dict[str, Set[str]]

        '''
        if self._used_symbols_from_module is None:
            self._extract_import_information()

        return self._used_symbols_from_module

    # ------------------------------------------------------------------------
    def get_psyir(self, routine_name=None):
        '''Returns the PSyIR representation of this module. This is based
        on the fparser tree (see get_parse_tree), and the information is
        cached. If the PSyIR must be modified, it needs to be copied,
        otherwise the modified tree will be returned from the cache in the
        future.
        If the conversion to PSyIR fails, a dummy FileContainer with an
        empty Container (module) is returned, which avoids additional error
        handling in many other subroutines.
        #TODO 2120: This should be revisited when improving on the error
        handling.

        :param routine_name: optional the name of a routine.
        :type routine_name: Optional[str]

        :returns: PSyIR representing this module.
        :rtype: List[:py:class:`psyclone.psyir.nodes.Node`]

        '''
        if self._psyir is None:
            try:
                self._psyir = \
                    self._processor.generate_psyir(self.get_parse_tree())
            except (KeyError, SymbolError, InternalError, FortranSyntaxError):
                # Create a dummy FileContainer with a dummy module. This avoids
                # additional error handling in other subroutines, since they
                # will all return 'no information', whatever you ask for
                self._psyir = FileContainer(os.path.basename(self._filename))
                module = Container("invalid-module")
                self._psyir.children.append(module)
            # Store the PSyIR of all routines:
            self._psyir_of_routines = {}
            for routine in self._psyir.walk(Routine):
                self._psyir_of_routines[routine.name.lower()] = routine

        if routine_name is not None:
            return self._psyir_of_routines[routine_name.lower()]
        return self._psyir

    # ------------------------------------------------------------------------
    def get_non_local_symbols(self, routine_name):
        '''This function returns a list of non-local accesses in this
        routine. It returns a list of triplets, each one containing:

        - the type ('routine', 'function', 'reference', 'unknown').
          The latter is used for array references or function calls,
          which we cannot distinguish till #1314 is done.
        - the name of the module (lowercase). This can be 'None' if no
          module information is available.
        - the Signature of the symbol
        - the access information for the given variable

        :param str routine_name: name of the routine for which to return
            the non-local symbol information.

        :returns: the non-local accesses in this routine.
        :rtype: List[Tuple[str, str, :py:class:`psyclone.core.Signature`, \
                          :py:class:`psyclone.core.SingleVariableAccessInfo`]]

        '''
        if self._psyir_of_routines is None:
            self.get_psyir()
        routine_name = routine_name.lower()
        if routine_name in self._generic_interfaces:
            # If a generic interface name is queried, return the union
            # of all routines listed. Use a better variable name:
            generic_name = routine_name
            non_locals = []
            for name in self._generic_interfaces[generic_name]:
                non_locals.extend(self.get_non_local_symbols(name))
            return non_locals

        # It's not a generic interface. Just query the Routine object:
        return self._psyir_of_routines[routine_name].get_non_local_symbols()

    # ------------------------------------------------------------------------
    def get_symbol(self, name):
        '''Returns the symbol with the specified name from the module symbol
        table.

        :param str name: name of the symbol to look up.

        :returns: the symbol with the give name, or None if the information
            could not be found.
        :rtype: Union[:py:class:`psyclone.psyir.symbols.Symbol`, NoneType]

        '''
        symbol_table = self.get_psyir().children[0].symbol_table

        try:
            return symbol_table.lookup(name)
        except KeyError:
            # Convert the exception to a None return value.
            return None
