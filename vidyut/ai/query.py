"""
AI Query Assistant for Vidyut.

This module provides canonical structures for AI-generated query plans
and an executor to apply them against the Vidyut ORM.

The design is provider-agnostic: LLMs produce AiQueryPlan JSON,
Vidyut executes it deterministically.

v0.4.2: Initial release
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Type, TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from vidyut.exceptions import ConfigurationError
from vidyut.registry import ModelRegistry

if TYPE_CHECKING:
    from vidyut.model.base import Model


# =============================================================================
# Type Aliases
# =============================================================================

SortDirection = Literal["asc", "desc"]


# =============================================================================
# Supported Lookups
# =============================================================================

SUPPORTED_LOOKUPS = {
    "exact",      # field = value
    "gt",         # field > value
    "gte",        # field >= value
    "lt",         # field < value
    "lte",        # field <= value
    "in",         # field IN (values)
    "isnull",     # field IS NULL / IS NOT NULL
    "icontains",  # ILIKE %value%
    "contains",   # LIKE %value%
}


# =============================================================================
# Pydantic Models - Query Plan Structure
# =============================================================================


class AiFilterCondition(BaseModel):
    """A single filter condition for a query."""
    
    field: str = Field(..., description="Field name, e.g., 'email', 'created_at', 'is_active'")
    lookup: str = Field(
        default="exact",
        description="Lookup type: 'exact', 'icontains', 'gte', 'lte', 'in', 'isnull', etc."
    )
    value: Any = Field(..., description="JSON-serializable filter value")
    
    model_config = {"extra": "forbid"}


class AiSortField(BaseModel):
    """A single sort specification."""
    
    field: str = Field(..., description="Field name to sort by")
    direction: SortDirection = Field(default="asc", description="Sort direction: 'asc' or 'desc'")
    
    model_config = {"extra": "forbid"}


class AiQueryPagination(BaseModel):
    """Pagination settings for a query."""
    
    limit: int = Field(default=50, ge=1, le=500, description="Maximum rows to return (1-500)")
    offset: int = Field(default=0, ge=0, description="Number of rows to skip")
    
    model_config = {"extra": "forbid"}


class AiQueryPlan(BaseModel):
    """
    Canonical representation of a read-only query against a single model.
    
    This is what LLMs should produce when translating natural language
    queries into structured query plans.
    
    Example:
        {
            "model": "User",
            "filters": [
                {"field": "is_active", "lookup": "exact", "value": true},
                {"field": "email", "lookup": "icontains", "value": "@gmail.com"}
            ],
            "sorting": [{"field": "created_at", "direction": "desc"}],
            "pagination": {"limit": 20, "offset": 0}
        }
    """
    
    model: str = Field(..., description="Model name, e.g., 'User' or 'myapp.User'")
    filters: List[AiFilterCondition] = Field(
        default_factory=list,
        description="List of filter conditions (combined with AND)"
    )
    sorting: List[AiSortField] = Field(
        default_factory=list,
        description="List of sort specifications (applied in order)"
    )
    pagination: AiQueryPagination = Field(
        default_factory=AiQueryPagination,
        description="Pagination settings"
    )
    select_fields: Optional[List[str]] = Field(
        default=None,
        description="Subset of fields to include in results (None = all fields)"
    )
    debug_notes: Optional[str] = Field(
        default=None,
        description="Optional explanation from the AI about the query plan"
    )
    
    model_config = {"extra": "forbid"}


class AiQueryRequest(BaseModel):
    """
    A natural language query request.
    
    This is what users/adapters provide to LLMs along with schema context.
    The LLM then produces an AiQueryPlan.
    """
    
    natural_language: str = Field(..., description="The user's natural language query")
    model: Optional[str] = Field(default=None, description="Optional target model hint")
    max_results: int = Field(default=50, ge=1, le=500, description="Maximum results to return")
    app_label: Optional[str] = Field(default=None, description="Optional app label for context")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context metadata"
    )
    
    model_config = {"extra": "forbid"}


class AiQueryResult(BaseModel):
    """Result of executing an AiQueryPlan."""
    
    plan: AiQueryPlan = Field(..., description="The executed query plan")
    rows: List[Dict[str, Any]] = Field(..., description="Query result rows as dictionaries")
    count: int = Field(..., description="Number of rows returned")
    limited: bool = Field(
        default=False,
        description="True if results were limited by pagination"
    )
    
    model_config = {"extra": "forbid"}


# =============================================================================
# Query Executor
# =============================================================================


def _resolve_model(model_name: str) -> Type["Model"]:
    """
    Resolve a model name to its class.
    
    Supports:
        - Simple name: "User"
        - Qualified name: "myapp.User"
    
    Args:
        model_name: The model name to resolve.
        
    Returns:
        The model class.
        
    Raises:
        ConfigurationError: If model not found.
    """
    # Try direct lookup first
    try:
        return ModelRegistry.get(model_name)
    except KeyError:
        pass
    
    # Try qualified name (e.g., "myapp.User" -> "User")
    if "." in model_name:
        simple_name = model_name.rsplit(".", 1)[-1]
        try:
            return ModelRegistry.get(simple_name)
        except KeyError:
            pass
    
    # Model not found - provide helpful error
    available = sorted(ModelRegistry.all().keys())
    raise ConfigurationError(
        f"Model '{model_name}' not found in registry. "
        f"Available models: {', '.join(available) if available else '(none registered)'}"
    )


def _validate_field(model: Type["Model"], field_name: str) -> None:
    """
    Validate that a field exists on the model.
    
    Args:
        model: The model class.
        field_name: The field name to validate.
        
    Raises:
        ConfigurationError: If field doesn't exist.
    """
    # Check 'id' (always present)
    if field_name == "id":
        return
    
    # Check model fields
    if field_name in model._fields:
        return
    
    # Check FK column names (e.g., author_id)
    if field_name.endswith("_id"):
        base_name = field_name[:-3]
        if base_name in model._fields:
            base_field = model._fields[base_name]
            if hasattr(base_field, 'column_name') and base_field.column_name == field_name:
                return
    
    available = sorted(model._fields.keys())
    raise ConfigurationError(
        f"Field '{field_name}' does not exist on model '{model.__name__}'. "
        f"Available fields: {', '.join(available)}"
    )


def _validate_lookup(lookup: str) -> None:
    """
    Validate that a lookup type is supported.
    
    Args:
        lookup: The lookup type to validate.
        
    Raises:
        ConfigurationError: If lookup not supported.
    """
    if lookup not in SUPPORTED_LOOKUPS:
        raise ConfigurationError(
            f"Unsupported lookup '{lookup}'. "
            f"Supported lookups: {', '.join(sorted(SUPPORTED_LOOKUPS))}"
        )


def _serialize_value(value: Any) -> Any:
    """
    Convert a value to JSON-serializable format.
    
    Args:
        value: The value to serialize.
        
    Returns:
        JSON-serializable value.
    """
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    return value


def _serialize_instance(
    instance: "Model",
    select_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Serialize a model instance to a dictionary.
    
    Args:
        instance: The model instance.
        select_fields: Optional list of fields to include.
        
    Returns:
        Dictionary of field name -> serialized value.
    """
    result: Dict[str, Any] = {}
    
    # Always include id
    result["id"] = _serialize_value(getattr(instance, "id", None))
    
    # Get field names to include
    if select_fields:
        field_names = [f for f in select_fields if f != "id"]
    else:
        field_names = list(instance._fields.keys())
    
    for field_name in field_names:
        if hasattr(instance, field_name):
            value = getattr(instance, field_name)
            result[field_name] = _serialize_value(value)
    
    return result


async def execute_ai_query_plan(plan: AiQueryPlan) -> AiQueryResult:
    """
    Execute an AiQueryPlan against the Vidyut ORM.
    
    This is the main executor that applies AI-generated query plans
    to the database. It validates all inputs and returns serialized results.
    
    Args:
        plan: The AiQueryPlan to execute.
        
    Returns:
        AiQueryResult with the query results.
        
    Raises:
        ConfigurationError: If model, field, or lookup is invalid.
    """
    # 1. Resolve model
    model = _resolve_model(plan.model)
    
    # 2. Start with base queryset
    qs = model.objects.filter()
    
    # 3. Apply filters
    for condition in plan.filters:
        # Validate field exists
        _validate_field(model, condition.field)
        
        # Validate lookup is supported
        _validate_lookup(condition.lookup)
        
        # Build filter expression
        if condition.lookup == "exact":
            filter_key = condition.field
        else:
            filter_key = f"{condition.field}__{condition.lookup}"
        
        qs = qs.filter(**{filter_key: condition.value})
    
    # 4. Apply sorting
    if plan.sorting:
        order_fields = []
        for sort in plan.sorting:
            # Validate field exists
            _validate_field(model, sort.field)
            
            if sort.direction == "desc":
                order_fields.append(f"-{sort.field}")
            else:
                order_fields.append(sort.field)
        
        qs = qs.order_by(*order_fields)
    
    # 5. Apply pagination
    # Vidyut QuerySet uses limit/offset via slicing or specific methods
    # We'll fetch all and slice - adjust if QuerySet has native limit/offset
    instances = await qs.all()
    
    # Apply offset and limit
    start = plan.pagination.offset
    end = start + plan.pagination.limit
    paginated_instances = instances[start:end]
    
    # 6. Serialize rows
    rows = [
        _serialize_instance(inst, plan.select_fields)
        for inst in paginated_instances
    ]
    
    # 7. Determine if results were limited
    limited = len(instances) > end or len(paginated_instances) >= plan.pagination.limit
    
    return AiQueryResult(
        plan=plan,
        rows=rows,
        count=len(rows),
        limited=limited,
    )


# =============================================================================
# Context Helpers
# =============================================================================


def get_query_plan_schema() -> Dict[str, Any]:
    """
    Get the JSON schema for AiQueryPlan.
    
    Returns:
        JSON Schema dict that LLMs can use to understand the query plan format.
    """
    return AiQueryPlan.model_json_schema()


def get_available_models_for_query() -> List[Dict[str, Any]]:
    """
    Get a list of available models with their field info for query context.
    
    Returns:
        List of model metadata dicts with name, fields, and supported lookups.
    """
    from vidyut.registry import get_model_meta
    
    result = []
    for name, model in ModelRegistry.all().items():
        meta = get_model_meta(model)
        result.append({
            "name": name,
            "description": meta.get("description", ""),
            "fields": [
                {
                    "name": f.get("name"),
                    "type": f.get("type"),
                    "nullable": f.get("nullable", False),
                }
                for f in meta.get("fields", [])
            ],
            "supported_lookups": sorted(SUPPORTED_LOOKUPS),
        })
    
    return result
