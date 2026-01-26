"""
AI CodeGen Helpers for Vidyut.

This module provides deterministic code generation from structured specs.
LLMs produce AiModelSpec/AiCodegenRequest JSON, Vidyut generates real code.

The design is provider-agnostic: no LLM calls happen here.
We simply transform structured specs into Vidyut-compatible code artifacts.

v0.4.2: Initial release
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Type Aliases
# =============================================================================

FieldType = Literal[
    "string",
    "text",
    "integer",
    "boolean",
    "datetime",
    "uuid",
    "decimal",
    "email",
    "url",
    "json",
    "fk",
    "m2m",
]


class AiCodegenTarget:
    """Target types for code generation."""
    MODEL = "model"
    VIEWSET = "viewset"
    SERIALIZER = "serializer"
    APP = "app"
    MIGRATION = "migration"


# =============================================================================
# Pydantic Models - CodeGen Specs
# =============================================================================


class AiFieldSpec(BaseModel):
    """Specification for a single model field."""
    
    name: str = Field(..., description="Field name in snake_case, e.g., 'title', 'created_at'")
    type: FieldType = Field(..., description="Field type: 'string', 'integer', 'fk', etc.")
    required: bool = Field(default=True, description="Whether the field is required (not nullable)")
    unique: bool = Field(default=False, description="Whether the field has a unique constraint")
    max_length: Optional[int] = Field(default=None, description="Max length for string fields")
    default: Optional[Any] = Field(default=None, description="Default value (JSON-serializable)")
    fk_model: Optional[str] = Field(default=None, description="Target model for FK/M2M fields")
    help_text: Optional[str] = Field(default=None, description="Help text/description for the field")
    
    model_config = {"extra": "forbid"}


class AiModelSpec(BaseModel):
    """
    Specification for generating a Vidyut model.
    
    This is what LLMs produce when translating natural language
    model descriptions into structured specs.
    
    Example:
        {
            "app_label": "blog",
            "name": "Article",
            "fields": [
                {"name": "title", "type": "string", "max_length": 200},
                {"name": "body", "type": "text"},
                {"name": "published_at", "type": "datetime", "required": false},
                {"name": "author", "type": "fk", "fk_model": "User"}
            ],
            "add_viewset": true,
            "add_serializer": true
        }
    """
    
    app_label: str = Field(default="app", description="App label for the model")
    name: str = Field(..., description="Model class name in PascalCase, e.g., 'UserProfile'")
    table_name: Optional[str] = Field(default=None, description="Optional database table name override")
    fields: List[AiFieldSpec] = Field(..., description="List of field specifications")
    ai_exposed: bool = Field(default=True, description="Whether to expose model to AI tools")
    add_admin: bool = Field(default=True, description="Generate admin registration")
    add_viewset: bool = Field(default=True, description="Generate ModelViewSet")
    add_serializer: bool = Field(default=True, description="Generate ModelSerializer")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    model_config = {"extra": "forbid"}


class AiCodegenRequest(BaseModel):
    """Request for code generation."""
    
    target: str = Field(
        ...,
        description="Generation target: 'model', 'viewset', 'serializer', 'app', 'migration'"
    )
    model_spec: Optional[AiModelSpec] = Field(
        default=None,
        description="Model specification (required for model/viewset/serializer/migration targets)"
    )
    app_name: Optional[str] = Field(
        default=None,
        description="App name (required for 'app' target)"
    )
    extra_options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional options like base_dir, include_tests, etc."
    )
    
    model_config = {"extra": "forbid"}


class AiCodegenResult(BaseModel):
    """Result of code generation."""
    
    files: Dict[str, str] = Field(
        ...,
        description="Mapping of file path -> file content"
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Human-readable notes for the developer"
    )
    
    model_config = {"extra": "forbid"}


# =============================================================================
# Field Type Mapping
# =============================================================================

FIELD_TYPE_MAPPING: Dict[FieldType, str] = {
    "string": "fields.String",
    "text": "fields.Text",
    "integer": "fields.Integer",
    "boolean": "fields.Boolean",
    "datetime": "fields.DateTime",
    "uuid": "fields.UUID",
    "decimal": "fields.Decimal",
    "email": "fields.Email",
    "url": "fields.URL",
    "json": "fields.JSON",
    "fk": "fields.ForeignKey",
    "m2m": "fields.ManyToMany",
}


# =============================================================================
# Code Generation Functions
# =============================================================================


def _format_field_definition(field: AiFieldSpec) -> str:
    """Generate a single field definition line."""
    field_class = FIELD_TYPE_MAPPING.get(field.type, "fields.String")
    
    args: List[str] = []
    
    # Handle FK/M2M first argument (target model)
    if field.type in ("fk", "m2m") and field.fk_model:
        args.append(f'"{field.fk_model}"')
        if field.type == "fk":
            args.append('on_delete="CASCADE"')
    
    # max_length for strings
    if field.type == "string" and field.max_length:
        args.append(f"max_length={field.max_length}")
    
    # nullable (opposite of required)
    if not field.required:
        args.append("nullable=True")
    
    # unique
    if field.unique:
        args.append("unique=True")
    
    # default
    if field.default is not None:
        if isinstance(field.default, str):
            args.append(f'default="{field.default}"')
        elif isinstance(field.default, bool):
            args.append(f"default={field.default}")
        else:
            args.append(f"default={field.default}")
    
    # help_text
    if field.help_text:
        # Escape quotes in help text
        escaped = field.help_text.replace('"', '\\"')
        args.append(f'help_text="{escaped}"')
    
    args_str = ", ".join(args)
    return f"    {field.name} = {field_class}({args_str})"


def generate_model_code(spec: AiModelSpec) -> Dict[str, str]:
    """
    Generate Python code for a Vidyut model.
    
    Args:
        spec: The model specification.
        
    Returns:
        Dictionary with file path -> content mapping.
    """
    lines = [
        '"""',
        f'{spec.name} Model',
        '',
        f'Generated by Vidyut AI CodeGen at {datetime.now().isoformat()}',
        '"""',
        'from vidyut import Model, fields',
        '',
        '',
    ]
    
    # Class definition
    lines.append(f'class {spec.name}(Model):')
    lines.append(f'    """')
    lines.append(f'    {spec.name} model.')
    
    if spec.ai_exposed:
        lines.append(f'    ')
        lines.append(f'    AI Exposed: Yes')
    
    lines.append(f'    """')
    lines.append(f'    ')
    
    # Table name override
    if spec.table_name:
        lines.append(f'    class Meta:')
        lines.append(f'        table_name = "{spec.table_name}"')
        lines.append(f'    ')
    
    # Fields
    for field in spec.fields:
        lines.append(_format_field_definition(field))
    
    lines.append('')
    
    content = '\n'.join(lines)
    file_path = f"{spec.app_label}/models.py"
    
    return {file_path: content}


def generate_viewset_code(spec: AiModelSpec) -> Dict[str, str]:
    """
    Generate Python code for a Vidyut ModelViewSet.
    
    Args:
        spec: The model specification.
        
    Returns:
        Dictionary with file path -> content mapping.
    """
    lines = [
        '"""',
        f'{spec.name} ViewSet',
        '',
        f'Generated by Vidyut AI CodeGen at {datetime.now().isoformat()}',
        '"""',
        'from vidyut.api import ModelViewSet',
        f'from {spec.app_label}.models import {spec.name}',
        '',
        '',
        f'class {spec.name}ViewSet(ModelViewSet):',
        f'    """',
        f'    API ViewSet for {spec.name}.',
        f'    """',
        f'    ',
        f'    model = {spec.name}',
        f'    prefix = "/api/{spec.name.lower()}s"',
    ]
    
    if spec.ai_exposed:
        lines.append(f'    ai_exposed = True')
    
    lines.append('')
    
    content = '\n'.join(lines)
    file_path = f"{spec.app_label}/views.py"
    
    return {file_path: content}


def generate_serializer_code(spec: AiModelSpec) -> Dict[str, str]:
    """
    Generate Python code for a Vidyut ModelSerializer.
    
    Args:
        spec: The model specification.
        
    Returns:
        Dictionary with file path -> content mapping.
    """
    field_names = [f.name for f in spec.fields]
    fields_str = ', '.join(f'"{f}"' for f in field_names)
    
    lines = [
        '"""',
        f'{spec.name} Serializer',
        '',
        f'Generated by Vidyut AI CodeGen at {datetime.now().isoformat()}',
        '"""',
        'from vidyut.api import ModelSerializer',
        f'from {spec.app_label}.models import {spec.name}',
        '',
        '',
        f'class {spec.name}Serializer(ModelSerializer):',
        f'    """',
        f'    Serializer for {spec.name}.',
        f'    """',
        f'    ',
        f'    class Meta:',
        f'        model = {spec.name}',
        f'        fields = [{fields_str}]',
        '',
    ]
    
    content = '\n'.join(lines)
    file_path = f"{spec.app_label}/serializers.py"
    
    return {file_path: content}


def generate_admin_code(spec: AiModelSpec) -> Dict[str, str]:
    """
    Generate Python code for admin registration.
    
    Args:
        spec: The model specification.
        
    Returns:
        Dictionary with file path -> content mapping.
    """
    # Get string fields for list_display
    string_fields = [f.name for f in spec.fields if f.type in ("string", "email")][:3]
    list_display = ['id'] + string_fields
    list_display_str = ', '.join(f'"{f}"' for f in list_display)
    
    lines = [
        '"""',
        f'{spec.name} Admin',
        '',
        f'Generated by Vidyut AI CodeGen at {datetime.now().isoformat()}',
        '"""',
        'from vidyut.contrib.admin import ModelAdmin, register',
        f'from {spec.app_label}.models import {spec.name}',
        '',
        '',
        f'@register({spec.name})',
        f'class {spec.name}Admin(ModelAdmin):',
        f'    """',
        f'    Admin configuration for {spec.name}.',
        f'    """',
        f'    ',
        f'    list_display = [{list_display_str}]',
        '',
    ]
    
    content = '\n'.join(lines)
    file_path = f"{spec.app_label}/admin.py"
    
    return {file_path: content}


def generate_app_skeleton(app_name: str) -> Dict[str, str]:
    """
    Generate a basic Vidyut app skeleton.
    
    Args:
        app_name: The name of the app to create.
        
    Returns:
        Dictionary with file path -> content mappings.
    """
    files: Dict[str, str] = {}
    
    # __init__.py
    files[f"{app_name}/__init__.py"] = f'''"""
{app_name} App

Generated by Vidyut AI CodeGen at {datetime.now().isoformat()}
"""
'''
    
    # models.py
    files[f"{app_name}/models.py"] = f'''"""
{app_name} Models

Generated by Vidyut AI CodeGen at {datetime.now().isoformat()}
"""
from vidyut import Model, fields


# Define your models here
# class Example(Model):
#     name = fields.String(max_length=100)
'''
    
    # views.py
    files[f"{app_name}/views.py"] = f'''"""
{app_name} Views

Generated by Vidyut AI CodeGen at {datetime.now().isoformat()}
"""
from vidyut.api import ModelViewSet


# Define your ViewSets here
# class ExampleViewSet(ModelViewSet):
#     model = Example
#     prefix = "/api/examples"
'''
    
    # serializers.py
    files[f"{app_name}/serializers.py"] = f'''"""
{app_name} Serializers

Generated by Vidyut AI CodeGen at {datetime.now().isoformat()}
"""
from vidyut.api import ModelSerializer


# Define your serializers here
# class ExampleSerializer(ModelSerializer):
#     class Meta:
#         model = Example
#         fields = ["id", "name"]
'''
    
    # admin.py
    files[f"{app_name}/admin.py"] = f'''"""
{app_name} Admin

Generated by Vidyut AI CodeGen at {datetime.now().isoformat()}
"""
from vidyut.contrib.admin import ModelAdmin, register


# Register your models with admin here
# @register(Example)
# class ExampleAdmin(ModelAdmin):
#     list_display = ["id", "name"]
'''
    
    return files


def generate_migration_stub(spec: AiModelSpec) -> Dict[str, str]:
    """
    Generate a migration stub file.
    
    This creates a basic migration structure - not fully wired to
    the migration engine, but provides a useful starting point.
    
    Args:
        spec: The model specification.
        
    Returns:
        Dictionary with file path -> content mapping.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    migration_name = f"{timestamp}_create_{spec.name.lower()}"
    
    # Build column definitions
    columns = ['        ("id", "SERIAL PRIMARY KEY")']
    for field in spec.fields:
        col_type = _get_sql_type(field)
        nullable = "" if field.required else " NULL"
        unique = " UNIQUE" if field.unique else ""
        columns.append(f'        ("{field.name}", "{col_type}{nullable}{unique}")')
    
    columns_str = ',\n'.join(columns)
    table_name = spec.table_name or f"{spec.app_label}_{spec.name.lower()}"
    
    lines = [
        '"""',
        f'Migration: Create {spec.name} table',
        '',
        f'Generated by Vidyut AI CodeGen at {datetime.now().isoformat()}',
        '"""',
        '',
        '# Migration metadata',
        f'name = "{migration_name}"',
        f'app_label = "{spec.app_label}"',
        '',
        '',
        'async def up(db):',
        f'    """Create the {spec.name} table."""',
        '    columns = [',
        columns_str,
        '    ]',
        f'    table_name = "{table_name}"',
        '    ',
        '    col_defs = ", ".join(f"{name} {type_}" for name, type_ in columns)',
        '    await db.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({col_defs})")',
        '',
        '',
        'async def down(db):',
        f'    """Drop the {spec.name} table."""',
        f'    await db.execute("DROP TABLE IF EXISTS {table_name}")',
        '',
    ]
    
    content = '\n'.join(lines)
    file_path = f"{spec.app_label}/migrations/{migration_name}.py"
    
    return {file_path: content}


def _get_sql_type(field: AiFieldSpec) -> str:
    """Get the SQL type for a field specification."""
    type_mapping = {
        "string": f"VARCHAR({field.max_length or 255})",
        "text": "TEXT",
        "integer": "INTEGER",
        "boolean": "BOOLEAN",
        "datetime": "TIMESTAMP WITH TIME ZONE",
        "uuid": "UUID",
        "decimal": "DECIMAL(10,2)",
        "email": "VARCHAR(255)",
        "url": "TEXT",
        "json": "JSONB",
        "fk": "INTEGER REFERENCES",  # Simplified
        "m2m": "INTEGER",  # Through table would be separate
    }
    return type_mapping.get(field.type, "TEXT")


# =============================================================================
# Main Dispatcher
# =============================================================================


def generate_code(request: AiCodegenRequest) -> AiCodegenResult:
    """
    Generate Vidyut code from a structured request.
    
    This is the main entry point for code generation. It dispatches
    to the appropriate generator based on the target type.
    
    Args:
        request: The code generation request.
        
    Returns:
        AiCodegenResult with generated files and notes.
        
    Raises:
        ValueError: If request is invalid.
    """
    files: Dict[str, str] = {}
    notes: List[str] = []
    
    target = request.target.lower()
    
    if target == AiCodegenTarget.MODEL:
        if not request.model_spec:
            raise ValueError("model_spec is required for 'model' target")
        
        spec = request.model_spec
        
        # Generate model code
        files.update(generate_model_code(spec))
        notes.append(f"Created {spec.name} model in {spec.app_label}/models.py")
        
        # Optionally generate related code
        if spec.add_viewset:
            files.update(generate_viewset_code(spec))
            notes.append(f"Created {spec.name}ViewSet in {spec.app_label}/views.py")
        
        if spec.add_serializer:
            files.update(generate_serializer_code(spec))
            notes.append(f"Created {spec.name}Serializer in {spec.app_label}/serializers.py")
        
        if spec.add_admin:
            files.update(generate_admin_code(spec))
            notes.append(f"Created {spec.name}Admin in {spec.app_label}/admin.py")
        
        # Add helpful notes
        notes.append(f"Add '{spec.app_label}' to INSTALLED_APPS if not already present")
        notes.append(f"Run 'vidyut makemigrations --app {spec.app_label}.models' to create migrations")
        notes.append(f"Run 'vidyut migrate --app {spec.app_label}.models' to apply migrations")
        
        if spec.add_viewset:
            notes.append(f"Wire the ViewSet into your app: app.include_viewset({spec.name}ViewSet)")
    
    elif target == AiCodegenTarget.VIEWSET:
        if not request.model_spec:
            raise ValueError("model_spec is required for 'viewset' target")
        
        files.update(generate_viewset_code(request.model_spec))
        notes.append(f"Created {request.model_spec.name}ViewSet")
        notes.append("Wire the ViewSet into your app using include_viewset()")
    
    elif target == AiCodegenTarget.SERIALIZER:
        if not request.model_spec:
            raise ValueError("model_spec is required for 'serializer' target")
        
        files.update(generate_serializer_code(request.model_spec))
        notes.append(f"Created {request.model_spec.name}Serializer")
    
    elif target == AiCodegenTarget.APP:
        if not request.app_name:
            raise ValueError("app_name is required for 'app' target")
        
        files.update(generate_app_skeleton(request.app_name))
        notes.append(f"Created app skeleton for '{request.app_name}'")
        notes.append(f"Add '{request.app_name}' to INSTALLED_APPS")
        notes.append("Define your models in models.py")
        notes.append("Create ViewSets in views.py and wire them to your app")
    
    elif target == AiCodegenTarget.MIGRATION:
        if not request.model_spec:
            raise ValueError("model_spec is required for 'migration' target")
        
        files.update(generate_migration_stub(request.model_spec))
        notes.append(f"Created migration stub for {request.model_spec.name}")
        notes.append("Review and customize the migration before applying")
        notes.append("Consider using 'vidyut makemigrations' for production migrations")
    
    else:
        raise ValueError(
            f"Unknown target '{target}'. "
            f"Supported targets: model, viewset, serializer, app, migration"
        )
    
    return AiCodegenResult(files=files, notes=notes)


# =============================================================================
# Schema Helpers
# =============================================================================


def get_codegen_schemas() -> Dict[str, Any]:
    """
    Get JSON schemas for codegen models.
    
    Returns:
        Dictionary with schema names -> JSON Schema dicts.
    """
    return {
        "AiFieldSpec": AiFieldSpec.model_json_schema(),
        "AiModelSpec": AiModelSpec.model_json_schema(),
        "AiCodegenRequest": AiCodegenRequest.model_json_schema(),
        "AiCodegenResult": AiCodegenResult.model_json_schema(),
    }
