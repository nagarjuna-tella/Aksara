"""
API Filter Backends

Provides DRF-style filter backends for Aksara ViewSets.

v0.5.39: Added DjangoFilterBackend for automatic query parameter filtering
following Django ORM lookup syntax (?price__gte=50&category__in=tech,news).
"""

from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
from fastapi import Request

from aksara.security.context import principal_from_request
from aksara.security.policy import get_policy_engine
from aksara.security.principal import Principal

if TYPE_CHECKING:
    from aksara.manager import QuerySet
    from aksara.api.viewsets import ModelViewSet


_TENANT_ORDERING_FIELDS = frozenset({"tenant_id", "tenant", "organisation_id", "org_id"})


def _resolve_principal_for_filter(request: Request) -> Optional[Principal]:
    """Resolve a principal for query filtering without trusting client headers."""
    state = getattr(request, "state", None)
    if state is not None:
        cached = getattr(state, "principal", None)
        if isinstance(cached, Principal):
            return cached
    try:
        return principal_from_request(request)
    except Exception:
        return None


class BaseFilterBackend:
    """Base class for filter backends."""
    
    def filter_queryset(self, request: Request, queryset: "QuerySet", view: "ModelViewSet") -> "QuerySet":
        """
        Return a filtered queryset.
        
        Args:
            request: The incoming request
            queryset: The base queryset
            view: The viewset instance
            
        Returns:
            A filtered QuerySet
        """
        return queryset


class DjangoFilterBackend(BaseFilterBackend):
    """
    Filter backend that automatically parses query parameters following Django ORM syntax.
    
    Supports Django-style lookups in query parameters:
        - field=value (exact match)
        - field__gt=value (greater than)
        - field__gte=value (greater than or equal)
        - field__lt=value (less than)
        - field__lte=value (less than or equal)
        - field__in=val1,val2 (membership)
        - field__isnull=true/false (null check)
        - field__icontains=substring (case-insensitive contains)
        - field__contains=substring (case-sensitive contains)
    
    v0.5.39: Initial implementation.
    
    Example:
        class ProductViewSet(ModelViewSet):
            model = Product
            filter_backends = [DjangoFilterBackend]
            filterable_fields = ['price', 'category', 'in_stock']
        
        # GET /products/?price__gte=50&category=electronics&in_stock=true
    """
    
    def filter_queryset(self, request: Request, queryset: "QuerySet", view: "ModelViewSet") -> "QuerySet":
        """
        Apply Django-style filters from query parameters to the queryset.
        
        Args:
            request: The HTTP request
            queryset: The QuerySet to filter
            view: The ViewSet instance
            
        Returns:
            Filtered QuerySet
        """
        filter_fields = getattr(view, 'filterable_fields', [])
        if not filter_fields:
            return queryset
        
        filters = self._parse_filter_params(request, filter_fields)
        if filters:
            queryset = queryset.filter(**filters)
        
        return queryset
    
    def _parse_filter_params(
        self,
        request: Request,
        filter_fields: List[str],
    ) -> Dict[str, Any]:
        """
        Parse query parameters into filter kwargs.
        
        Args:
            request: The HTTP request
            filter_fields: List of allowed filter fields
            
        Returns:
            Dictionary of filter kwargs
        """
        filters = {}
        query_params = request.query_params
        
        for field in filter_fields:
            # Check for exact match first
            if field in query_params:
                value = query_params[field]
                filters[field] = self._coerce_value(value)
            
            # Check for lookups (field__lookup)
            lookup_prefix = f"{field}__"
            for param_name, param_value in query_params.items():
                if param_name.startswith(lookup_prefix):
                    # Extract the lookup type
                    lookup = param_name[len(lookup_prefix):]
                    coerced_value = self._coerce_lookup_value(lookup, param_value)
                    filters[param_name] = coerced_value
        
        return filters
    
    def _coerce_value(self, value: str) -> Union[str, bool, None]:
        """
        Coerce string query parameter into appropriate Python type.
        
        Args:
            value: String value from query parameter
            
        Returns:
            Coerced value (str, bool, or None)
        """
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        if value.lower() in ('null', 'none', ''):
            return None
        return value
    
    def _coerce_lookup_value(self, lookup: str, value: str) -> Any:
        """
        Coerce value based on lookup type.
        
        Args:
            lookup: The lookup type (e.g., 'in', 'isnull', 'gt')
            value: The string value from query parameter
            
        Returns:
            Coerced value appropriate for the lookup
        """
        if lookup == 'in':
            # Split comma-separated values
            return [v.strip() for v in value.split(',') if v.strip()]
        
        if lookup == 'isnull':
            # Convert to boolean
            return self._coerce_value(value)
        
        # For numeric comparisons, try to coerce to number
        if lookup in ('gt', 'gte', 'lt', 'lte'):
            try:
                if '.' in value:
                    return float(value)
                return int(value)
            except ValueError:
                # Fall back to string
                return value
        
        # Default: coerce as general value
        return self._coerce_value(value)


class SearchFilter(BaseFilterBackend):
    """
    Search filter backend.
    
    Filters the queryset based on a ?search= query parameter.
    Searches across fields defined in view.search_fields using ILIKE (icontains).
    """
    search_param = "search"
    
    def filter_queryset(self, request: Request, queryset: "QuerySet", view: "ModelViewSet") -> "QuerySet":
        search_terms = request.query_params.get(self.search_param)
        search_fields = getattr(view, "search_fields", [])
        
        if not search_terms or not search_fields:
            return queryset
            
        return queryset.search(search_terms, search_fields)


class OrderingFilter(BaseFilterBackend):
    """
    Ordering filter backend.
    
    Orders the queryset based on a ?ordering= query parameter.
    Allows ordering by fields defined in view.ordering_fields.
    Prefix with '-' for descending order.
    Multiple fields can be comma-separated: ?ordering=-created_at,id
    """
    ordering_param = "ordering"
    
    def filter_queryset(self, request: Request, queryset: "QuerySet", view: "ModelViewSet") -> "QuerySet":
        ordering_terms = request.query_params.get(self.ordering_param)
        ordering_fields = getattr(view, "ordering_fields", [])
        
        if not ordering_terms or not ordering_fields:
            # Check if there's default ordering on the view
            default_ordering = getattr(view, "ordering", None)
            if default_ordering:
                if isinstance(default_ordering, str):
                    return queryset.order_by(default_ordering)
                elif isinstance(default_ordering, (list, tuple)):
                    return queryset.order_by(*default_ordering)
            return queryset
            
        # Parse requested ordering fields
        terms = [t.strip() for t in ordering_terms.split(",") if t.strip()]
        valid_terms = []
        
        # Check against allowed ordering_fields
        # If ordering_fields == "__all__", any field is allowed
        allow_all = ordering_fields == "__all__"
        principal = _resolve_principal_for_filter(request)
        visible_fields = None
        if principal is not None:
            decision = get_policy_engine().visible_fields(principal, view.model)
            visible_fields = set(decision.allowed_fields)
        
        for term in terms:
            # Strip '-' to check the actual field name
            field_name = term[1:] if term.startswith("-") else term

            if principal is not None and field_name in _TENANT_ORDERING_FIELDS and not principal.is_system:
                continue
            if visible_fields is not None and field_name not in visible_fields:
                continue

            if allow_all or field_name in ordering_fields:
                valid_terms.append(term)
                
        if valid_terms:
            return queryset.order_by(*valid_terms)
            
        return queryset
