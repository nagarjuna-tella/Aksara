"""
Query Manager and QuerySet

Django-like query interface for Aksara models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Tuple, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from aksara.model.base import Model

from aksara.db import quote_identifier
from aksara.db.expressions import Aggregate, Q, compile_expression, is_expression
from aksara.exceptions import ConfigurationError

T = TypeVar("T", bound="Model")
_UNSET = object()


def _is_vector_field(field: Any) -> bool:
    """Return True for Vector fields, including subclasses."""
    from aksara.fields import Vector

    return isinstance(field, Vector)


def _typed_parameter(field: Any, param_idx: int) -> str:
    """Bind a value with the PostgreSQL type declared by its model field."""
    if _is_vector_field(field):
        return f"CAST(${param_idx} AS vector)"
    return f"CAST(${param_idx} AS {field.sql_type})"


# Supported lookup types
LOOKUP_OPERATORS = {
    "exact": "=",          # field__exact=value (same as field=value)
    "gt": ">",             # field__gt=value
    "gte": ">=",           # field__gte=value
    "lt": "<",             # field__lt=value
    "lte": "<=",           # field__lte=value
    "in": "IN",            # field__in=[v1, v2]
    "isnull": "IS NULL",   # field__isnull=True/False
    "icontains": "ILIKE",  # field__icontains="substring"
    "contains": "LIKE",    # field__contains="substring"
}


def _json_lookup_value(value: Any) -> str:
    """Normalize Python values for text-based JSON path comparisons."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _json_numeric_cast(value: Any) -> Optional[str]:
    """Determine the SQL numeric cast for JSON path comparisons."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return "double precision"
    return None


def _parse_isnull_value(value: Any) -> bool:
    """Parse __isnull values without relying on Python truthiness."""
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
        raise ValueError(
            "__isnull lookup expects a boolean or one of: "
            "true/false, 1/0, yes/no, y/n, on/off"
        )

    raise TypeError(
        "__isnull lookup expects a boolean or strict boolean string, "
        f"got {type(value).__name__}"
    )


def parse_lookup(key: str) -> Tuple[str, str]:
    """
    Parse a filter key into field name and lookup type.
    
    Args:
        key: Filter key like "email" or "age__gte"
        
    Returns:
        Tuple of (field_name, lookup_type)
    """
    if "__" in key:
        parts = key.rsplit("__", 1)
        field_name, lookup = parts[0], parts[1]
        if lookup in LOOKUP_OPERATORS:
            return field_name, lookup
        # If lookup not recognized, treat entire key as field name (exact match)
        return key, "exact"
    return key, "exact"


def split_json_lookup(model: Type[T], key: str) -> tuple[str, list[str], str]:
    """Split a filter key into base field, JSON path, and lookup type."""
    from aksara.fields import JSON

    field_name, lookup = parse_lookup(key)
    if field_name in model._fields:
        return field_name, [], lookup

    parts = field_name.split("__")
    if not parts:
        return field_name, [], lookup

    base_field = parts[0]
    field = model._fields.get(base_field)
    if field is None or not isinstance(field, JSON):
        return field_name, [], lookup

    return base_field, parts[1:], lookup


class QuerySet(Generic[T]):
    """
    Lazy query builder for filtering and fetching model instances.
    
    QuerySets are lazy - they don't execute until you call a terminal
    method like .all(), .first(), or .count().
    
    Usage:
        # Get all active users
        users = await User.objects.filter(is_active=True).all()
        
        # Get first matching user
        user = await User.objects.filter(email="test@example.com").first()
        
        # Count matching records
        count = await User.objects.filter(is_active=True).count()
        
        # Advanced lookups
        users = await User.objects.filter(
            age__gte=18,
            email__icontains="@gmail.com",
            status__in=["active", "pending"],
        ).all()
        
        # Ordering
        users = await User.objects.order_by("email").all()           # Ascending
        users = await User.objects.order_by("-created_at").all()     # Descending
        users = await User.objects.order_by("is_active", "-email").all()  # Multiple
        
        # Chained with filter
        users = await User.objects.filter(is_active=True).order_by("email").all()
        
        # Preload FK/O2O relations (avoids N+1)
        posts = await Post.objects.select_related("author").all()
        for p in posts:
            _ = p.author  # No additional query!
    """
    
    def __init__(
        self,
        model: Type[T],
        filters: Optional[Dict[str, Any]] = None,
        select_related_fields: Optional[Set[str]] = None,
        prefetch_related_fields: Optional[Set[str]] = None,
        order_by_fields: Optional[List[str]] = None,
        q_objects: Optional[List[Q]] = None,
        annotations: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a QuerySet.
        
        Args:
            model: The model class to query
            filters: Dictionary of field=value or field__lookup=value filters
            select_related_fields: Set of FK/O2O fields to eagerly load
            prefetch_related_fields: Set of M2M fields to eagerly load
            order_by_fields: List of field names for ordering (prefix with - for descending)
        """
        self._model = model
        self._filters = filters or {}
        self._select_related: Set[str] = select_related_fields or set()
        self._prefetch_related: Set[str] = prefetch_related_fields or set()
        self._order_by: Optional[List[str]] = order_by_fields
        self._q_objects: List[Q] = list(q_objects or [])
        self._annotations: Dict[str, Any] = dict(annotations or {})
        self._search: Optional[Tuple[str, List[str]]] = None  # (term, fields)
        self._limit_value: Optional[int] = None
        self._offset_value: Optional[int] = None
        self._soft_delete_mode: str | None = None

    def _clone(
        self,
        *,
        filters: Any = _UNSET,
        select_related_fields: Any = _UNSET,
        prefetch_related_fields: Any = _UNSET,
        order_by_fields: Any = _UNSET,
        q_objects: Any = _UNSET,
        annotations: Any = _UNSET,
        search: Any = _UNSET,
        limit_value: Any = _UNSET,
        offset_value: Any = _UNSET,
        soft_delete_mode: Any = _UNSET,
    ) -> "QuerySet[T]":
        """Clone the queryset while overriding selected state."""
        qs = QuerySet(
            self._model,
            self._filters.copy() if filters is _UNSET else filters,
            self._select_related.copy() if select_related_fields is _UNSET else select_related_fields,
            self._prefetch_related.copy() if prefetch_related_fields is _UNSET else prefetch_related_fields,
            (self._order_by.copy() if self._order_by else None) if order_by_fields is _UNSET else order_by_fields,
            self._q_objects.copy() if q_objects is _UNSET else q_objects,
            self._annotations.copy() if annotations is _UNSET else annotations,
        )
        qs._search = self._search if search is _UNSET else search
        qs._limit_value = self._limit_value if limit_value is _UNSET else limit_value
        qs._offset_value = self._offset_value if offset_value is _UNSET else offset_value
        qs._soft_delete_mode = (
            self._soft_delete_mode
            if soft_delete_mode is _UNSET
            else soft_delete_mode
        )
        return qs

    def limit(self, n: int) -> "QuerySet[T]":
        """Limit the number of rows returned."""
        if n is not None and n < 0:
            raise ValueError("limit must be non-negative")
        return self._clone(limit_value=n)

    def offset(self, n: int) -> "QuerySet[T]":
        """Skip the first n rows of the result."""
        if n is not None and n < 0:
            raise ValueError("offset must be non-negative")
        return self._clone(offset_value=n)

    @staticmethod
    def _assemble_query(*parts: str) -> str:
        """Join non-empty clause parts with a single space."""
        return " ".join(part for part in parts if part)

    def filter(self, *args: Q, **kwargs) -> "QuerySet[T]":
        """
        Add filter conditions to the query.
        
        Supports lookups:
            - field=value (exact match)
            - field__gt=value (greater than)
            - field__gte=value (greater than or equal)
            - field__lt=value (less than)
            - field__lte=value (less than or equal)
            - field__in=[v1, v2, ...] (membership)
            - field__isnull=True/False (null check)
            - field__icontains="substring" (case-insensitive contains)
            - field__contains="substring" (case-sensitive contains)
        
        Args:
            **kwargs: Field=value or field__lookup=value conditions (combined with AND)
            
        Returns:
            New QuerySet with additional filters
        """
        for q_object in args:
            if not isinstance(q_object, Q):
                raise TypeError("filter() positional arguments must be Q objects")

        new_filters = {**self._filters, **kwargs}
        new_q_objects = self._q_objects + list(args)
        return self._clone(filters=new_filters, q_objects=new_q_objects)

    def with_deleted(self) -> QuerySet[T]:
        """Include deleted rows without discarding existing query state."""
        return self._clone(soft_delete_mode="all")

    def only_deleted(self) -> QuerySet[T]:
        """Select deleted rows without discarding existing query state."""
        return self._clone(soft_delete_mode="deleted")
    
    def search(self, term: str, fields: List[str]) -> "QuerySet[T]":
        """
        Add a search condition across multiple fields (combined with OR).
        
        Args:
            term: The search term
            fields: List of field names to search across
            
        Returns:
            New QuerySet with search condition applied
        """
        if not term or not fields:
            return self

        return self._clone(search=(term, fields))
    
    def order_by(self, *fields: str) -> "QuerySet[T]":
        """
        Specify ordering for the query results.
        
        Fields can be specified as:
            - "field_name" for ascending order
            - "-field_name" for descending order
        
        Multiple fields can be specified; ordering is applied in order.
        Calling order_by() again replaces previous ordering.
        
        Args:
            *fields: Field names to order by (prefix with - for descending)
            
        Returns:
            New QuerySet with ordering applied
            
        Raises:
            ConfigurationError: If no fields provided or field doesn't exist
            
        Usage:
            # Ascending
            User.objects.order_by("email")
            
            # Descending
            User.objects.order_by("-created_at")
            
            # Multiple fields
            User.objects.order_by("is_active", "-created_at")
            
            # Chained (later call replaces earlier)
            User.objects.order_by("email").order_by("-created_at")  # final: created_at DESC
        """
        if not fields:
            raise ConfigurationError(
                "order_by() requires at least one field. "
                "Usage: .order_by('field') or .order_by('-field')"
            )
        
        # Validate each field
        validated_fields = []
        for field in fields:
            if not isinstance(field, str):
                raise ConfigurationError(
                    f"order_by() fields must be strings, got {type(field).__name__}"
                )
            
            # Parse descending prefix
            if field.startswith("-"):
                field_name = field[1:]
                if field_name.startswith("-"):
                    # Double minus like "--email" is invalid
                    raise ConfigurationError(
                        f"Invalid order_by field '{field}'. "
                        f"Use '-{field_name[1:]}' for descending order."
                    )
            else:
                field_name = field
            
            if not field_name:
                raise ConfigurationError(
                    "order_by() field name cannot be empty"
                )
            
            # Check if field exists on model
            # Allow 'id' as it's always present
            field_valid = False
            
            if field_name == "id":
                field_valid = True
            elif field_name in self._model._fields:
                field_valid = True
            elif field_name.endswith("_id"):
                # Check if it's a FK column name (e.g., author_id for FK field 'author')
                base_field_name = field_name[:-3]  # Remove _id suffix
                if base_field_name in self._model._fields:
                    # Verify it's actually a FK field with this column name
                    base_field = self._model._fields[base_field_name]
                    if hasattr(base_field, 'column_name') and base_field.column_name == field_name:
                        field_valid = True
            
            if not field_valid:
                available_fields = sorted(self._model._fields.keys())
                # Also add _id variants for FK fields
                fk_columns = []
                for fname, fobj in self._model._fields.items():
                    if hasattr(fobj, 'column_name') and fobj.column_name != fname:
                        fk_columns.append(fobj.column_name)
                all_orderable = sorted(set(available_fields + fk_columns))
                raise ConfigurationError(
                    f"Cannot order by '{field_name}' - field does not exist on {self._model.__name__}. "
                    f"Available fields: {', '.join(all_orderable)}"
                )
            
            validated_fields.append(field)
        
        return self._clone(order_by_fields=validated_fields)
    
    def select_related(self, *fields: str) -> "QuerySet[T]":
        """
        Mark ForeignKey / OneToOne fields to be eagerly loaded.
        
        Uses batched queries to avoid N+1 problems. After the main query,
        a single additional query fetches all related objects.
        
        Args:
            *fields: Names of FK/O2O fields to preload
            
        Returns:
            New QuerySet with select_related fields added
            
        Usage:
            # Single field
            posts = await Post.objects.select_related("author").all()
            
            # Multiple fields
            posts = await Post.objects.select_related("author", "category").all()
            
            # Chained
            posts = await Post.objects.select_related("author").select_related("category").all()
        """
        new_select_related = self._select_related | set(fields)
        return self._clone(select_related_fields=new_select_related)
    
    def prefetch_related(self, *fields: str) -> "QuerySet[T]":
        """
        Mark ManyToMany fields to be eagerly loaded.
        
        Uses batched queries to avoid N+1 problems.
        
        Args:
            *fields: Names of M2M fields to preload
            
        Returns:
            New QuerySet with prefetch_related fields added
        """
        new_prefetch_related = self._prefetch_related | set(fields)
        return self._clone(prefetch_related_fields=new_prefetch_related)

    def annotate(self, **kwargs: Any) -> "QuerySet[T]":
        """Add computed or aggregate annotations to the SELECT list."""
        if not kwargs:
            raise ValueError("annotate() requires at least one named expression")

        new_annotations = {**self._annotations, **kwargs}
        return self._clone(annotations=new_annotations)

    def _qualified_column(self, table_or_alias: str, column_name: str) -> str:
        """Build a qualified, quoted column reference."""
        return f"{quote_identifier(table_or_alias)}.{quote_identifier(column_name)}"

    def _base_column_reference(self, field_name: str, qualify: bool = False) -> str:
        """Resolve a column on the base model, optionally qualifying it."""
        _, _, column_name = self._resolve_field_reference(field_name)

        if not qualify:
            return quote_identifier(column_name)
        return self._qualified_column(self._model.__tablename__, column_name)

    def _resolve_field_reference(self, field_name: str):
        """Resolve model field names and FK/O2O DB-column aliases."""
        from aksara.fields import ForeignKey, OneToOne

        if field_name == "id" and field_name in self._model._fields:
            field = self._model._fields[field_name]
            return field_name, field, "id"

        if field_name in self._model._fields:
            field = self._model._fields[field_name]
            return field_name, field, field.column_name

        for model_field_name, field in self._model._fields.items():
            if not isinstance(field, (ForeignKey, OneToOne)):
                continue
            if field.db_column_name == field_name:
                return model_field_name, field, field.db_column_name

        raise ValueError(f"Unknown field reference: {field_name}")

    def _new_join_state(self) -> Dict[str, Any]:
        """Create state for deterministic join registration during compilation."""
        return {"joins": [], "seen": {}}

    def _register_join(self, join_state: Dict[str, Any], key: str, alias: str, join_sql: str) -> str:
        """Register a join once and return its alias."""
        if key not in join_state["seen"]:
            join_state["seen"][key] = alias
            join_state["joins"].append(join_sql)
        return join_state["seen"][key]

    def _build_join_clause(self, join_state: Optional[Dict[str, Any]] = None) -> str:
        """Build the SQL JOIN clause from a join state."""
        if not join_state or not join_state["joins"]:
            return ""
        return " ".join(join_state["joins"])

    def _resolve_joined_field_column(self, model: Type[T], alias: str, field_name: Optional[str]) -> str:
        """Resolve a field reference on a joined relation target."""
        resolved_name = field_name or "id"
        if resolved_name == "id":
            return self._qualified_column(alias, "id")

        if resolved_name in model._fields:
            return self._qualified_column(alias, model._fields[resolved_name].column_name)

        if resolved_name.endswith("_id"):
            base_field_name = resolved_name[:-3]
            field = model._fields.get(base_field_name)
            if field is not None and field.column_name == resolved_name:
                return self._qualified_column(alias, resolved_name)

        raise ValueError(
            f"Unknown related field '{resolved_name}' on {model.__name__}"
        )

    def _ensure_forward_fk_join(self, field_name: str, join_state: Dict[str, Any]) -> tuple[str, Type[T]]:
        """Ensure a JOIN exists for a forward FK/O2O relation."""
        field = self._model._fk_fields[field_name]
        related_model = field.to_model
        alias = f"{field_name}__rel"
        join_sql = (
            f"LEFT JOIN {quote_identifier(related_model.__tablename__)} AS {quote_identifier(alias)} "
            f"ON {self._qualified_column(alias, 'id')} = "
            f"{self._qualified_column(self._model.__tablename__, field.column_name)}"
        )
        self._register_join(join_state, f"forward_fk:{field_name}", alias, join_sql)
        return alias, related_model

    def _ensure_forward_m2m_join(self, field_name: str, join_state: Dict[str, Any]) -> tuple[str, Type[T]]:
        """Ensure JOINs exist for a forward many-to-many relation."""
        field = self._model._m2m_fields[field_name]
        related_model = field.to_model
        through_alias = f"{field_name}__through"
        relation_alias = f"{field_name}__rel"
        self._register_join(
            join_state,
            f"forward_m2m_through:{field_name}",
            through_alias,
            (
                f"LEFT JOIN {quote_identifier(field.join_table_name)} AS {quote_identifier(through_alias)} "
                f"ON {self._qualified_column(through_alias, field.source_column)} = "
                f"{self._qualified_column(self._model.__tablename__, 'id')}"
            ),
        )
        self._register_join(
            join_state,
            f"forward_m2m_target:{field_name}",
            relation_alias,
            (
                f"LEFT JOIN {quote_identifier(related_model.__tablename__)} AS {quote_identifier(relation_alias)} "
                f"ON {self._qualified_column(relation_alias, 'id')} = "
                f"{self._qualified_column(through_alias, field.target_column)}"
            ),
        )
        return relation_alias, related_model

    def _ensure_reverse_relation_join(self, relation_name: str, join_state: Dict[str, Any]) -> tuple[str, Type[T]]:
        """Ensure JOINs exist for a reverse relation registered on the model."""
        from aksara.fields import ForeignKey
        from aksara.relations import RelationRegistry

        for relation in RelationRegistry.get_relations_to(self._model):
            if relation.related_name != relation_name:
                continue

            relation_alias = f"{relation_name}__rel"
            if relation.relation_type in ("fk", "o2o"):
                field = relation.source_model._fields.get(relation.field_name)
                if isinstance(field, ForeignKey):
                    fk_column = field.db_column_name
                else:
                    fk_column = f"{relation.field_name}_id"
                join_sql = (
                    f"LEFT JOIN {quote_identifier(relation.source_table)} AS {quote_identifier(relation_alias)} "
                    f"ON {self._qualified_column(relation_alias, fk_column)} = "
                    f"{self._qualified_column(self._model.__tablename__, 'id')}"
                )
                self._register_join(
                    join_state,
                    f"reverse_relation:{relation_name}",
                    relation_alias,
                    join_sql,
                )
                return relation_alias, relation.source_model

            if relation.relation_type == "m2m":
                through_alias = f"{relation_name}__through"
                m2m_field = relation.source_model._m2m_fields.get(relation.field_name)
                if m2m_field is None:
                    raise ValueError(
                        f"ManyToMany metadata for relation '{relation_name}' is not available"
                    )
                self._register_join(
                    join_state,
                    f"reverse_m2m_through:{relation_name}",
                    through_alias,
                    (
                        f"LEFT JOIN {quote_identifier(m2m_field.join_table_name)} AS {quote_identifier(through_alias)} "
                        f"ON {self._qualified_column(through_alias, m2m_field.target_column)} = "
                        f"{self._qualified_column(self._model.__tablename__, 'id')}"
                    ),
                )
                self._register_join(
                    join_state,
                    f"reverse_m2m_target:{relation_name}",
                    relation_alias,
                    (
                        f"LEFT JOIN {quote_identifier(relation.source_table)} AS {quote_identifier(relation_alias)} "
                        f"ON {self._qualified_column(relation_alias, 'id')} = "
                        f"{self._qualified_column(through_alias, m2m_field.source_column)}"
                    ),
                )
                return relation_alias, relation.source_model

        raise ValueError(f"Unknown relation reference: {relation_name}")

    def _resolve_aggregate_source(self, source: str, join_state: Dict[str, Any]) -> str:
        """Resolve a direct or one-hop relation aggregate source to SQL."""
        parts = source.split("__")
        if len(parts) > 2:
            raise ValueError(
                "Aggregate relation paths currently support one relation hop, "
                f"got '{source}'"
            )

        if len(parts) == 1 and (
            source == "id"
            or source in self._model._fields
            or source.endswith("_id")
        ):
            return self._base_column_reference(source)

        relation_name = parts[0]
        related_field_name = parts[1] if len(parts) == 2 else None

        if relation_name in self._model._m2m_fields:
            alias, related_model = self._ensure_forward_m2m_join(relation_name, join_state)
            return self._resolve_joined_field_column(related_model, alias, related_field_name)

        if relation_name in self._model._fk_fields:
            alias, related_model = self._ensure_forward_fk_join(relation_name, join_state)
            return self._resolve_joined_field_column(related_model, alias, related_field_name)

        alias, related_model = self._ensure_reverse_relation_join(relation_name, join_state)
        return self._resolve_joined_field_column(related_model, alias, related_field_name)

    def _compile_annotation_expression(
        self,
        expression: Any,
        values: List[Any],
        join_state: Dict[str, Any],
    ) -> str:
        """Compile an annotation or aggregate expression, registering joins when needed."""
        if isinstance(expression, Aggregate):
            if expression.source == "*":
                source_sql = "*"
            elif isinstance(expression.source, str):
                source_sql = self._resolve_aggregate_source(expression.source, join_state)
            else:
                source_sql = compile_expression(self._model, expression.source, values)

            distinct_sql = "DISTINCT " if expression.distinct and source_sql != "*" else ""
            return f"{expression.function_name}({distinct_sql}{source_sql})"

        return compile_expression(self._model, expression, values)

    def _compile_filter_condition(
        self,
        key: str,
        value: Any,
        values: List[Any],
        qualify_base: bool = False,
    ) -> str:
        """Compile a single filter condition to SQL."""
        from aksara.fields import Vector

        field_name, json_path, lookup = split_json_lookup(self._model, key)

        try:
            _model_field_name, field, _ = self._resolve_field_reference(field_name)
        except ValueError as exc:
            raise ValueError(f"Unknown field: {field_name}") from exc

        col_name = self._base_column_reference(field_name, qualify=qualify_base)

        if json_path:
            json_expr = col_name
            for segment in json_path[:-1]:
                values.append(segment)
                json_expr = f"{json_expr} -> ${len(values)}"

            values.append(json_path[-1])
            raw_expr = f"{json_expr} -> ${len(values)}"
            text_expr = f"{json_expr} ->> ${len(values)}"

            if lookup == "isnull":
                is_null = _parse_isnull_value(value)
                return f"{raw_expr} IS NULL" if is_null else f"{raw_expr} IS NOT NULL"

            if lookup in {"icontains", "contains"}:
                values.append(f"%{value}%")
                operator = "ILIKE" if lookup == "icontains" else "LIKE"
                return f"{text_expr} {operator} ${len(values)}"

            if lookup == "in":
                if not isinstance(value, (list, tuple, set)):
                    raise ValueError(f"__in lookup requires a list, got {type(value)}")
                if not value:
                    return "FALSE"
                placeholders = []
                for item in value:
                    values.append(_json_lookup_value(item))
                    placeholders.append(f"${len(values)}")
                return f"{text_expr} IN ({', '.join(placeholders)})"

            if lookup in {"gt", "gte", "lt", "lte"}:
                cast_type = _json_numeric_cast(value)
                if cast_type is None:
                    raise ValueError(
                        f"JSON path lookup '{lookup}' requires an int or float value"
                    )
                values.append(value)
                operator = LOOKUP_OPERATORS[lookup]
                return f"({text_expr})::{cast_type} {operator} ${len(values)}"

            values.append(_json_lookup_value(value))
            return f"{text_expr} = ${len(values)}"

        def _parameter(index: int) -> str:
            if isinstance(field, Vector):
                return f"CAST(${index} AS vector)"
            return f"${index}"

        if lookup == "exact":
            if value is None:
                return f"{col_name} IS NULL"
            if is_expression(value):
                return (
                    f"{col_name} = "
                    f"{compile_expression(self._model, value, values)}"
                )
            values.append(field.to_db(value))
            return f"{col_name} = {_parameter(len(values))}"

        if lookup == "gt":
            if is_expression(value):
                return f"{col_name} > {compile_expression(self._model, value, values)}"
            values.append(field.to_db(value))
            return f"{col_name} > {_parameter(len(values))}"

        if lookup == "gte":
            if is_expression(value):
                return f"{col_name} >= {compile_expression(self._model, value, values)}"
            values.append(field.to_db(value))
            return f"{col_name} >= {_parameter(len(values))}"

        if lookup == "lt":
            if is_expression(value):
                return f"{col_name} < {compile_expression(self._model, value, values)}"
            values.append(field.to_db(value))
            return f"{col_name} < {_parameter(len(values))}"

        if lookup == "lte":
            if is_expression(value):
                return f"{col_name} <= {compile_expression(self._model, value, values)}"
            values.append(field.to_db(value))
            return f"{col_name} <= {_parameter(len(values))}"

        if lookup == "in":
            if not isinstance(value, (list, tuple, set)):
                raise ValueError(f"__in lookup requires a list, got {type(value)}")
            if not value:
                return "FALSE"

            placeholders = []
            for item in value:
                values.append(field.to_db(item))
                placeholders.append(_parameter(len(values)))
            return f"{col_name} IN ({', '.join(placeholders)})"

        if lookup == "isnull":
            is_null = _parse_isnull_value(value)
            return f"{col_name} IS NULL" if is_null else f"{col_name} IS NOT NULL"

        if lookup == "icontains":
            if is_expression(value):
                raise ValueError("Expression values are not supported for __icontains lookups")
            values.append(f"%{value}%")
            return f"{col_name} ILIKE ${len(values)}"

        if lookup == "contains":
            if is_expression(value):
                raise ValueError("Expression values are not supported for __contains lookups")
            values.append(f"%{value}%")
            return f"{col_name} LIKE ${len(values)}"

        raise ValueError(f"Unknown lookup type: {lookup}")

    def _compile_q_object(
        self,
        q_object: Q,
        values: List[Any],
        qualify_base: bool = False,
    ) -> str:
        """Recursively compile a Q object tree into SQL."""
        parts = []

        for child in q_object.children:
            if isinstance(child, Q):
                child_sql = self._compile_q_object(child, values, qualify_base=qualify_base)
            else:
                child_sql = self._compile_filter_condition(
                    child[0],
                    child[1],
                    values,
                    qualify_base=qualify_base,
                )

            if child_sql:
                parts.append(child_sql)

        if not parts:
            return ""

        compiled = f" {q_object.connector} ".join(parts)
        if len(parts) > 1:
            compiled = f"({compiled})"
        if q_object.negated:
            compiled = f"NOT ({compiled})"
        return compiled

    def _build_where_clause(
        self,
        existing_values: Optional[List[Any]] = None,
        qualify_base: bool = False,
    ) -> Tuple[str, List[Any]]:
        """
        Build WHERE clause from filters and search conditions.
        
        Returns:
            Tuple of (WHERE clause string, parameter values list)
        """
        values = existing_values if existing_values is not None else []

        if (
            not self._filters
            and not self._q_objects
            and not self._search
            and self._soft_delete_mode in {None, "all"}
        ):
            return "", values

        conditions = []

        if self._soft_delete_mode in {"active", "deleted"}:
            deleted_column = self._base_column_reference(
                "deleted_at", qualify=qualify_base
            )
            null_operator = (
                "IS NULL" if self._soft_delete_mode == "active" else "IS NOT NULL"
            )
            conditions.append(f"{deleted_column} {null_operator}")

        for q_object in self._q_objects:
            q_sql = self._compile_q_object(q_object, values, qualify_base=qualify_base)
            if q_sql:
                conditions.append(q_sql)

        if self._filters:
            filter_conditions = [
                self._compile_filter_condition(key, value, values, qualify_base=qualify_base)
                for key, value in self._filters.items()
            ]
            if filter_conditions:
                compiled_filters = " AND ".join(filter_conditions)
                if len(filter_conditions) > 1:
                    compiled_filters = f"({compiled_filters})"
                conditions.append(compiled_filters)

        # Handle search condition (OR across multiple fields)
        if self._search:
            term, search_fields = self._search
            search_conditions = []
            
            for field_name in search_fields:
                if field_name not in self._model._fields:
                    raise ValueError(f"Unknown search field: {field_name}")
                
                col_name = self._base_column_reference(field_name, qualify=qualify_base)
                values.append(f"%{term}%")
                search_conditions.append(f"{col_name} ILIKE ${len(values)}")
                
            if search_conditions:
                conditions.append(f"({' OR '.join(search_conditions)})")
        
        return f"WHERE {' AND '.join(conditions)}", values

    def _build_select_clause(
        self,
        existing_values: Optional[List[Any]] = None,
        join_state: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[Any]]:
        """Build the SELECT clause including annotations when present."""
        values = existing_values if existing_values is not None else []
        if not self._annotations:
            return "*", values

        active_join_state = join_state or self._new_join_state()
        table = quote_identifier(self._model.__tablename__)
        select_parts = [f"{table}.*"]

        for alias, expression in self._annotations.items():
            select_parts.append(
                f"{self._compile_annotation_expression(expression, values, active_join_state)} AS {quote_identifier(alias)}"
            )

        return ", ".join(select_parts), values

    def _build_group_by_clause(self, join_state: Optional[Dict[str, Any]] = None) -> str:
        """Build a GROUP BY clause when annotations include aggregates."""
        if not any(isinstance(expression, Aggregate) for expression in self._annotations.values()):
            return ""

        qualify_base = bool(join_state and join_state["joins"])
        columns = [
            self._base_column_reference(field.name, qualify=qualify_base)
            for field in self._model._fields.values()
        ]
        return f"GROUP BY {', '.join(columns)}"
    
    def _build_order_by_clause(self, qualify_base: bool = False) -> str:
        """
        Build ORDER BY clause from ordering fields.
        
        Returns:
            ORDER BY clause string (empty if no ordering)
        """
        if not self._order_by:
            return ""
        
        order_parts = []
        for field in self._order_by:
            # Parse descending prefix
            if field.startswith("-"):
                field_name = field[1:]
                direction = "DESC"
            else:
                field_name = field
                direction = "ASC"
            
            # Get column name
            if field_name == "id":
                col_name = self._base_column_reference("id", qualify=qualify_base)
            elif field_name in self._model._fields:
                col_name = self._base_column_reference(field_name, qualify=qualify_base)
            elif field_name.endswith("_id"):
                # Check if it's a FK column name (e.g., author_id for FK field 'author')
                base_field_name = field_name[:-3]
                if base_field_name in self._model._fields:
                    col_name = self._base_column_reference(field_name, qualify=qualify_base)
                else:
                    col_name = quote_identifier(field_name)  # Fallback
            else:
                col_name = quote_identifier(field_name)  # Fallback (should have been validated)
            
            order_parts.append(f"{col_name} {direction}")
        
        return f"ORDER BY {', '.join(order_parts)}"
    
    def _build_limit_offset_clause(self, values: List[Any]) -> str:
        """Append limit/offset parameters and produce the SQL clause."""
        parts: List[str] = []
        if self._limit_value is not None:
            values.append(self._limit_value)
            parts.append(f"LIMIT ${len(values)}")
        if self._offset_value is not None:
            values.append(self._offset_value)
            parts.append(f"OFFSET ${len(values)}")
        return " ".join(parts)

    def _build_select_query(self, *, override_select: Optional[str] = None) -> Tuple[str, List[Any]]:
        """Build the full SELECT query and parameter list."""
        join_state = self._new_join_state()
        if override_select is None:
            select_clause, values = self._build_select_clause(join_state=join_state)
        else:
            select_clause = override_select
            values = []
        join_clause = self._build_join_clause(join_state)
        qualify_base = bool(join_state["joins"])
        where_clause, values = self._build_where_clause(values, qualify_base=qualify_base)
        group_by_clause = (
            self._build_group_by_clause(join_state) if override_select is None else ""
        )
        order_by_clause = self._build_order_by_clause(qualify_base=qualify_base)
        limit_clause = self._build_limit_offset_clause(values)
        table = quote_identifier(self._model.__tablename__)
        query = self._assemble_query(
            f"SELECT {select_clause}",
            f"FROM {table}",
            join_clause,
            where_clause,
            group_by_clause,
            order_by_clause,
            limit_clause,
        )
        return query, values

    async def all(self) -> List[T]:
        """
        Execute the query and return all matching records.

        Returns:
            List of model instances
        """
        from aksara.db import Database

        db = Database.get_instance()
        query, values = self._build_select_query()
        records = await db.fetch(query, *values)
        
        instances = [self._model._from_record(record) for record in records]
        
        # Handle select_related - batch load FK/O2O relations
        if self._select_related and instances:
            await self._load_select_related(instances, db)
        
        # Handle prefetch_related - batch load M2M relations
        if self._prefetch_related and instances:
            await self._load_prefetch_related(instances, db)
        
        return instances
    
    async def _load_select_related(self, instances: List[T], db) -> None:
        """
        Batch load FK/O2O related objects for all instances.

        Fires all FK queries concurrently via asyncio.gather() — one query per
        related field rather than one query per field per instance.
        """
        import asyncio

        async def _load_one(field_name: str) -> None:
            if field_name not in self._model._fk_fields:
                raise ValueError(
                    f"select_related: '{field_name}' is not a ForeignKey/OneToOne field "
                    f"on {self._model.__name__}"
                )

            field = self._model._fk_fields[field_name]
            related_model = field.to_model

            fk_ids = {
                fk_id
                for instance in instances
                if (fk_id := instance._data.get(field_name)) is not None
            }

            if not fk_ids:
                for instance in instances:
                    instance._prefetched_relations[field_name] = None
                return

            placeholders = ", ".join(f"${i+1}" for i in range(len(fk_ids)))
            related_table = quote_identifier(related_model.__tablename__)
            related_query = f"SELECT * FROM {related_table} WHERE id IN ({placeholders})"

            related_records = await db.fetch(related_query, *list(fk_ids))

            related_map = {}
            for rec in related_records:
                related_instance = related_model._from_record(rec)
                related_map[related_instance.id] = related_instance

            for instance in instances:
                fk_id = instance._data.get(field_name)
                instance._prefetched_relations[field_name] = related_map.get(fk_id)

        await asyncio.gather(*(_load_one(fn) for fn in self._select_related))
    
    async def _load_prefetch_related(self, instances: List[T], db) -> None:
        """
        Batch load M2M related objects for all instances.
        
        For each prefetch_related field:
        1. Collect all source IDs
        2. Query through table with JOIN
        3. Build a mapping {source_id: [related_instances]}
        4. Attach to each instance._prefetched_relations
        """
        for field_name in self._prefetch_related:
            # Validate field exists and is M2M
            if field_name not in self._model._m2m_fields:
                raise ValueError(
                    f"prefetch_related: '{field_name}' is not a ManyToMany field "
                    f"on {self._model.__name__}"
                )
            
            m2m_field = self._model._m2m_fields[field_name]
            related_model = m2m_field.to_model
            join_table = m2m_field.join_table_name
            
            # Get column names for join table
            from aksara.fields import _singularize

            source_table = self._model.__tablename__
            target_table = related_model.__tablename__

            source_col = f"{_singularize(source_table)}_id"
            target_col = f"{_singularize(target_table)}_id"
            
            # Collect all source IDs
            source_ids = [instance.id for instance in instances]
            
            if not source_ids:
                continue
            
            # Batch query - join through table with target table
            placeholders = ", ".join(f"${i+1}" for i in range(len(source_ids)))
            m2m_query = f"""
                SELECT j.{source_col}, t.*
                FROM {join_table} j
                INNER JOIN {target_table} t ON t.id = j.{target_col}
                WHERE j.{source_col} IN ({placeholders})
            """
            
            records = await db.fetch(m2m_query, *source_ids)
            
            # Build mapping {source_id: [related_instances]}
            related_map: Dict[Any, List] = {sid: [] for sid in source_ids}
            for record in records:
                source_id = record[source_col]
                # Create instance from record (excluding the source_col)
                related_instance = related_model._from_record(record)
                related_map[source_id].append(related_instance)
            
            # Attach to each instance
            for instance in instances:
                instance._prefetched_relations[field_name] = related_map.get(instance.id, [])
    
    async def fetch_with_count(self) -> Tuple[List[T], int]:
        """
        Fetch matching rows along with the total count in a single query.

        Uses PostgreSQL's ``COUNT(*) OVER()`` window function so pagination
        endpoints can avoid issuing a separate ``SELECT COUNT(*)`` query.

        Returns:
            Tuple ``(instances, total_count)`` where ``total_count`` reflects
            the unpaginated row count for the current filters.
        """
        from aksara.db import Database

        db = Database.get_instance()

        # Build the query with COUNT(*) OVER() appended to the SELECT list.
        join_state = self._new_join_state()
        select_clause, values = self._build_select_clause(join_state=join_state)
        select_clause = f"{select_clause}, COUNT(*) OVER() AS _total_count"
        join_clause = self._build_join_clause(join_state)
        qualify_base = bool(join_state["joins"])
        where_clause, values = self._build_where_clause(values, qualify_base=qualify_base)
        group_by_clause = self._build_group_by_clause(join_state)
        order_by_clause = self._build_order_by_clause(qualify_base=qualify_base)
        limit_clause = self._build_limit_offset_clause(values)
        table = quote_identifier(self._model.__tablename__)
        query = self._assemble_query(
            f"SELECT {select_clause}",
            f"FROM {table}",
            join_clause,
            where_clause,
            group_by_clause,
            order_by_clause,
            limit_clause,
        )

        records = await db.fetch(query, *values)

        if not records:
            # No rows in this page — fall back to a plain COUNT for the total.
            total = await self.count()
            return [], total

        total = int(records[0]["_total_count"])
        instances = [self._model._from_record(record) for record in records]

        if self._select_related and instances:
            await self._load_select_related(instances, db)
        if self._prefetch_related and instances:
            await self._load_prefetch_related(instances, db)

        return instances, total

    async def first(self) -> Optional[T]:
        """
        Execute the query and return the first matching record.

        Returns:
            First matching model instance or None
        """
        from aksara.db import Database

        db = Database.get_instance()
        # Force LIMIT 1 for first()
        query, values = self._clone(limit_value=1)._build_select_query()
        record = await db.fetchrow(query, *values)

        if record is None:
            return None

        instance = self._model._from_record(record)
        instances = [instance]
        if self._select_related:
            await self._load_select_related(instances, db)
        if self._prefetch_related:
            await self._load_prefetch_related(instances, db)
        return instance

    async def count(self) -> int:
        """
        Execute the query and return the count of matching records.

        Returns:
            Number of matching records
        """
        from aksara.db import Database

        db = Database.get_instance()

        where_clause, values = self._build_where_clause()
        table = quote_identifier(self._model.__tablename__)
        query = self._assemble_query(
            f"SELECT COUNT(*) FROM {table}",
            where_clause,
        )

        count = await db.fetchval(query, *values)

        return count or 0

    async def exists(self) -> bool:
        """
        Check if any matching records exist.

        Uses ``SELECT 1 ... LIMIT 1`` so PostgreSQL can stop at the first
        matching row instead of scanning to compute COUNT(*).

        Returns:
            True if at least one record matches, False otherwise
        """
        from aksara.db import Database

        db = Database.get_instance()

        where_clause, values = self._build_where_clause()
        table = quote_identifier(self._model.__tablename__)
        query = self._assemble_query(
            f"SELECT 1 FROM {table}",
            where_clause,
            "LIMIT 1",
        )

        value = await db.fetchval(query, *values)
        return value is not None
    
    async def delete(self) -> int:
        """
        Delete all matching records.

        Returns:
            Number of deleted records
        """
        from aksara.db import Database

        db = Database.get_instance()

        where_clause, values = self._build_where_clause()
        table = quote_identifier(self._model.__tablename__)
        query = self._assemble_query(f"DELETE FROM {table}", where_clause)

        result = await db.execute(query, *values)

        # Parse "DELETE X" to get count
        try:
            return int(result.split()[-1])
        except (IndexError, ValueError):
            return 0

    async def update(self, **kwargs: Any) -> int:
        """Update all rows in the queryset, supporting F expressions."""
        from aksara.db import Database

        if not kwargs:
            raise ValueError("update() requires at least one field assignment")

        assignments = dict(kwargs)
        auto_now_fields = [
            name
            for name, field in self._model._fields.items()
            if getattr(field, "auto_now", False)
        ]
        auto_now_field_set = set(auto_now_fields)
        updates_non_auto_field = any(name not in auto_now_field_set for name in assignments)
        if auto_now_fields and updates_non_auto_field:
            now = datetime.now(timezone.utc)
            for field_name in auto_now_fields:
                assignments.setdefault(field_name, now)

        values: List[Any] = []
        set_clauses = []

        for field_name, value in assignments.items():
            if field_name not in self._model._fields:
                raise ValueError(f"Unknown field: {field_name}")

            field = self._model._fields[field_name]
            col_name = quote_identifier(field.column_name)
            if is_expression(value):
                set_clauses.append(f"{col_name} = {compile_expression(self._model, value, values)}")
            else:
                values.append(field.to_db(value))
                if _is_vector_field(field):
                    set_clauses.append(f"{col_name} = CAST(${len(values)} AS vector)")
                else:
                    set_clauses.append(f"{col_name} = ${len(values)}")

        where_clause, values = self._build_where_clause(values)
        table = quote_identifier(self._model.__tablename__)
        query = self._assemble_query(
            f"UPDATE {table} SET {', '.join(set_clauses)}",
            where_clause,
        )

        db = Database.get_instance()
        result = await db.execute(query, *values)

        try:
            return int(result.split()[-1])
        except (IndexError, ValueError):
            return 0

    async def aggregate(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute aggregate expressions and return a summary dictionary."""
        from aksara.db import Database

        if not kwargs:
            raise ValueError("aggregate() requires at least one named aggregate")

        values: List[Any] = []
        join_state = self._new_join_state()
        select_parts = []
        for alias, expression in kwargs.items():
            if not isinstance(expression, Aggregate):
                raise ValueError("aggregate() values must be Aggregate instances")
            select_parts.append(
                f"{self._compile_annotation_expression(expression, values, join_state)} AS {quote_identifier(alias)}"
            )

        qualify_base = bool(join_state["joins"])
        join_clause = self._build_join_clause(join_state)
        where_clause, values = self._build_where_clause(values, qualify_base=qualify_base)
        table = quote_identifier(self._model.__tablename__)
        query = self._assemble_query(
            f"SELECT {', '.join(select_parts)}",
            f"FROM {table}",
            join_clause,
            where_clause,
        )

        db = Database.get_instance()
        row = await db.fetchrow(query, *values)
        if row is None:
            return {alias: None for alias in kwargs}
        return dict(row)


class Manager(Generic[T]):
    """
    Manager class attached to each Model for querying.
    
    Accessed via Model.objects, provides the entry point for all queries.
    
    Usage:
        # Create a new record
        user = await User.objects.create(email="test@example.com")
        
        # Get a specific record
        user = await User.objects.get(id=user_id)
        
        # Filter records
        users = await User.objects.filter(is_active=True).all()
    """
    
    def __init__(self, model: Type[T]):
        """
        Initialize the manager.
        
        Args:
            model: The model class this manager is attached to
        """
        self._model = model
    
    def _soft_delete_active(self) -> bool:
        """Return True when the model opts into soft-delete handling."""
        return (
            getattr(self._model, '_soft_delete_enabled', False)
            and 'deleted_at' in self._model._fields
        )

    def _apply_soft_delete(self, qs: QuerySet[T]) -> QuerySet[T]:
        """Apply the soft-delete filter to a queryset based on its mode flags."""
        if not self._soft_delete_active():
            return qs
        if qs._soft_delete_mode is None:
            return qs._clone(soft_delete_mode="active")
        return qs

    def filter(self, *args: Q, **kwargs) -> QuerySet[T]:
        """
        Create a QuerySet with the given filters.

        For SoftDeleteModel subclasses, automatically excludes soft-deleted records
        unless specifically requested via with_deleted().

        Args:
            **kwargs: Field=value conditions

        Returns:
            QuerySet for chaining
        """
        qs = QuerySet(self._model).filter(*args, **kwargs)
        return self._apply_soft_delete(qs)

    def with_deleted(self) -> QuerySet[T]:
        """Start a queryset that includes soft-deleted records."""
        return QuerySet(self._model).with_deleted()

    def only_deleted(self) -> QuerySet[T]:
        """Start a queryset that only contains soft-deleted records."""
        return QuerySet(self._model).only_deleted()
    
    def search(self, term: str, fields: List[str]) -> QuerySet[T]:
        """
        Create a QuerySet with a search condition.

        Routes through filter() so SoftDeleteModel excludes soft-deleted rows.
        """
        return self.filter().search(term, fields)

    def annotate(self, **kwargs: Any) -> QuerySet[T]:
        """Create a QuerySet with annotations.

        Routes through filter() so SoftDeleteModel excludes soft-deleted rows.
        """
        return self.filter().annotate(**kwargs)

    async def aggregate(self, **kwargs: Any) -> Dict[str, Any]:
        """Execute aggregate expressions for the model.

        Routes through filter() so SoftDeleteModel excludes soft-deleted rows.
        """
        return await self.filter().aggregate(**kwargs)

    def order_by(self, *fields: str) -> QuerySet[T]:
        """
        Create a QuerySet with ordering.

        Routes through filter() so SoftDeleteModel excludes soft-deleted rows.
        """
        return self.filter().order_by(*fields)

    def select_related(self, *fields: str) -> QuerySet[T]:
        """
        Create a QuerySet with select_related fields.

        Routes through filter() so SoftDeleteModel excludes soft-deleted rows.
        """
        return self.filter().select_related(*fields)

    def prefetch_related(self, *fields: str) -> QuerySet[T]:
        """
        Create a QuerySet with prefetch_related fields.

        Routes through filter() so SoftDeleteModel excludes soft-deleted rows.
        """
        return self.filter().prefetch_related(*fields)
    
    async def all(self) -> List[T]:
        """
        Get all records.

        Routes through ``self.filter()`` so SoftDeleteModel automatically
        excludes soft-deleted rows.

        Returns:
            List of all model instances
        """
        return await self.filter().all()
    
    async def create(self, **kwargs) -> T:
        """
        Create and save a new model instance.
        
        Args:
            **kwargs: Field values for the new instance
            
        Returns:
            The created model instance
        """
        instance = self._model(**kwargs)
        await instance.save()
        return instance
    
    async def get(self, *args: Q, **kwargs) -> T:
        """
        Get a single record matching the given conditions.

        Args:
            **kwargs: Field=value conditions

        Returns:
            The matching model instance

        Raises:
            DoesNotExist: If no matching record is found
            MultipleObjectsReturned: If multiple records match
        """
        # Use LIMIT 2 so we can detect "more than one" without scanning every
        # matching row.
        queryset = self.filter(*args, **kwargs).limit(2)
        results = await queryset.all()

        if not results:
            raise DoesNotExist(f"{self._model.__name__} matching query does not exist")

        if len(results) > 1:
            raise MultipleObjectsReturned(
                f"get() returned more than one {self._model.__name__} instance, expected 1"
            )

        return results[0]
    
    async def get_or_none(self, *args: Q, **kwargs) -> Optional[T]:
        """
        Get a single record or None if not found.

        Args:
            **kwargs: Field=value conditions

        Returns:
            The matching model instance or None
        """
        return await self.filter(*args, **kwargs).first()

    async def update(self, **kwargs: Any) -> int:
        """Update all rows for this model.

        Routes through filter() so SoftDeleteModel excludes soft-deleted rows.
        """
        return await self.filter().update(**kwargs)
    
    async def get_or_create(self, defaults: Optional[Dict[str, Any]] = None, **kwargs) -> tuple[T, bool]:
        """
        Get an existing record or create a new one.
        
        Args:
            defaults: Field values to use when creating
            **kwargs: Field=value conditions for lookup
            
        Returns:
            Tuple of (instance, created) where created is True if new
        """
        try:
            instance = await self.get(**kwargs)
            return instance, False
        except DoesNotExist:
            create_kwargs = {**kwargs, **(defaults or {})}
            instance = await self.create(**create_kwargs)
            return instance, True

    async def _prepare_bulk_create_objects(self, objs: List[T]) -> None:
        """Apply save-path preparation and auto_now timestamps before bulk insert."""
        from aksara.db.expressions import is_expression

        for obj in objs:
            for field_name in self._model._fields:
                if is_expression(obj._data.get(field_name)):
                    raise ValueError("Expressions are not supported in bulk_create()")

            for field_name, field in self._model._async_prepare_fields.items():
                obj._data[field_name] = await field.async_prepare(
                    obj._data.get(field_name),
                    instance=obj,
                )

            for field in self._model._generic_fk_fields.values():
                await field.async_prepare(obj)

            await obj._validate_fields()

        now = datetime.now(timezone.utc)
        for obj in objs:
            for field_name, field in self._model._fields.items():
                if getattr(field, "auto_now", False):
                    obj._data[field_name] = now

    def _bulk_create_field_names(self, batch: List[T]) -> List[str]:
        """Return the DB insert field set after all batch rows are prepared."""
        field_names = []
        for field_name, field in self._model._fields.items():
            values = [obj._data.get(field_name) for obj in batch]

            if field_name == "id" and all(value is None for value in values):
                continue
            if getattr(field, "auto_now_add", False) and all(value is None for value in values):
                continue

            if any(value is not None for value in values) or getattr(field, "nullable", False):
                field_names.append(field_name)

        return field_names

    def _bulk_create_value_sql(
        self,
        field_name: str,
        field: Any,
        value: Any,
        param_idx: int,
    ) -> tuple[str, bool]:
        """Return the SQL token for a bulk-create value and whether it binds a param."""
        if value is None and (
            field_name == "id"
            or getattr(field, "auto_now_add", False)
        ):
            return "DEFAULT", False

        if _is_vector_field(field):
            return f"CAST(${param_idx} AS vector)", True
        return f"${param_idx}", True

    def _hydrate_bulk_created_object(self, obj: T, record: Any) -> None:
        """Update the caller's object with all columns returned by INSERT."""
        from aksara.fields import ForeignKey

        record_keys = set(record.keys())
        for field_name, field in self._model._fields.items():
            if isinstance(field, ForeignKey):
                col_name = field.db_column_name
                if col_name in record_keys:
                    obj._data[field_name] = field.to_python(record[col_name])
            elif field_name in record_keys:
                obj._data[field_name] = field.to_python(record[field_name])
        obj._is_new = False
    
    async def bulk_create(
        self,
        objs: List[T],
        batch_size: int = 1000,
        ignore_conflicts: bool = False,
    ) -> List[T]:
        """
        Bulk insert multiple model instances.
        
        v0.5.39: Initial implementation.
        
        Efficiently inserts many records in batches, much faster than
        calling create() in a loop.
        
        Args:
            objs: List of unsaved model instances
            batch_size: Number of records to insert per batch (default: 1000)
            ignore_conflicts: If True, silently skip conflicts (ON CONFLICT DO NOTHING)
                             If False, raise on duplicate keys
            
        Returns:
            List of inserted model instances with IDs populated
            
        Raises:
            ValueError: If objs is empty or contains saved instances
            
        Usage:
            users_to_create = [User(email=f"user{i}@example.com") for i in range(10000)]
            created_users = await User.objects.bulk_create(users_to_create, batch_size=1000)
        """
        from aksara.db import Database
        
        if not objs:
            return []
        
        # Validate all instances are new (not saved)
        for obj in objs:
            if not obj._is_new:
                raise ValueError("bulk_create() requires unsaved model instances")

        await self._prepare_bulk_create_objects(objs)
        
        db = Database.get_instance()
        created_instances = []
        
        # Process in batches
        for batch_start in range(0, len(objs), batch_size):
            batch = objs[batch_start : batch_start + batch_size]
            
            # Build multi-row INSERT statement
            field_names = self._bulk_create_field_names(batch)
            all_values = []
            placeholders = []
            param_idx = 1
            
            for obj in batch:
                row_placeholders = []
                
                for field_name in field_names:
                    field = self._model._fields[field_name]
                    value = obj._data.get(field_name)
                    value_sql, binds_param = self._bulk_create_value_sql(
                        field_name,
                        field,
                        value,
                        param_idx,
                    )
                    row_placeholders.append(value_sql)
                    if binds_param:
                        all_values.append(field.to_db(value))
                        param_idx += 1
                
                placeholders.append(f"({', '.join(row_placeholders)})")
            
            # Build the INSERT statement using each field's DB column name
            # (e.g. ForeignKey "owner" → column "owner_id"), not the Python
            # field name.
            columns = ", ".join(
                quote_identifier(self._model._fields[f].column_name)
                for f in field_names
            )
            values_clause = ", ".join(placeholders)
            table = quote_identifier(self._model.__tablename__)
            
            conflict_clause = ""
            if ignore_conflicts:
                conflict_clause = " ON CONFLICT DO NOTHING"
            
            query = f"""
                INSERT INTO {table} ({columns})
                VALUES {values_clause}
                {conflict_clause}
                RETURNING *
            """
            
            records = await db.fetch(query, *all_values)
            
            # Hydrate original objects when PostgreSQL returned one row per
            # input object. With ignore_conflicts=True PostgreSQL may return
            # fewer rows, and the skipped input rows cannot be matched safely.
            if len(records) == len(batch):
                for obj, record in zip(batch, records):
                    self._hydrate_bulk_created_object(obj, record)
                    created_instances.append(obj)
            else:
                for record in records:
                    instance = self._model._from_record(record)
                    created_instances.append(instance)
        
        return created_instances
    
    async def bulk_update(
        self,
        objs: List[T],
        fields: List[str],
        batch_size: int = 1000,
    ) -> int:
        """
        Bulk update multiple model instances.
        
        v0.5.39: Initial implementation.
        
        Efficiently updates many records in batches.
        
        Args:
            objs: List of saved model instances to update
            fields: List of field names to update
            batch_size: Number of records to update per batch
            
        Returns:
            Total number of records updated
            
        Raises:
            ValueError: If objs is empty, contains unsaved instances, or fields is empty
            
        Usage:
            users = await User.objects.filter(is_active=False).all()
            for user in users:
                user.updated_at = datetime.now()
            
            await User.objects.bulk_update(users, fields=['updated_at'], batch_size=1000)
        """
        from aksara.db import Database
        from aksara.db.expressions import is_expression
        
        if not objs or not fields:
            raise ValueError("bulk_update() requires non-empty objs and fields lists")
        
        # Validate all instances are saved
        for obj in objs:
            if obj._is_new:
                raise ValueError("bulk_update() requires saved model instances")
        
        db = Database.get_instance()
        updated_count = 0
        
        # Process in batches
        for batch_start in range(0, len(objs), batch_size):
            batch = objs[batch_start : batch_start + batch_size]
            
            # Build multi-row UPDATE using CASE statements
            # Example: UPDATE users SET email = CASE WHEN id = $1 THEN $2 ... END
            case_statements = {}
            ids = []
            param_idx = 1
            
            for field_name in fields:
                if field_name not in self._model._fields:
                    raise ValueError(f"Unknown field: {field_name}")
                
                field = self._model._fields[field_name]
                when_clauses = []
                
                for obj in batch:
                    # Searched CASE requires a boolean WHEN expression — must
                    # compare the primary key column to the parameter, not just
                    # bind the PK value as the condition.
                    value_sql = _typed_parameter(field, param_idx + 1)
                    when_clauses.append(
                        f"WHEN {quote_identifier('id')} = ${param_idx} THEN {value_sql}"
                    )
                    ids.append(obj.id)
                    value = obj._data.get(field_name)
                    if is_expression(value):
                        raise ValueError("Expressions are not supported in bulk_update()")
                    ids.append(field.to_db(value))
                    param_idx += 2

                col_name = quote_identifier(field.column_name)
                case_statements[col_name] = " ".join(when_clauses)
            
            # Build the UPDATE statement
            set_clause = ", ".join(
                f"{col_name} = CASE {case_stmt} END"
                for col_name, case_stmt in case_statements.items()
            )
            
            # Append the WHERE id parameters after the CASE parameters so the
            # IN list references exactly the distinct primary keys for this
            # batch (no duplicate / dead parameters).
            where_ids = [obj.id for obj in batch]
            where_start = len(ids) + 1
            id_placeholders = ", ".join(
                f"${where_start + i}" for i in range(len(where_ids))
            )
            table = quote_identifier(self._model.__tablename__)

            query = f"""
                UPDATE {table}
                SET {set_clause}
                WHERE id IN ({id_placeholders})
            """

            result = await db.execute(query, *ids, *where_ids)
            
            # Parse result to get count
            try:
                updated_count += int(result.split()[-1])
            except (IndexError, ValueError):
                pass
        
        return updated_count
    
    async def upsert(
        self,
        defaults: Optional[Dict[str, Any]] = None,
        update_fields: Optional[List[str]] = None,
        **kwargs,
    ) -> tuple[T, bool]:
        """
        Upsert (insert or update) a record using PostgreSQL ON CONFLICT.
        
        v0.5.39: Initial implementation.
        
        Uses the model's unique constraints to determine conflict handling.
        If a unique constraint is violated, updates the specified fields
        instead of inserting.
        
        Args:
            defaults: Field values to use when creating or updating
            update_fields: List of field names to update on conflict
                          If None, all fields from defaults are updated
            **kwargs: Field values for matching/creating (used as unique key)
            
        Returns:
            Tuple of (instance, created) where created is True if inserted
            
        Raises:
            ValueError: If no unique constraint matches the upsert keys
            
        Usage:
            # Insert or update by email (assuming email is unique)
            user, created = await User.objects.upsert(
                email="john@example.com",
                defaults={'name': 'John', 'is_active': True},
                update_fields=['name', 'updated_at']
            )
        """
        from aksara.db import Database
        from aksara.db.expressions import is_expression
        
        defaults = defaults or {}
        db = Database.get_instance()

        # Determine which fields to update
        if update_fields is None:
            update_fields = list(defaults.keys())

        # Build INSERT statement with DO UPDATE
        insert_fields = list(kwargs.keys()) + list(defaults.keys())
        insert_values = []
        # Resolve each insert field to its actual DB column name (FKs map
        # "owner" → "owner_id") and run values through field.to_db() so
        # serializers like JSON.to_db() apply before asyncpg receives them.
        insert_columns = []
        for field_name in insert_fields:
            value = kwargs[field_name] if field_name in kwargs else defaults.get(field_name)
            if is_expression(value):
                raise ValueError("Expressions are not supported in upsert() insert values")
            if field_name not in self._model._fields:
                raise ValueError(f"Unknown field: {field_name}")
            field = self._model._fields[field_name]
            insert_columns.append(field.column_name)
            insert_values.append(field.to_db(value))

        placeholders = [f"${i+1}" for i in range(len(insert_values))]
        columns = ", ".join(quote_identifier(c) for c in insert_columns)
        values = ", ".join(placeholders)

        # Find a unique constraint to use for conflict detection
        unique_constraint_fields = list(kwargs.keys())

        # Build the ON CONFLICT clause using DB column names so ForeignKey
        # conflict targets reference the real column (e.g. "owner_id").
        conflict_columns = [
            self._model._fields[f].column_name for f in unique_constraint_fields
        ]
        conflict_fields = ", ".join(quote_identifier(c) for c in conflict_columns)

        # Build the UPDATE clause
        update_clauses = []
        for field_name in update_fields:
            if field_name not in self._model._fields:
                raise ValueError(f"Unknown field: {field_name}")

            field = self._model._fields[field_name]
            col_name = quote_identifier(field.column_name)

            # Use the value from defaults if provided
            if field_name in defaults:
                idx = insert_fields.index(field_name) + 1
                update_clauses.append(f"{col_name} = ${idx}")
            else:
                update_clauses.append(f"{col_name} = EXCLUDED.{col_name}")

        table = quote_identifier(self._model.__tablename__)

        # ``DO UPDATE SET`` with no assignments is invalid SQL. When the
        # caller passes only conflict keys (no defaults / update_fields),
        # fall back to the canonical no-op assignment ``conflict_col =
        # EXCLUDED.conflict_col`` so the statement stays valid and
        # ``RETURNING *`` still surfaces the existing row.
        if not update_clauses:
            noop_col = quote_identifier(conflict_columns[0])
            update_clauses.append(f"{noop_col} = EXCLUDED.{noop_col}")

        update_sql = ", ".join(update_clauses)

        query = f"""
            INSERT INTO {table} ({columns})
            VALUES ({values})
            ON CONFLICT ({conflict_fields})
            DO UPDATE SET {update_sql}
            RETURNING *, (xmax = 0) AS _is_created
        """

        record: Any = await db.fetchrow(query, *insert_values)
        instance = self._model._from_record(record)
        created = bool(record["_is_created"])

        return instance, created
    
    async def count(self) -> int:
        """
        Count all records.

        Routes through ``self.filter()`` so SoftDeleteModel automatically
        excludes soft-deleted rows.

        Returns:
            Total number of records
        """
        return await self.filter().count()


class DoesNotExist(Exception):
    """Raised when a query returns no results."""
    pass


class MultipleObjectsReturned(Exception):
    """Raised when get() returns multiple results."""
    pass
