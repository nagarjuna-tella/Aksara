"""
Model Admin Options

ModelAdmin configuration class for customizing admin behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

if TYPE_CHECKING:
    from aksara.model.base import Model
    from aksara.contrib.admin.site import AdminSite
    from fastapi import Request


class ModelAdmin:
    """
    Configuration class for model admin behavior.
    
    Subclass this to customize how a model appears and behaves in the admin.
    
    Attributes:
        list_display: Fields to show in the list view (default: auto-picks up to 4)
        search_fields: Fields to search against
        list_filter: Fields to filter by
        readonly_fields: Fields that cannot be edited
        form_fields: Fields to show in forms (default: all non-pk fields)
    
    Example:
        class ArticleAdmin(ModelAdmin):
            list_display = ["title", "author", "created_at"]
            search_fields = ["title", "body"]
            list_filter = ["status"]
            readonly_fields = ["created_at", "updated_at"]
            
        site.register(Article, ArticleAdmin)
    """
    
    # List view configuration
    list_display: List[str] = []
    search_fields: List[str] = []
    list_filter: List[str] = []
    
    # Form configuration
    readonly_fields: List[str] = []
    form_fields: Optional[List[str]] = None  # None means auto-infer
    
    def __init__(self, model: Type["Model"], site: "AdminSite"):
        """
        Initialize the ModelAdmin.
        
        Args:
            model: The Model class this admin is for
            site: The AdminSite instance
        """
        self.model = model
        self.site = site
    
    # -------------------------------------------------------------------------
    # Query Helpers
    # -------------------------------------------------------------------------
    
    async def get_queryset(self, request: "Request") -> Any:
        """
        Get the base queryset for list views.
        
        Override to customize filtering based on request/user.
        
        Args:
            request: The FastAPI Request object
            
        Returns:
            A QuerySet (Manager.filter() result)
        """
        return self.model.objects.filter()
    
    async def get_object(self, request: "Request", pk: str) -> "Model":
        """
        Get a single object by primary key.
        
        Args:
            request: The FastAPI Request object
            pk: The primary key value
            
        Returns:
            The model instance
            
        Raises:
            DoesNotExist: If object not found
        """
        return await self.model.objects.get(id=pk)
    
    # -------------------------------------------------------------------------
    # Permissions
    # -------------------------------------------------------------------------
    
    def has_view_permission(
        self,
        request: "Request",
        obj: Optional["Model"] = None,
    ) -> bool:
        """
        Check if the user can view objects in admin.
        
        Args:
            request: The FastAPI Request object
            obj: Optional specific object being viewed
            
        Returns:
            True if user has permission
        """
        user = getattr(request.state, "user", None)
        return bool(user and getattr(user, "is_staff", False))
    
    def has_add_permission(self, request: "Request") -> bool:
        """
        Check if the user can add new objects.
        
        Args:
            request: The FastAPI Request object
            
        Returns:
            True if user has permission
        """
        return self.has_view_permission(request)
    
    def has_change_permission(
        self,
        request: "Request",
        obj: Optional["Model"] = None,
    ) -> bool:
        """
        Check if the user can change objects.
        
        Args:
            request: The FastAPI Request object
            obj: Optional specific object being changed
            
        Returns:
            True if user has permission
        """
        return self.has_view_permission(request, obj)
    
    def has_delete_permission(
        self,
        request: "Request",
        obj: Optional["Model"] = None,
    ) -> bool:
        """
        Check if the user can delete objects.
        
        Args:
            request: The FastAPI Request object
            obj: Optional specific object being deleted
            
        Returns:
            True if user has permission
        """
        return self.has_view_permission(request, obj)
    
    # -------------------------------------------------------------------------
    # Field Configuration
    # -------------------------------------------------------------------------
    
    def get_list_display(self, request: "Request") -> List[str]:
        """
        Get fields to display in list view.
        
        Args:
            request: The FastAPI Request object
            
        Returns:
            List of field names
        """
        if self.list_display:
            return self.list_display
        
        # Fallback: id + up to 3 non-relational fields
        names: List[str] = []
        for field in self.model.meta.fields:
            names.append(field.name)
        
        # Ensure id is first
        if "id" in names:
            names.remove("id")
            names.insert(0, "id")
        
        return names[:4]
    
    def get_readonly_fields(
        self,
        request: "Request",
        obj: Optional["Model"] = None,
    ) -> List[str]:
        """
        Get fields that cannot be edited.
        
        Args:
            request: The FastAPI Request object
            obj: Optional object being edited
            
        Returns:
            List of readonly field names
        """
        return self.readonly_fields or []
    
    # Fields that are always excluded from forms (auto-managed by the ORM)
    AUTO_EXCLUDE_FIELDS = {"created_at", "updated_at"}
    
    def get_form_fields(
        self,
        request: "Request",
        obj: Optional["Model"] = None,
    ) -> List[str]:
        """
        Get fields to show in add/change forms.
        
        By default, excludes:
        - Primary key fields
        - Auto-managed timestamp fields (created_at, updated_at)
        - Readonly fields
        
        Args:
            request: The FastAPI Request object
            obj: Optional object being edited
            
        Returns:
            List of field names for the form
        """
        if self.form_fields is not None:
            return self.form_fields
        
        readonly = set(self.get_readonly_fields(request, obj))
        fields: List[str] = []
        
        for field in self.model.meta.fields:
            # Skip primary key
            if getattr(field, "primary_key", False):
                continue
            # Skip auto-managed timestamp fields
            if field.name in self.AUTO_EXCLUDE_FIELDS:
                continue
            # Skip readonly fields
            if field.name in readonly:
                continue
            fields.append(field.name)
        
        # Also include ManyToMany fields
        for m2m_name in self.model.meta.many_to_many.keys():
            if m2m_name not in readonly:
                fields.append(m2m_name)
        
        return fields
    
    def get_field_type(self, field_name: str) -> str:
        """
        Get the HTML input type for a field.
        
        Args:
            field_name: Name of the field
            
        Returns:
            HTML input type string
        """
        # Check if it's a ManyToMany field first
        if field_name in self.model.meta.many_to_many:
            return "multiselect"
        
        field = self.model.meta.get_field(field_name)
        if not field:
            return "text"
        
        field_type = field.__class__.__name__
        
        type_map = {
            "Email": "email",
            "URL": "url",
            "Integer": "number",
            "Float": "number",
            "Decimal": "number",
            "Boolean": "checkbox",
            "DateTime": "datetime-local",
            "Date": "date",
            "Time": "time",
            "Text": "textarea",
            "JSON": "textarea",
            "ForeignKey": "select",
        }
        
        return type_map.get(field_type, "text")
    
    async def get_field_choices(
        self,
        field_name: str,
        request: "Request",
    ) -> List[tuple]:
        """
        Get choices for a ForeignKey or ManyToMany field.
        
        Returns list of (value, label) tuples for the select dropdown.
        
        Args:
            field_name: Name of the FK or M2M field
            request: The FastAPI Request object
            
        Returns:
            List of (id, display_string) tuples
        """
        from aksara.fields import ForeignKey, ManyToMany
        
        # Check for ManyToMany field first
        m2m_fields = self.model.meta.many_to_many
        if field_name in m2m_fields:
            m2m_field = m2m_fields[field_name]
            related_model = m2m_field.to_model
            objects = await related_model.objects.all()
            return [(str(obj.id), self._get_object_display(obj)) for obj in objects]
        
        # Check for ForeignKey field
        field = self.model.meta.get_field(field_name)
        if not field or not isinstance(field, ForeignKey):
            return []
        
        # Get the related model
        related_model = field.to_model
        
        # Fetch all related objects
        objects = await related_model.objects.all()
        
        choices = []
        for obj in objects:
            # Try to get a good display string
            label = self._get_object_display(obj)
            choices.append((str(obj.id), label))
        
        return choices
    
    def _get_object_display(self, obj: "Model") -> str:
        """
        Get a display string for a model instance.
        
        Tries __str__, then common field names, then falls back to ID.
        """
        # Try __str__ if it's been customized
        str_repr = str(obj)
        if str_repr and not str_repr.startswith("<"):
            return str_repr
        
        # Try common display fields
        for attr in ["name", "title", "email", "username", "label", "description"]:
            val = getattr(obj, attr, None)
            if val:
                return str(val)
        
        # Fall back to ID
        return str(obj.id)
    
    # -------------------------------------------------------------------------
    # Save / Delete Hooks
    # -------------------------------------------------------------------------
    
    async def save_model(
        self,
        request: "Request",
        obj: "Model",
        form_data: Dict[str, Any],
        is_created: bool,
    ) -> None:
        """
        Save the model instance.
        
        Override for custom save behavior.
        
        Args:
            request: The FastAPI Request object
            obj: The model instance
            form_data: Form data dict
            is_created: True if this is a new object
        """
        m2m_fields = self.model.meta.many_to_many
        m2m_data = {}
        
        # Separate M2M data from regular field data
        for name, value in form_data.items():
            if name in m2m_fields:
                m2m_data[name] = value
            else:
                setattr(obj, name, value)
        
        # Save the object first (required for M2M relations)
        await obj.save()
        
        # Now handle M2M relations
        for m2m_name, related_ids in m2m_data.items():
            m2m_manager = getattr(obj, m2m_name)
            related_model = m2m_fields[m2m_name].to_model
            
            # Clear existing relations and set new ones
            await m2m_manager.clear()
            
            if related_ids:
                # Fetch the related objects by IDs
                related_objects = []
                for rid in related_ids:
                    try:
                        related_obj = await related_model.objects.get(id=rid)
                        related_objects.append(related_obj)
                    except Exception:
                        pass  # Skip invalid IDs
                
                if related_objects:
                    await m2m_manager.add(*related_objects)
    
    async def delete_model(self, request: "Request", obj: "Model") -> None:
        """
        Delete the model instance.
        
        Override for custom delete behavior.
        
        Args:
            request: The FastAPI Request object
            obj: The model instance to delete
        """
        await obj.delete()
