# -----------------------------------------------------------------------------
# BSD 3-Clause License
#
# Copyright (c) 2019-2023, Science and Technology Facilities Council.
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
# Authors R. W. Ford, A. R. Porter, S. Siso and N. Nobre, STFC Daresbury Lab
# Modified J. Henrichs, Bureau of Meteorology
# -----------------------------------------------------------------------------

''' This module contains the datatype definitions.'''

import abc
from collections import OrderedDict, namedtuple
from enum import Enum

from psyclone.errors import InternalError
from psyclone.psyir.symbols.data_type_symbol import DataTypeSymbol
from psyclone.psyir.symbols.datasymbol import DataSymbol
from psyclone.psyir.symbols.symbol import Symbol


class DataType(metaclass=abc.ABCMeta):
    '''Abstract base class from which all types are derived.'''

    @abc.abstractmethod
    def __str__(self):
        '''
        :returns: a description of this type.
        :rtype: str

        '''

    def __eq__(self, other):
        '''
        :param Any other: the object to check equality to.

        :returns: whether this type is equal to the 'other' type.
        :rtype: bool
        '''
        return type(other) is type(self)


class DeferredType(DataType):
    # pylint: disable=too-few-public-methods
    '''Indicates that the type is unknown at this point.'''

    def __str__(self):
        '''
        :returns: a description of this deferred type.
        :rtype: str

        '''
        return "DeferredType"


class NoType(DataType):
    # pylint: disable=too-few-public-methods
    ''' Indicates that the associated symbol has an empty type (equivalent
    to `void` in C). '''

    def __str__(self):
        return "NoType"


class UnknownType(DataType, metaclass=abc.ABCMeta):
    '''
    Indicates that a variable declaration is not supported by the PSyIR.
    This class is abstract and must be subclassed for each language
    supported by the PSyIR frontends.

    :param str declaration_txt: string containing the original variable \
                                declaration.

    :raises TypeError: if the supplied declaration_txt is not a str.

    '''
    def __init__(self, declaration_txt):
        if not isinstance(declaration_txt, str):
            raise TypeError(
                f"UnknownType constructor expects the original variable "
                f"declaration as a string but got an argument of type "
                f"'{type(declaration_txt).__name__}'")
        self._declaration = None
        self.declaration = declaration_txt

    @abc.abstractmethod
    def __str__(self):
        ''' Abstract method that must be implemented in subclass. '''

    @property
    def declaration(self):
        '''
        :returns: the original declaration of the symbol. This is obviously \
                  language specific and hence this class must be subclassed.
        :rtype: str
        '''
        return self._declaration

    @declaration.setter
    def declaration(self, value):
        '''
        Sets the original declaration that this instance represents.

        :param str value: the original declaration.

        '''
        self._declaration = value[:]


class UnknownFortranType(UnknownType):
    '''
    Indicates that a Fortran declaration is not supported by the PSyIR.

    :param str declaration_txt: string containing the original variable \
                                declaration.
    '''
    def __init__(self, declaration_txt):
        super().__init__(declaration_txt)
        # This will hold the Fortran type specification (as opposed to
        # the whole declaration).
        self._type_text = ""

    def __str__(self):
        return f"UnknownFortranType('{self._declaration}')"

    @property
    def declaration(self):
        '''
        This useless routine is required so that we can override the associated
        setter method below.
        '''
        return super().declaration

    @declaration.setter
    def declaration(self, value):
        '''
        Sets the original declaration that this instance represents and
        removes any cached type text.

        :param str value: the original declaration.

        '''
        self._declaration = value[:]
        self._type_text = ""

    @property
    def type_text(self):
        '''
        Parses the original Fortran declaration and uses the resulting
        parse tree to extract the type information. This is returned in
        text form and also cached.

        TODO #1419 - alter Unknown(Fortran)Type so that it is only the
        type information that is stored as a string. i.e. remove the name
        of the variable being declared. Once that is done this method
        won't be required.

        :returns: the Fortran code specifying the type.
        :rtype: str
        '''
        if self._type_text:
            return self._type_text

        # Encapsulate fparser2 functionality here.
        # pylint:disable=import-outside-toplevel
        from fparser.common.readfortran import FortranStringReader
        from fparser.common.sourceinfo import FortranFormat
        from fparser.two import Fortran2008
        from fparser.two.parser import ParserFactory
        string_reader = FortranStringReader(self._declaration)
        # Set reader to free format.
        string_reader.set_format(FortranFormat(True, False))
        ParserFactory().create(std="f2008")
        ptree = Fortran2008.Declaration_Construct(
            string_reader)
        self._type_text = str(ptree.children[0])

        return self._type_text

    def __eq__(self, other):
        '''
        :param Any other: the object to check equality to.

        :returns: whether this type is equal to the 'other' type.
        :rtype: bool
        '''
        if not super().__eq__(other):
            return False

        return other.type_text == self.type_text


class ScalarType(DataType):
    '''Describes a scalar datatype (and its precision).

    :param intrinsic: the intrinsic of this scalar type.
    :type intrinsic: :py:class:`pyclone.psyir.datatypes.ScalarType.Intrinsic`
    :param precision: the precision of this scalar type.
    :type precision: :py:class:`psyclone.psyir.symbols.ScalarType.Precision`, \
        int or :py:class:`psyclone.psyir.symbols.DataSymbol`

    :raises TypeError: if any of the arguments are of the wrong type.
    :raises ValueError: if any of the argument have unexpected values.

    '''

    class Intrinsic(Enum):
        '''Enumeration of the different intrinsic scalar datatypes that are
        supported by the PSyIR.

        '''
        INTEGER = 1
        REAL = 2
        BOOLEAN = 3
        CHARACTER = 4

    class Precision(Enum):
        '''Enumeration of the different types of 'default' precision that may
        be specified for a scalar datatype.

        '''
        SINGLE = 1
        DOUBLE = 2
        UNDEFINED = 3

    def __init__(self, intrinsic, precision):
        if not isinstance(intrinsic, ScalarType.Intrinsic):
            raise TypeError(
                f"ScalarType expected 'intrinsic' argument to be of type "
                f"ScalarType.Intrinsic but found "
                f"'{type(intrinsic).__name__}'.")
        if not isinstance(precision, (int, ScalarType.Precision, DataSymbol)):
            raise TypeError(
                f"ScalarType expected 'precision' argument to be of type "
                f"int, ScalarType.Precision or DataSymbol, but found "
                f"'{type(precision).__name__}'.")
        if isinstance(precision, int) and precision <= 0:
            raise ValueError(
                f"The precision of a DataSymbol when specified as an integer "
                f"number of bytes must be > 0 but found '{precision}'.")
        if (isinstance(precision, DataSymbol) and
                not (isinstance(precision.datatype, ScalarType) and
                     precision.datatype.intrinsic ==
                     ScalarType.Intrinsic.INTEGER) and
                not isinstance(precision.datatype, DeferredType)):
            raise ValueError(
                f"A DataSymbol representing the precision of another "
                f"DataSymbol must be of either 'deferred' or scalar, "
                f"integer type but got: {precision}")

        self._intrinsic = intrinsic
        self._precision = precision

    @property
    def intrinsic(self):
        '''
        :returns: the intrinsic used by this scalar type.
        :rtype: :py:class:`pyclone.psyir.datatypes.ScalarType.Intrinsic`
        '''
        return self._intrinsic

    @property
    def precision(self):
        '''
        :returns: the precision of this scalar type.
        :rtype: :py:class:`psyclone.psyir.symbols.ScalarType.Precision`, \
            int or :py:class:`psyclone.psyir.symbols.DataSymbol`
        '''
        return self._precision

    def __str__(self):
        '''
        :returns: a description of this scalar datatype.
        :rtype: str

        '''
        if isinstance(self.precision, ScalarType.Precision):
            precision_str = self.precision.name
        else:
            precision_str = str(self.precision)
        return f"Scalar<{self.intrinsic.name}, {precision_str}>"

    def __eq__(self, other):
        '''
        :param Any other: the object to check equality to.

        :returns: whether this type is equal to the 'other' type.
        :rtype: bool
        '''
        if not super().__eq__(other):
            return False

        return (self.precision == other.precision and
                self.intrinsic == other.intrinsic)


class ArrayType(DataType):
    '''Describes an array datatype. Can be an array of intrinsic types (e.g.
    integer) or of structure types. For the latter, the type must currently be
    specified as a DataTypeSymbol (see #1031).

    :param datatype: the datatype of the array elements.
    :type datatype: :py:class:`psyclone.psyir.datatypes.DataType` or \
        :py:class:`psyclone.psyir.symbols.DataTypeSymbol`
    :param list shape: shape of the symbol in column-major order (leftmost \
        index is contiguous in memory). Each entry represents an array \
        dimension. If it is ArrayType.Extent.ATTRIBUTE the extent of that \
        dimension is unknown but can be obtained by querying the run-time \
        system (e.g. using the SIZE intrinsic in Fortran). If it is \
        ArrayType.Extent.DEFERRED then the extent is also unknown and may or \
        may not be defined at run-time (e.g. the array is ALLOCATABLE in \
        Fortran). Otherwise it can be an int or a DataNode (that returns an \
        int) or a 2-tuple of such quantities. If only a single value is \
        provided then that is taken to be the upper bound and the lower bound \
        defaults to 1. If a 2-tuple is provided then the two members specify \
        the lower and upper bounds, respectively, of the current dimension. \
        Note that providing an int is supported as a convenience, the provided\
        value will be stored internally as a Literal node.

    :raises TypeError: if the arguments are of the wrong type.
    :raises NotImplementedError: if a structure type does not have a \
                                 DataTypeSymbol as its type.
    '''
    class Extent(Enum):
        '''
        Enumeration of array shape extents that are unspecified at compile
        time. When the extent must exist and is accessible via the run-time
        system it is an 'ATTRIBUTE'. When it may or may not be defined in the
        current scope (e.g. the array may need to be allocated/malloc'd) it
        is 'DEFERRED'.

        '''
        DEFERRED = 1
        ATTRIBUTE = 2

    #: namedtuple used to store lower and upper limits of an array dimension
    ArrayBounds = namedtuple("ArrayBounds", ["lower", "upper"])

    def __init__(self, datatype, shape):

        # This import must be placed here to avoid circular dependencies.
        # pylint: disable=import-outside-toplevel
        from psyclone.psyir.nodes import Literal, DataNode

        def _node_from_int(var):
            ''' Helper routine that simply creates a Literal out of an int.
            If the supplied arg is not an int then it is returned unchanged.

            :param var: variable for which to create a Literal if necessary.
            :type var: int or :py:class:`psyclone.psyir.nodes.DataNode`

            :returns: a DataNode representing the supplied input.
            :rtype: :py:class:`psyclone.psyir.nodes.DataNode`

            '''
            if isinstance(var, int):
                return Literal(str(var), INTEGER_TYPE)
            return var

        if isinstance(datatype, DataType):
            if isinstance(datatype, StructureType):
                # TODO #1031 remove this restriction.
                raise NotImplementedError(
                    "When creating an array of structures, the type of "
                    "those structures must be supplied as a DataTypeSymbol "
                    "but got a StructureType instead.")
            if not isinstance(datatype, UnknownType):
                self._intrinsic = datatype.intrinsic
                self._precision = datatype.precision
            else:
                self._intrinsic = datatype
                self._precision = None
        elif isinstance(datatype, DataTypeSymbol):
            self._intrinsic = datatype
            self._precision = None
        else:
            raise TypeError(
                f"ArrayType expected 'datatype' argument to be of type "
                f"DataType or DataTypeSymbol but found "
                f"'{type(datatype).__name__}'.")
        # We do not have a setter for shape as it is an immutable property,
        # therefore we have a separate validation routine.
        self._validate_shape(shape)
        # Replace any ints in shape with a Literal. int's are only supported
        # as they allow a more concise dimension declaration.
        self._shape = []
        one = Literal("1", INTEGER_TYPE)
        for dim in shape:
            if isinstance(dim, (DataNode, int)):
                # The lower bound is 1 by default.
                self._shape.append(ArrayType.ArrayBounds(one.copy(),
                                                         _node_from_int(dim)))
            elif isinstance(dim, tuple):
                self._shape.append(
                    ArrayType.ArrayBounds(_node_from_int(dim[0]),
                                          _node_from_int(dim[1])))
            else:
                self._shape.append(dim)

        self._datatype = datatype

    @property
    def datatype(self):
        '''
        :returns: the datatype of each element in the array.
        :rtype: :py:class:`psyclone.psyir.symbols.DataSymbol`
        '''
        # TODO #1857: This property might be affected.
        return self._datatype

    @property
    def intrinsic(self):
        '''
        :returns: the intrinsic type of each element in the array.
        :rtype: :py:class:`pyclone.psyir.datatypes.ScalarType.Intrinsic` or \
                :py:class:`psyclone.psyir.symbols.DataSymbol`
        '''
        return self._intrinsic

    @property
    def precision(self):
        '''
        :returns: the precision of each element in the array.
        :rtype: :py:class:`psyclone.psyir.symbols.ScalarType.Precision`, \
            int or :py:class:`psyclone.psyir.symbols.DataSymbol`
        '''
        return self._precision

    @property
    def shape(self):
        '''
        :returns: the (validated) shape of the symbol in column-major order \
            (leftmost index is contiguous in memory) with each entry \
            representing an array dimension.

        :rtype: a list of ArrayType.Extent.ATTRIBUTE, \
            ArrayType.Extent.DEFERRED, or \
            :py:class:`psyclone.psyir.nodes.ArrayType.ArrayBounds`. If an \
            entry is ArrayType.Extent.ATTRIBUTE the extent of that dimension \
            is unknown but can be obtained by querying the run-time \
            system (e.g. using the SIZE intrinsic in Fortran). If it \
            is ArrayType.Extent.DEFERRED then the extent is also \
            unknown and may or may not be defined at run-time \
            (e.g. the array is ALLOCATABLE in Fortran). Otherwise an \
            entry is a DataNode that returns an int.

        '''
        self._validate_shape(self._shape)
        return self._shape

    def _validate_shape(self, extents):
        '''Check that the supplied shape specification is valid. This is not
        implemented as a setter because the shape property is immutable.

        :param extents: list of extents, one for each array dimension.
        :type extents: List[ \
            :py:class:`psyclone.psyir.symbols.ArrayType.Extent` | int \
            | :py:class:`psyclone.psyir.nodes.DataNode` | \
            Tuple[int | :py:class:`psyclone.psyir.nodes.DataNode | \
                  :py:class:`psyclone.psyir.symbols.ArrayType.Extent]]

        :raises TypeError: if extents is not a list.
        :raises TypeError: if one or more of the supplied extents is a \
            DataSymbol that is not a scalar integer or of Unknown/DeferredType.
        :raises TypeError: if one or more of the supplied extents is not an \
            int, ArrayType.Extent or DataNode.
        :raises TypeError: if the extents contain an invalid combination of \
            ATTRIBUTE/DEFERRED and known limits.

        '''
        # This import must be placed here to avoid circular
        # dependencies.
        # pylint: disable=import-outside-toplevel
        from psyclone.psyir.nodes import DataNode, Reference

        def _validate_data_node(dim_node, is_lower_bound=False):
            '''
            Checks that the supplied DataNode is valid as part of an
            array-shape specification.

            :param dim_node: the node to check for validity.
            :type dim_node: int | :py:class:`psyclone.psyir.nodes.DataNode`
            :param bool is_lower_bound: whether the supplied node represents \
                                        the lower bound of an array shape.

            :raises TypeError: if the DataNode is not valid in this context.

            '''
            if isinstance(dim_node, int):
                # An integer value is always valid.
                return

            # When issue #1799 is addressed then check that the
            # datatype returned is an int (or is unknown). For the
            # moment, just check that if the DataNode is a
            # Reference then the associated symbol is a scalar
            # integer or is unknown.
            if isinstance(dim_node, Reference):
                # Check the DataSymbol instance is a scalar
                # integer or is unknown
                dtype = dim_node.datatype
                if isinstance(dtype, ArrayType) and dtype.shape:
                    raise TypeError(
                        f"If a DataSymbol is referenced in a dimension "
                        f"declaration then it should be a scalar but "
                        f"'{dim_node}' is not.")
                if not (isinstance(dtype, (UnknownType, DeferredType)) or
                        dtype.intrinsic == ScalarType.Intrinsic.INTEGER):
                    raise TypeError(
                        f"If a DataSymbol is referenced in a dimension "
                        f"declaration then it should be an integer or "
                        f"of UnknownType or DeferredType, but "
                        f"'{dim_node.name}' is a '{dtype}'.")
                # TODO #1089 - add check that any References are not to a
                # local datasymbol that is not constant (as this would have
                # no value).
                return

            if isinstance(dim_node, ArrayType.Extent):
                if is_lower_bound:
                    raise TypeError(
                        "If present, the lower bound in an ArrayType 'shape' "
                        "must represent a value but found ArrayType.Extent")
                return

            if isinstance(dim_node, DataNode):
                return

            raise TypeError(
                f"ArrayType shape-list elements can only be 'int', "
                f"ArrayType.Extent, 'DataNode' or a 2-tuple thereof but found "
                f"'{type(dim_node).__name__}'.")

        # ---------------------------------------------------------------------
        if not isinstance(extents, list):
            raise TypeError(
                f"ArrayType 'shape' must be of type list but found "
                f"'{type(extents).__name__}'.")

        for dimension in extents:
            if isinstance(dimension, tuple):
                if len(dimension) != 2:
                    raise TypeError(
                        f"An ArrayType shape-list element specifying lower "
                        f"and upper bounds must be a 2-tuple but "
                        f"'{dimension}' has {len(dimension)} entries.")
                _validate_data_node(dimension[0], is_lower_bound=True)
                _validate_data_node(dimension[1])
            else:
                _validate_data_node(dimension)

        if ArrayType.Extent.DEFERRED in extents:
            if not all(dim == ArrayType.Extent.DEFERRED
                       for dim in extents):
                raise TypeError(
                    f"A declaration of an allocatable array must have"
                    f" the extent of every dimension as 'DEFERRED' but "
                    f"found shape: {extents}.")

        if ArrayType.Extent.ATTRIBUTE in extents:
            # If we have an 'assumed-shape' array then *every*
            # dimension must have an 'ATTRIBUTE' extent
            for dim in extents:
                if not (dim == ArrayType.Extent.ATTRIBUTE or
                        (isinstance(dim, tuple) and
                         dim[-1] == ArrayType.Extent.ATTRIBUTE)):
                    raise TypeError(
                        f"An assumed-shape array must have every "
                        f"dimension unspecified (either as 'ATTRIBUTE' or "
                        f"with the upper bound as 'ATTRIBUTE') but found "
                        f"shape: {extents}.")

    def __str__(self):
        '''
        :returns: a description of this array datatype. If the lower bound \
            of any dimension has the default value of 1 then it is omitted \
            for the sake of brevity.
        :rtype: str

        '''
        dims = []
        # The shape getter includes validation.
        for dimension in self.shape:
            if isinstance(dimension, ArrayType.ArrayBounds):
                dim_text = ""
                # Have to import locally to avoid circular dependence
                # pylint: disable=import-outside-toplevel
                from psyclone.psyir.nodes import Literal
                # Lower bound. If it is "1" then we omit it.
                if isinstance(dimension.lower, Literal):
                    if dimension.lower.value != "1":
                        dim_text = dimension.lower.value + ":"
                else:
                    dim_text = str(dimension.lower) + ":"
                # Upper bound.
                if isinstance(dimension.upper, Literal):
                    dim_text += dimension.upper.value
                else:
                    dim_text += str(dimension.upper)
                dims.append(dim_text)
            elif isinstance(dimension, ArrayType.Extent):
                dims.append(f"'{dimension.name}'")

        return f"Array<{self._datatype}, shape=[{', '.join(dims)}]>"

    def __eq__(self, other):
        '''
        :param Any other: the object to check equality to.

        :returns: whether this ArrayType is equal to the 'other' ArrayType.
        :rtype: bool
        '''
        if not super().__eq__(other):
            return False

        if (self.intrinsic != other.intrinsic or
                self.precision != other.precision):
            return False

        if len(self.shape) != len(other.shape):
            return False

        # TODO #1799 - this implementation currently has some limitations.
        # e.g. a(1:10) and b(2:11) have the same datatype (an array of 1
        # dimension and 10 elements) but we will currently return false.
        # One improvement could be to use the SymbolicMath to do the comparison
        # but this won't resolve all cases as shape can be references.
        for this_dim, other_dim in zip(self.shape, other.shape):
            if this_dim != other_dim:
                return False

        return True


class StructureType(DataType):
    '''
    Describes a 'structure' or 'derived' datatype that is itself composed
    of a list of other datatypes. Those datatypes are stored as an
    OrderedDict of namedtuples.

    Note, we could have chosen to use a SymbolTable to store the properties
    of the constituents of the type. (Since they too have a name, a type,
    and visibility.) If this class ends up duplicating a lot of the
    SymbolTable functionality then this decision could be revisited.

    '''
    # Each member of a StructureType is represented by a ComponentType
    # (named tuple).
    ComponentType = namedtuple("ComponentType", ["name", "datatype",
                                                 "visibility"])

    def __init__(self):
        self._components = OrderedDict()

    def __str__(self):
        return "StructureType<>"

    @staticmethod
    def create(components):
        '''
        Creates a StructureType from the supplied list of properties.

        :param components: the name, type and visibility of each component.
        :type components: list of 3-tuples

        :returns: the new type object.
        :rtype: :py:class:`psyclone.psyir.symbols.StructureType`

        '''
        stype = StructureType()
        for component in components:
            if len(component) != 3:
                raise TypeError(
                    f"Each component must be specified using a 3-tuple of "
                    f"(name, type, visibility) but found a tuple with "
                    f"{len(component)} members: {component}")
            stype.add(component[0], component[1], component[2])
        return stype

    @property
    def components(self):
        '''
        :returns: Ordered dictionary of the components of this type.
        :rtype: :py:class:`collections.OrderedDict`
        '''
        return self._components

    def add(self, name, datatype, visibility):
        '''
        Create a component with the supplied attributes and add it to
        this StructureType.

        :param str name: the name of the new component.
        :param datatype: the type of the new component.
        :type datatype: :py:class:`psyclone.psyir.symbols.DataType` or \
                        :py:class:`psyclone.psyir.symbols.DataTypeSymbol`
        :param visibility: whether this component is public or private.
        :type visibility: :py:class:`psyclone.psyir.symbols.Symbol.Visibility`

        :raises TypeError: if any of the supplied values are of the wrong type.

        '''
        if not isinstance(name, str):
            raise TypeError(
                f"The name of a component of a StructureType must be a 'str' "
                f"but got '{type(name).__name__}'")
        if not isinstance(datatype, (DataType, DataTypeSymbol)):
            raise TypeError(
                f"The type of a component of a StructureType must be a "
                f"'DataType' or 'DataTypeSymbol' but got "
                f"'{type(datatype).__name__}'")
        if not isinstance(visibility, Symbol.Visibility):
            raise TypeError(
                f"The visibility of a component of a StructureType must be "
                f"an instance of 'Symbol.Visibility' but got "
                f"'{type(visibility).__name__}'")
        if datatype is self:
            # A StructureType cannot contain a component of its own type
            raise TypeError(
                f"Error attempting to add component '{name}' - a "
                f"StructureType definition cannot be recursive - i.e. it "
                f"cannot contain components with the same type as itself.")

        self._components[name] = self.ComponentType(name, datatype, visibility)

    def lookup(self, name):
        '''
        :returns: the ComponentType tuple describing the named member of this \
                  StructureType.
        :rtype: :py:class:`psyclone.psyir.symbols.StructureType.ComponentType`
        '''
        return self._components[name]

    def __eq__(self, other):
        '''
        :param Any other: the object to check equality to.

        :returns: whether this StructureType is equal to the 'other' type.
        :rtype: bool
        '''
        if not super().__eq__(other):
            return False

        if len(self.components) != len(other.components):
            return False

        if self.components != other.components:
            return False

        return True


# Create common scalar datatypes
REAL_TYPE = ScalarType(ScalarType.Intrinsic.REAL,
                       ScalarType.Precision.UNDEFINED)
REAL_SINGLE_TYPE = ScalarType(ScalarType.Intrinsic.REAL,
                              ScalarType.Precision.SINGLE)
REAL_DOUBLE_TYPE = ScalarType(ScalarType.Intrinsic.REAL,
                              ScalarType.Precision.DOUBLE)
REAL4_TYPE = ScalarType(ScalarType.Intrinsic.REAL, 4)
REAL8_TYPE = ScalarType(ScalarType.Intrinsic.REAL, 8)
INTEGER_TYPE = ScalarType(ScalarType.Intrinsic.INTEGER,
                          ScalarType.Precision.UNDEFINED)
INTEGER_SINGLE_TYPE = ScalarType(ScalarType.Intrinsic.INTEGER,
                                 ScalarType.Precision.SINGLE)
INTEGER_DOUBLE_TYPE = ScalarType(ScalarType.Intrinsic.INTEGER,
                                 ScalarType.Precision.DOUBLE)
INTEGER4_TYPE = ScalarType(ScalarType.Intrinsic.INTEGER, 4)
INTEGER8_TYPE = ScalarType(ScalarType.Intrinsic.INTEGER, 8)
BOOLEAN_TYPE = ScalarType(ScalarType.Intrinsic.BOOLEAN,
                          ScalarType.Precision.UNDEFINED)
CHARACTER_TYPE = ScalarType(ScalarType.Intrinsic.CHARACTER,
                            ScalarType.Precision.UNDEFINED)

# Mapping from PSyIR scalar data types to intrinsic Python types
# ignoring precision.
TYPE_MAP_TO_PYTHON = {ScalarType.Intrinsic.INTEGER: int,
                      ScalarType.Intrinsic.CHARACTER: str,
                      ScalarType.Intrinsic.BOOLEAN: bool,
                      ScalarType.Intrinsic.REAL: float}


# For automatic documentation generation
__all__ = ["UnknownType", "UnknownFortranType", "DeferredType", "ScalarType",
           "ArrayType", "StructureType"]
