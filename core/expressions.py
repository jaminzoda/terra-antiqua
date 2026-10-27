# Copyright (C) 2021 by Jovid Aminov, Diego Ruiz, Guillaume Dupont-Nivet
# Terra Antiqua is a plugin for the software QGis that deals with the reconstruction of paleogeography.
# Full copyright notice in file: terra_antiqua.py
# [QGIS4 port] New in v1.1.1 (lines marked "# [QGIS4 port]"):
#  - Evaluates the expressions and formulas typed in the tools (e.g. "H > 2000", "H*0.5 + 100")
#    without Python's eval(), which the QGIS plugin repository blocks as a security risk.
#  - Results are the same as with eval() for expressions made of numbers, H, arithmetic,
#    comparisons, &, |, ~, brackets and NumPy math functions. Anything else (imports, hidden
#    attributes, file access, etc.) is refused with a clear message.
#  See core/compat.py for the note on how this port was made.

"""Safe evaluation of user expressions on elevation arrays."""  # [QGIS4 port]

import ast
import builtins
import operator
import types

import numpy as np

_BINARY_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.BitAnd: operator.and_, ast.BitOr: operator.or_,
    ast.BitXor: operator.xor, ast.LShift: operator.lshift, ast.RShift: operator.rshift,
    ast.MatMult: operator.matmul,
}
_UNARY_OPERATORS = {
    ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Not: operator.not_, ast.Invert: operator.invert,
}
_COMPARISONS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
    ast.Gt: operator.gt, ast.GtE: operator.ge, ast.Is: operator.is_, ast.IsNot: operator.is_not,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
}

# NumPy functions that read or write files, run code, or reach low-level memory are not offered.
_NUMPY_EXCLUDED = {
    "load", "save", "savez", "savez_compressed", "savetxt", "loadtxt", "genfromtxt", "fromfile",
    "fromregex", "memmap", "DataSource", "ctypeslib", "lib", "show_config", "show_runtime", "info",
    "source", "who", "lookfor", "get_include", "test", "add_newdoc", "add_docstring", "deprecate",
    "deprecate_with_doc", "recfromcsv", "recfromtxt", "set_string_function", "setbufsize",
    "frompyfunc", "vectorize", "piecewise", "apply_along_axis", "apply_over_axes", "nditer",
    "nested_iters", "char", "rec", "emath", "testing", "f2py", "distutils", "polynomial", "fft",
    "linalg", "random", "ma", "matrixlib", "core", "compat", "typing", "exceptions", "dtypes",
}


def _allowed_numpy_object(name):
    if name.startswith("_") or name in _NUMPY_EXCLUDED:
        return False
    obj = getattr(np, name, None)
    return obj is not None and not isinstance(obj, types.ModuleType)


# The names that "from numpy import *" provides, as the original modules used
_NUMPY_STAR = {name: getattr(np, name) for name in getattr(np, "__all__", dir(np))
               if _allowed_numpy_object(name)}
# Everything reachable as np.<name>
_NUMPY_ATTRIBUTES = {name for name in dir(np) if _allowed_numpy_object(name)}

# Python built-ins that make sense in a formula
_SAFE_BUILTINS = {name: getattr(builtins, name) for name in (
    "abs", "all", "any", "bool", "complex", "divmod", "float", "int", "len", "list", "max", "min",
    "pow", "range", "round", "sum", "tuple")}

# Attributes allowed on numbers and arrays (e.g. H.mean())
_VALUE_ATTRIBUTES = {"shape", "size", "ndim", "T", "real", "imag", "dtype", "mean", "min", "max",
                     "sum", "std", "any", "all", "clip", "round", "astype", "copy"}
_VALUE_TYPES = (np.ndarray, np.generic, int, float, complex, bool)


def _base_names():
    """Names visible to an expression, in the same order of precedence as in the original modules:
    Python built-ins, then "from numpy import *", then the restored built-ins, then np."""
    names = dict(_SAFE_BUILTINS)
    names.update(_NUMPY_STAR)
    names.update({name: getattr(builtins, name) for name in ("abs", "bool", "max", "min", "pow", "round")})
    names["np"] = np
    return names


class ExpressionError(ValueError):
    """Raised when an expression uses something that is not allowed."""


def evaluate(expression, variables):  # [QGIS4 port]
    """Evaluates an expression such as "H > 2000" or "H*0.5 + sqrt(abs(H))".

    :param expression: the expression typed by the user.
    :param variables: names the expression may use, e.g. {"H": elevation_array}.
    :return: the result, as eval() would return it.
    """
    tree = ast.parse(str(expression).strip(), mode="eval")
    names = _base_names()
    names.update(variables)
    return _Evaluator(names).visit(tree.body)


class _Evaluator:
    def __init__(self, names):
        self.names = names

    def visit(self, node):
        method = getattr(self, "visit_" + type(node).__name__, None)
        if method is None:
            raise ExpressionError(f"'{type(node).__name__}' is not allowed in expressions")
        return method(node)

    # --- values
    def visit_Constant(self, node):
        return node.value

    def visit_Num(self, node):  # Python 3.7
        return node.n

    def visit_Str(self, node):  # Python 3.7
        return node.s

    def visit_NameConstant(self, node):  # Python 3.7
        return node.value

    def visit_Ellipsis(self, node):  # Python 3.7
        return Ellipsis

    def visit_Name(self, node):
        if node.id.startswith("_"):
            raise ExpressionError(f"'{node.id}' is not allowed in expressions")
        if node.id not in self.names:
            raise NameError(f"name '{node.id}' is not defined")
        return self.names[node.id]

    def visit_Attribute(self, node):
        value = self.visit(node.value)
        attr = node.attr
        if not attr.startswith("_"):
            if value is np and attr in _NUMPY_ATTRIBUTES:
                return getattr(np, attr)
            if isinstance(value, _VALUE_TYPES) and attr in _VALUE_ATTRIBUTES:
                return getattr(value, attr)
        raise ExpressionError(f"'.{attr}' is not allowed in expressions")

    def visit_Tuple(self, node):
        return tuple(self.visit(e) for e in node.elts)

    def visit_List(self, node):
        return [self.visit(e) for e in node.elts]

    # --- operations
    def visit_BinOp(self, node):
        op = _BINARY_OPERATORS.get(type(node.op))
        if op is None:
            raise ExpressionError("this operator is not allowed in expressions")
        return op(self.visit(node.left), self.visit(node.right))

    def visit_UnaryOp(self, node):
        return _UNARY_OPERATORS[type(node.op)](self.visit(node.operand))

    def visit_BoolOp(self, node):  # same short-circuit rules as Python's "and" / "or"
        value = self.visit(node.values[0])
        for next_node in node.values[1:]:
            if isinstance(node.op, ast.And):
                if not value:
                    return value
            elif value:
                return value
            value = self.visit(next_node)
        return value

    def visit_Compare(self, node):  # a < b < c behaves as (a < b) and (b < c), as in Python
        left = self.visit(node.left)
        last = len(node.ops) - 1
        for i, (op, comparator) in enumerate(zip(node.ops, node.comparators)):
            right = self.visit(comparator)
            result = _COMPARISONS[type(op)](left, right)
            if i == last or not result:
                return result
            left = right

    def visit_IfExp(self, node):
        return self.visit(node.body) if self.visit(node.test) else self.visit(node.orelse)

    def visit_Call(self, node):
        func = self.visit(node.func)
        args = []
        for arg in node.args:
            if isinstance(arg, ast.Starred):
                raise ExpressionError("'*' arguments are not allowed in expressions")
            args.append(self.visit(arg))
        kwargs = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                raise ExpressionError("'**' arguments are not allowed in expressions")
            kwargs[keyword.arg] = self.visit(keyword.value)
        return func(*args, **kwargs)

    # --- indexing, e.g. H[H > 0]
    def visit_Subscript(self, node):
        return self.visit(node.value)[self.visit(node.slice)]

    def visit_Index(self, node):  # Python 3.7 / 3.8
        return self.visit(node.value)

    def visit_Slice(self, node):
        return slice(*(None if part is None else self.visit(part)
                       for part in (node.lower, node.upper, node.step)))

    def visit_ExtSlice(self, node):  # Python 3.7 / 3.8
        return tuple(self.visit(d) for d in node.dims)
