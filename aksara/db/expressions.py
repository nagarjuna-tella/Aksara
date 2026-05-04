"""
ORM expressions and query composition primitives.

v0.5.45: Adds Q(), F(), annotate(), and aggregate() support.
"""

from __future__ import annotations

from typing import Any, ClassVar, TYPE_CHECKING

from aksara.db import quote_identifier

if TYPE_CHECKING:
    from aksara.model.base import Model


class BaseExpression:
    """Base class for SQL expressions compiled by the ORM."""

    contains_aggregate: ClassVar[bool] = False

    def resolve(self, model: type["Model"], values: list[Any]) -> str:
        """Resolve the expression to parameterized SQL."""
        raise NotImplementedError

    def __add__(self, other: Any) -> "CombinedExpression":
        return CombinedExpression(self, "+", ensure_expression(other))

    def __sub__(self, other: Any) -> "CombinedExpression":
        return CombinedExpression(self, "-", ensure_expression(other))

    def __mul__(self, other: Any) -> "CombinedExpression":
        return CombinedExpression(self, "*", ensure_expression(other))

    def __truediv__(self, other: Any) -> "CombinedExpression":
        return CombinedExpression(self, "/", ensure_expression(other))

    def __radd__(self, other: Any) -> "CombinedExpression":
        return CombinedExpression(ensure_expression(other), "+", self)

    def __rsub__(self, other: Any) -> "CombinedExpression":
        return CombinedExpression(ensure_expression(other), "-", self)

    def __rmul__(self, other: Any) -> "CombinedExpression":
        return CombinedExpression(ensure_expression(other), "*", self)

    def __rtruediv__(self, other: Any) -> "CombinedExpression":
        return CombinedExpression(ensure_expression(other), "/", self)


class ValueExpression(BaseExpression):
    """Parameterize a literal value inside an expression tree."""

    def __init__(self, value: Any):
        self.value = value

    def resolve(self, model: type["Model"], values: list[Any]) -> str:
        values.append(self.value)
        return f"${len(values)}"


class F(BaseExpression):
    """Reference a model field directly in SQL."""

    def __init__(self, field_name: str):
        self.field_name = field_name

    def resolve(self, model: type["Model"], values: list[Any]) -> str:
        return _resolve_model_column(model, self.field_name)

    def __repr__(self) -> str:
        return f"F({self.field_name!r})"


class CombinedExpression(BaseExpression):
    """Compose two expressions with an arithmetic operator."""

    def __init__(self, lhs: BaseExpression, operator: str, rhs: BaseExpression):
        self.lhs = lhs
        self.operator = operator
        self.rhs = rhs

    def resolve(self, model: type["Model"], values: list[Any]) -> str:
        lhs_sql = self.lhs.resolve(model, values)
        rhs_sql = self.rhs.resolve(model, values)
        return f"({lhs_sql} {self.operator} {rhs_sql})"


class Aggregate(BaseExpression):
    """Base class for SQL aggregate functions."""

    contains_aggregate: ClassVar[bool] = True
    function_name: ClassVar[str] = "AGGREGATE"

    def __init__(self, source: str | BaseExpression = "*", *, distinct: bool = False):
        self.source = source
        self.distinct = distinct

    def resolve(self, model: type["Model"], values: list[Any]) -> str:
        if self.source == "*":
            source_sql = "*"
        elif isinstance(self.source, str):
            source_sql = _resolve_model_column(model, self.source)
        else:
            source_sql = self.source.resolve(model, values)

        distinct_sql = "DISTINCT " if self.distinct and source_sql != "*" else ""
        return f"{self.function_name}({distinct_sql}{source_sql})"


class Count(Aggregate):
    """COUNT aggregate."""

    function_name = "COUNT"


class Sum(Aggregate):
    """SUM aggregate."""

    function_name = "SUM"


class Avg(Aggregate):
    """AVG aggregate."""

    function_name = "AVG"


class Min(Aggregate):
    """MIN aggregate."""

    function_name = "MIN"


class Max(Aggregate):
    """MAX aggregate."""

    function_name = "MAX"


class Q:
    """Composable boolean query object for complex filters."""

    def __init__(self, **filters: Any):
        self.children: list[Q | tuple[str, Any]] = list(filters.items())
        self.connector = "AND"
        self.negated = False

    def __and__(self, other: "Q") -> "Q":
        return self._combine(other, "AND")

    def __or__(self, other: "Q") -> "Q":
        return self._combine(other, "OR")

    def __invert__(self) -> "Q":
        clone = self._clone()
        clone.negated = not clone.negated
        return clone

    def _combine(self, other: "Q", connector: str) -> "Q":
        if not isinstance(other, Q):
            return NotImplemented

        combined = Q()
        combined.children = [self._clone(), other._clone()]
        combined.connector = connector
        return combined

    def _clone(self) -> "Q":
        clone = Q()
        clone.children = [child._clone() if isinstance(child, Q) else child for child in self.children]
        clone.connector = self.connector
        clone.negated = self.negated
        return clone

    def __repr__(self) -> str:
        return (
            f"Q(children={self.children!r}, connector={self.connector!r}, "
            f"negated={self.negated!r})"
        )


def ensure_expression(value: Any) -> BaseExpression:
    """Wrap a literal value in an expression when needed."""
    if isinstance(value, BaseExpression):
        return value
    return ValueExpression(value)


def is_expression(value: Any) -> bool:
    """Return True when a value is an ORM expression."""
    return isinstance(value, BaseExpression)


def compile_expression(model: type["Model"], expression: Any, values: list[Any]) -> str:
    """Compile an expression tree to SQL."""
    return ensure_expression(expression).resolve(model, values)


def _resolve_model_column(model: type["Model"], field_name: str) -> str:
    """Resolve a model field name or FK column alias to a quoted column."""
    if field_name == "id":
        return quote_identifier("id")

    if field_name in model._fields:
        return quote_identifier(model._fields[field_name].column_name)

    if field_name.endswith("_id"):
        base_field_name = field_name[:-3]
        field = model._fields.get(base_field_name)
        if field is not None and field.column_name == field_name:
            return quote_identifier(field.column_name)

    raise ValueError(f"Unknown field reference: {field_name}")


__all__ = [
    "Aggregate",
    "Avg",
    "BaseExpression",
    "CombinedExpression",
    "Count",
    "F",
    "Max",
    "Min",
    "Q",
    "Sum",
    "compile_expression",
    "ensure_expression",
    "is_expression",
]