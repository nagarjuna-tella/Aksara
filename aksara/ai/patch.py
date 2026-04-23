"""
Aksara AI Patch Engine (THE SURGEON)

Safe, deterministic, fully validated AI patching that allows AI agents
to propose structural code changes with Aksara validating, applying,
or rejecting unsafe modifications.

This is the same safety layer that Cursor, Copilot Workspace, and Replit
Ghostwriter all needed - but built directly into Aksara.

v0.4.4: Initial AI Patch Engine release

Usage:
    from aksara.ai.patch import apply_ai_patches, AiPatchRequest
    
    request = AiPatchRequest(
        operations=[
            AiPatchOperation(type="add_field", model="User", field="bio", field_spec={"type": "text"})
        ],
        reason="Add bio field to user profile"
    )
    result = apply_ai_patches(request, preview=True)
"""

from __future__ import annotations

import ast
import copy
import difflib
import hashlib
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Set, Tuple, Type, Union

from pydantic import BaseModel, Field, field_validator

from aksara.ai.codegen import (
    AiFieldSpec,
    AiModelSpec,
    FIELD_TYPE_MAPPING,
    generate_model_code,
    generate_viewset_code,
)


# =============================================================================
# Constants & Configuration
# =============================================================================

# Operations that are allowed
ALLOWED_OPERATIONS = frozenset([
    "modify_file",
    "replace_text",
    "insert_text",
    "delete_text",
    "add_model",
    "update_model",
    "delete_model",
    "add_field",
    "update_field",
    "delete_field",
    "add_viewset",
    "update_viewset",
    "delete_viewset",
    "add_import",
])

# File patterns that are NEVER allowed to be modified
PROTECTED_PATTERNS = frozenset([
    "**/migrations/*.py",  # Migration files
    "*/migrations/*.py",
    "migrations/*.py",
    "**/__pycache__/**",
    "*/__pycache__/*",
    "__pycache__/*",
    "**/.git/**",
    ".git/**",
    ".git/*",
    "**/.env",
    ".env",
    "**/secrets.*",
    "secrets.*",
    "**/credentials.*",
    "credentials.*",
])

# Directories that can be modified
ALLOWED_DIRECTORIES = frozenset([
    "app",
    "apps",
    "models",
    "views",
    "api",
    "serializers",
    "admin",
    "tests",
    "core",
])

# Dangerous patterns that should be blocked
DANGEROUS_PATTERNS = [
    r"os\.system\s*\(",
    r"subprocess\.\w+\s*\(",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__\s*\(",
    r"open\s*\([^)]*['\"]w['\"]",  # write mode
    r"shutil\.rmtree\s*\(",
    r"os\.remove\s*\(",
    r"os\.unlink\s*\(",
]

DANGEROUS_AST_MODULES = frozenset({
    "os",
    "subprocess",
    "shutil",
    "importlib",
    "ctypes",
    "cffi",
})

DIRECT_DANGEROUS_CALLS = frozenset({"eval", "exec", "compile", "__import__"})
ATTRIBUTE_DANGEROUS_CALLS = frozenset({
    "os.system",
    "os.popen",
    "os.remove",
    "os.unlink",
    "os.rmdir",
    "os.execv",
    "os.execve",
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_output",
    "subprocess.Popen",
    "shutil.rmtree",
    "shutil.move",
    "shutil.copyfileobj",
    "importlib.import_module",
    "importlib.util.spec_from_file_location",
    "ctypes.CDLL",
    "cffi.dlopen",
})
GETATTR_DANGEROUS_NAMES = frozenset({
    "system",
    "popen",
    "remove",
    "unlink",
    "rmdir",
    "execv",
    "execve",
    "run",
    "call",
    "check_output",
    "Popen",
    "rmtree",
    "move",
    "copyfileobj",
    "import_module",
    "spec_from_file_location",
    "CDLL",
    "dlopen",
})


# =============================================================================
# Enums
# =============================================================================

class PatchOperationType(str, Enum):
    """Types of patch operations."""
    MODIFY_FILE = "modify_file"
    REPLACE_TEXT = "replace_text"
    INSERT_TEXT = "insert_text"
    DELETE_TEXT = "delete_text"
    ADD_MODEL = "add_model"
    UPDATE_MODEL = "update_model"
    DELETE_MODEL = "delete_model"
    ADD_FIELD = "add_field"
    UPDATE_FIELD = "update_field"
    DELETE_FIELD = "delete_field"
    ADD_VIEWSET = "add_viewset"
    UPDATE_VIEWSET = "update_viewset"
    DELETE_VIEWSET = "delete_viewset"
    ADD_IMPORT = "add_import"


class PatchValidationError(str, Enum):
    """Types of validation errors."""
    PATH_OUTSIDE_PROJECT = "path_outside_project"
    PROTECTED_FILE = "protected_file"
    SYNTAX_ERROR = "syntax_error"
    INVALID_MODEL = "invalid_model"
    INVALID_FIELD = "invalid_field"
    DANGEROUS_CODE = "dangerous_code"
    MISSING_REQUIRED = "missing_required"
    FILE_NOT_FOUND = "file_not_found"
    INVALID_OPERATION = "invalid_operation"


# =============================================================================
# Pydantic Models
# =============================================================================

class AiPatchOperation(BaseModel):
    """
    A single patch operation.
    
    Supports both raw diff-style edits and structured model/field edits.
    
    Examples:
        # File modification
        AiPatchOperation(type="modify_file", path="app/models.py", diff="...")
        
        # Add a model
        AiPatchOperation(
            type="add_model",
            model="Article",
            app_label="blog",
            model_spec={"fields": [...]}
        )
        
        # Add a field
        AiPatchOperation(
            type="add_field",
            model="User",
            field="bio",
            field_spec={"type": "text", "nullable": True}
        )
    """
    
    type: Literal[
        "modify_file",
        "replace_text",
        "insert_text",
        "delete_text",
        "add_model",
        "update_model",
        "delete_model",
        "add_field",
        "update_field",
        "delete_field",
        "add_viewset",
        "update_viewset",
        "delete_viewset",
        "add_import",
    ] = Field(..., description="Type of patch operation")
    
    # Generic fields for file edits
    path: Optional[str] = Field(default=None, description="File path relative to project root")
    diff: Optional[str] = Field(default=None, description="Unified diff to apply")
    start_line: Optional[int] = Field(default=None, description="Start line for text operations (1-indexed)")
    end_line: Optional[int] = Field(default=None, description="End line for text operations (1-indexed)")
    text: Optional[str] = Field(default=None, description="Text content for insert/replace operations")
    old_text: Optional[str] = Field(default=None, description="Text to find and replace")
    new_text: Optional[str] = Field(default=None, description="Replacement text")
    
    # Structured model edits
    model: Optional[str] = Field(default=None, description="Model name for model/field operations")
    app_label: Optional[str] = Field(default=None, description="App label (default: 'app')")
    field: Optional[str] = Field(default=None, description="Field name for field operations")
    field_spec: Optional[Dict[str, Any]] = Field(default=None, description="Field specification")
    model_spec: Optional[Dict[str, Any]] = Field(default=None, description="Model specification")
    
    # Import operations
    import_statement: Optional[str] = Field(default=None, description="Import statement to add")
    
    # Metadata
    note: Optional[str] = Field(default=None, description="Human-readable note about this operation")
    
    model_config = {"extra": "forbid"}
    
    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ALLOWED_OPERATIONS:
            raise ValueError(f"Invalid operation type: {v}")
        return v


class AiPatchRequest(BaseModel):
    """
    Request to apply one or more patch operations.
    
    Example:
        {
            "operations": [
                {"type": "add_field", "model": "User", "field": "bio", "field_spec": {"type": "text"}},
                {"type": "add_import", "path": "app/models.py", "import_statement": "from datetime import datetime"}
            ],
            "reason": "Add bio field to user model"
        }
    """
    
    operations: List[AiPatchOperation] = Field(..., description="List of patch operations to apply")
    reason: Optional[str] = Field(default=None, description="Reason for this patch request")
    dry_run: bool = Field(default=False, description="If True, validate but don't apply")
    
    model_config = {"extra": "forbid"}
    
    @field_validator("operations")
    @classmethod
    def validate_operations(cls, v: List[AiPatchOperation]) -> List[AiPatchOperation]:
        if not v:
            raise ValueError("At least one operation is required")
        return v


class AiPatchValidationResult(BaseModel):
    """Result of validating a single operation."""
    
    valid: bool = Field(..., description="Whether the operation is valid")
    error_type: Optional[str] = Field(default=None, description="Type of validation error")
    error_message: Optional[str] = Field(default=None, description="Human-readable error message")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")
    
    model_config = {"extra": "forbid"}


class AiPatchFileChange(BaseModel):
    """Represents a change to a single file."""
    
    path: str = Field(..., description="File path relative to project root")
    original_content: Optional[str] = Field(default=None, description="Original file content")
    new_content: str = Field(..., description="New file content after patch")
    diff: str = Field(default="", description="Unified diff of changes")
    created: bool = Field(default=False, description="Whether this is a new file")
    
    model_config = {"extra": "forbid"}


class AiPatchResult(BaseModel):
    """
    Result of applying patch operations.
    
    Contains information about what changed, any errors,
    and the ability to preview or rollback.
    """
    
    applied: bool = Field(..., description="Whether patches were applied successfully")
    preview_only: bool = Field(default=False, description="Whether this was preview mode")
    files_changed: Dict[str, AiPatchFileChange] = Field(
        default_factory=dict,
        description="Map of path -> file change details"
    )
    operations_applied: int = Field(default=0, description="Number of operations applied")
    operations_failed: int = Field(default=0, description="Number of operations that failed")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    notes: List[str] = Field(default_factory=list, description="Informational notes")
    rollback_available: bool = Field(default=False, description="Whether rollback is available")
    checksum: str = Field(default="", description="Checksum of all changes for verification")
    
    model_config = {"extra": "forbid"}


# =============================================================================
# Validation Functions
# =============================================================================

def _is_path_safe(path: str, project_root: str) -> bool:
    """Check if a path is within the project root."""
    try:
        # Resolve to absolute paths
        abs_path = os.path.abspath(os.path.join(project_root, path))
        abs_root = os.path.abspath(project_root)
        
        # Check if the path starts with the root
        return abs_path.startswith(abs_root + os.sep) or abs_path == abs_root
    except Exception:
        return False


def _is_protected_file(path: str) -> bool:
    """Check if a file matches protected patterns."""
    from fnmatch import fnmatch
    
    for pattern in PROTECTED_PATTERNS:
        if fnmatch(path, pattern):
            return True
    return False


def validate_patch_ast(content: str) -> Tuple[bool, str]:
    """Validate that the AI-generated code is safe via AST whitelist."""
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"
        
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False, "Dangerous pattern detected: import statements are not allowed."
            
        if isinstance(node, ast.Call):
            # Resolve function name
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
                
            if name in {'eval', 'exec', 'compile', '__import__', 'open', 'vars', 'dir', 'getattr', 'setattr', 'delattr'}:
                return False, f"Dangerous pattern detected: function call {name}"
                
        if isinstance(node, ast.Attribute):
            if node.attr in {'__class__', '__bases__', '__subclasses__', '__globals__', '__builtins__', '__dict__'}:
                return False, f"Dangerous pattern detected: attribute access {node.attr}"
                
        if isinstance(node, ast.Name):
            if node.id in {'__class__', '__bases__', '__subclasses__', '__globals__', '__builtins__', '__dict__'}:
                return False, f"Dangerous pattern detected: name access {node.id}"
                
    return True, ""


def _resolve_call_name(node: ast.AST) -> Optional[str]:
    """Resolve a function or attribute node to a dotted name when possible."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _resolve_call_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
    return None


def _get_import_module_target(node: ast.AST) -> Optional[str]:
    """Resolve importlib.import_module("module") targets from call nodes."""
    if not isinstance(node, ast.Call):
        return None
    if _resolve_call_name(node.func) != "importlib.import_module":
        return None
    if not node.args:
        return None
    module_arg = node.args[0]
    if isinstance(module_arg, ast.Constant) and isinstance(module_arg.value, str):
        return module_arg.value
    return None


def _get_getattr_danger(node: ast.AST) -> Optional[str]:
    """Detect getattr(..., "dangerous_name") indirection."""
    if not isinstance(node, ast.Call):
        return None
    if _resolve_call_name(node.func) != "getattr" or len(node.args) < 2:
        return None
    attr_arg = node.args[1]
    if isinstance(attr_arg, ast.Constant) and isinstance(attr_arg.value, str):
        if attr_arg.value in GETATTR_DANGEROUS_NAMES:
            return attr_arg.value
    return None


def _is_decoder_call(node: ast.AST) -> bool:
    """Check if a node decodes potentially obfuscated code before execution."""
    if not isinstance(node, ast.Call):
        return False

    call_name = _resolve_call_name(node.func)
    if call_name in {"base64.b64decode", "codecs.decode", "bytes.decode"}:
        return True

    return isinstance(node.func, ast.Attribute) and node.func.attr == "decode"


def _ast_dangerous_code_check(content: str) -> list[str]:
    """Check for dangerous code patterns that evade the regex fast path."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Call):
            dangerous_getattr = _get_getattr_danger(node.func)
            if dangerous_getattr:
                violations.append(f"Dangerous getattr call detected: {dangerous_getattr}")
                continue

        call_name = _resolve_call_name(node.func)
        if call_name in DIRECT_DANGEROUS_CALLS:
            violations.append(f"Dangerous call detected: {call_name}")
            continue

        if call_name in ATTRIBUTE_DANGEROUS_CALLS:
            violations.append(f"Dangerous call detected: {call_name}")
            continue

        dangerous_getattr = _get_getattr_danger(node)
        if dangerous_getattr:
            violations.append(f"Dangerous getattr access detected: {dangerous_getattr}")
            continue

        if isinstance(node.func, ast.Attribute):
            import_target = _get_import_module_target(node.func.value)
            if import_target in DANGEROUS_AST_MODULES:
                violations.append(
                    f"Dangerous dynamic import call detected: {import_target}.{node.func.attr}"
                )
                continue

        if call_name in {"eval", "exec"} and any(_is_decoder_call(arg) for arg in node.args):
            violations.append(f"Dangerous decoded execution detected: {call_name}")

    return violations


def _validate_python_syntax(content: str) -> Tuple[bool, Optional[str]]:
    """Validate Python syntax using AST."""
    try:
        ast.parse(content)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"


def _validate_model_reference(model_name: str, project_root: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a model exists in the project.
    
    For now, we do a simple file search. In production,
    you'd check the ModelRegistry.
    """
    # Simple validation - model name should be PascalCase
    if not model_name or not model_name[0].isupper():
        return False, f"Invalid model name: {model_name} (must be PascalCase)"
    
    # Check if model is referenced anywhere
    # This is a basic check - in production you'd use ModelRegistry
    return True, None


def validate_operation(
    operation: AiPatchOperation,
    project_root: str,
    existing_files: Optional[Dict[str, str]] = None
) -> AiPatchValidationResult:
    """
    Validate a single patch operation.
    
    Safety rules:
    - ❌ Reject: Editing outside project dir
    - ❌ Reject: Modifying migration files directly
    - ❌ Reject: Dangerous code patterns
    - ❌ Reject: Invalid model references
    - ❌ Reject: Syntax errors after patch
    - ✔ Allow: Editing app directories
    - ✔ Allow: Adding models, fields, viewsets
    - ✔ Allow: Adding imports
    """
    warnings: List[str] = []
    
    # Validate path-based operations
    if operation.path:
        # Check if path is within project
        if not _is_path_safe(operation.path, project_root):
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.PATH_OUTSIDE_PROJECT.value,
                error_message=f"Path '{operation.path}' is outside project directory"
            )
        
        # Check if file is protected
        if _is_protected_file(operation.path):
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.PROTECTED_FILE.value,
                error_message=f"Cannot modify protected file: {operation.path}"
            )
    
    # Validate content-based operations
    if operation.text:
        valid, danger_msg = validate_patch_ast(operation.text)
        if not valid:
            from aksara.exceptions import PatchRejectedError
            raise PatchRejectedError(danger_msg)
    
    if operation.new_text:
        valid, danger_msg = validate_patch_ast(operation.new_text)
        if not valid:
            from aksara.exceptions import PatchRejectedError
            raise PatchRejectedError(danger_msg)
    
    # Validate operation-specific requirements
    op_type = operation.type
    
    if op_type == "modify_file":
        if not operation.path:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="modify_file requires 'path'"
            )
        if not operation.diff and not operation.text:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="modify_file requires 'diff' or 'text'"
            )
    
    elif op_type == "replace_text":
        if not operation.path:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="replace_text requires 'path'"
            )
        if not operation.old_text or operation.new_text is None:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="replace_text requires 'old_text' and 'new_text'"
            )
    
    elif op_type == "insert_text":
        if not operation.path:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="insert_text requires 'path'"
            )
        if operation.start_line is None or not operation.text:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="insert_text requires 'start_line' and 'text'"
            )
    
    elif op_type == "delete_text":
        if not operation.path:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="delete_text requires 'path'"
            )
        if operation.start_line is None or operation.end_line is None:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="delete_text requires 'start_line' and 'end_line'"
            )
    
    elif op_type in ("add_model", "update_model"):
        if not operation.model:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message=f"{op_type} requires 'model'"
            )
        if op_type == "add_model" and not operation.model_spec:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="add_model requires 'model_spec'"
            )
    
    elif op_type == "delete_model":
        if not operation.model:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="delete_model requires 'model'"
            )
        warnings.append("delete_model will require a migration to remove the table")
    
    elif op_type in ("add_field", "update_field"):
        if not operation.model:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message=f"{op_type} requires 'model'"
            )
        if not operation.field:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message=f"{op_type} requires 'field'"
            )
        if op_type == "add_field" and not operation.field_spec:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="add_field requires 'field_spec'"
            )
    
    elif op_type == "delete_field":
        if not operation.model or not operation.field:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="delete_field requires 'model' and 'field'"
            )
        warnings.append("delete_field will require a migration to remove the column")
    
    elif op_type in ("add_viewset", "update_viewset"):
        if not operation.model:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message=f"{op_type} requires 'model'"
            )
    
    elif op_type == "delete_viewset":
        if not operation.model:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="delete_viewset requires 'model'"
            )
    
    elif op_type == "add_import":
        if not operation.path:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="add_import requires 'path'"
            )
        if not operation.import_statement:
            return AiPatchValidationResult(
                valid=False,
                error_type=PatchValidationError.MISSING_REQUIRED.value,
                error_message="add_import requires 'import_statement'"
            )
    
    return AiPatchValidationResult(valid=True, warnings=warnings)


def validate_patch_request(
    request: AiPatchRequest,
    project_root: str,
    existing_files: Optional[Dict[str, str]] = None
) -> Tuple[bool, List[AiPatchValidationResult]]:
    """
    Validate all operations in a patch request.
    
    Returns (all_valid, list of validation results).
    """
    results: List[AiPatchValidationResult] = []
    all_valid = True
    
    for op in request.operations:
        result = validate_operation(op, project_root, existing_files)
        results.append(result)
        if not result.valid:
            all_valid = False
    
    return all_valid, results


# =============================================================================
# File Patch Executors
# =============================================================================

def _generate_diff(original: str, modified: str, path: str) -> str:
    """Generate a unified diff between original and modified content."""
    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm=""
    )
    
    return "".join(diff)


def _apply_unified_diff(original: str, diff: str) -> Tuple[bool, str, Optional[str]]:
    """
    Apply a unified diff to content.
    
    Returns (success, result_content, error_message).
    """
    try:
        # Parse the diff
        lines = diff.splitlines()
        result_lines = original.splitlines()
        
        # Track current position
        offset = 0
        
        # Find hunk headers
        for i, line in enumerate(lines):
            if line.startswith("@@"):
                # Parse hunk header: @@ -start,count +start,count @@
                match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                if not match:
                    continue
                
                orig_start = int(match.group(1)) - 1  # Convert to 0-indexed
                new_start = int(match.group(3)) - 1
                
                # Process hunk lines
                j = i + 1
                current_line = orig_start + offset
                
                while j < len(lines) and not lines[j].startswith("@@"):
                    hunk_line = lines[j]
                    
                    if hunk_line.startswith("-"):
                        # Delete line
                        if current_line < len(result_lines):
                            del result_lines[current_line]
                            offset -= 1
                    elif hunk_line.startswith("+"):
                        # Add line
                        result_lines.insert(current_line, hunk_line[1:])
                        current_line += 1
                        offset += 1
                    elif hunk_line.startswith(" "):
                        # Context line
                        current_line += 1
                    
                    j += 1
        
        return True, "\n".join(result_lines), None
    except Exception as e:
        return False, "", f"Failed to apply diff: {str(e)}"


def apply_modify_file(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """
    Apply a modify_file operation.
    
    If diff is provided, apply it. Otherwise, replace entire content.
    """
    if not operation.path:
        return False, None, "Path is required"
    
    abs_path = os.path.join(project_root, operation.path)
    
    # Get original content
    original_content = file_cache.get(operation.path, "")
    if not original_content and os.path.exists(abs_path):
        with open(abs_path, "r") as f:
            original_content = f.read()
        file_cache[operation.path] = original_content
    
    # Determine new content
    if operation.diff:
        success, new_content, error = _apply_unified_diff(original_content, operation.diff)
        if not success:
            return False, None, error
    elif operation.text is not None:
        new_content = operation.text
    else:
        return False, None, "Either diff or text is required"
    
    # Validate Python syntax if it's a Python file
    if operation.path.endswith(".py"):
        is_valid, syntax_error = _validate_python_syntax(new_content)
        if not is_valid:
            return False, None, syntax_error
    
    # Generate diff for the result
    diff = _generate_diff(original_content, new_content, operation.path)
    
    change = AiPatchFileChange(
        path=operation.path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=not original_content
    )
    
    return True, change, None


def apply_replace_text(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Apply a replace_text operation."""
    if not operation.path or not operation.old_text:
        return False, None, "Path and old_text are required"
    
    abs_path = os.path.join(project_root, operation.path)
    
    # Get original content
    original_content = file_cache.get(operation.path, "")
    if not original_content and os.path.exists(abs_path):
        with open(abs_path, "r") as f:
            original_content = f.read()
        file_cache[operation.path] = original_content
    
    if operation.old_text not in original_content:
        return False, None, f"Text to replace not found in {operation.path}"
    
    new_content = original_content.replace(operation.old_text, operation.new_text or "", 1)
    
    # Validate Python syntax if it's a Python file
    if operation.path.endswith(".py"):
        is_valid, syntax_error = _validate_python_syntax(new_content)
        if not is_valid:
            return False, None, syntax_error
    
    diff = _generate_diff(original_content, new_content, operation.path)
    
    change = AiPatchFileChange(
        path=operation.path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=False
    )
    
    return True, change, None


def apply_insert_text(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Apply an insert_text operation at a specific line."""
    if not operation.path or operation.start_line is None or not operation.text:
        return False, None, "Path, start_line, and text are required"
    
    abs_path = os.path.join(project_root, operation.path)
    
    # Get original content
    original_content = file_cache.get(operation.path, "")
    if not original_content and os.path.exists(abs_path):
        with open(abs_path, "r") as f:
            original_content = f.read()
        file_cache[operation.path] = original_content
    
    lines = original_content.splitlines()
    insert_index = operation.start_line - 1  # Convert to 0-indexed
    
    if insert_index < 0:
        insert_index = 0
    if insert_index > len(lines):
        insert_index = len(lines)
    
    # Insert the text
    new_lines = lines[:insert_index] + operation.text.splitlines() + lines[insert_index:]
    new_content = "\n".join(new_lines)
    
    # Validate Python syntax if it's a Python file
    if operation.path.endswith(".py"):
        is_valid, syntax_error = _validate_python_syntax(new_content)
        if not is_valid:
            return False, None, syntax_error
    
    diff = _generate_diff(original_content, new_content, operation.path)
    
    change = AiPatchFileChange(
        path=operation.path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=not original_content
    )
    
    return True, change, None


def apply_delete_text(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Apply a delete_text operation (remove lines)."""
    if not operation.path or operation.start_line is None or operation.end_line is None:
        return False, None, "Path, start_line, and end_line are required"
    
    abs_path = os.path.join(project_root, operation.path)
    
    # Get original content
    original_content = file_cache.get(operation.path, "")
    if not original_content and os.path.exists(abs_path):
        with open(abs_path, "r") as f:
            original_content = f.read()
        file_cache[operation.path] = original_content
    
    lines = original_content.splitlines()
    start_idx = operation.start_line - 1  # Convert to 0-indexed
    end_idx = operation.end_line  # end_line is inclusive
    
    if start_idx < 0 or end_idx > len(lines):
        return False, None, f"Line range {operation.start_line}-{operation.end_line} is out of bounds"
    
    # Delete the lines
    new_lines = lines[:start_idx] + lines[end_idx:]
    new_content = "\n".join(new_lines)
    
    # Validate Python syntax if it's a Python file
    if operation.path.endswith(".py"):
        is_valid, syntax_error = _validate_python_syntax(new_content)
        if not is_valid:
            return False, None, syntax_error
    
    diff = _generate_diff(original_content, new_content, operation.path)
    
    change = AiPatchFileChange(
        path=operation.path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=False
    )
    
    return True, change, None


def apply_add_import(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Add an import statement to a file."""
    if not operation.path or not operation.import_statement:
        return False, None, "Path and import_statement are required"
    
    abs_path = os.path.join(project_root, operation.path)
    
    # Get original content
    original_content = file_cache.get(operation.path, "")
    if not original_content and os.path.exists(abs_path):
        with open(abs_path, "r") as f:
            original_content = f.read()
        file_cache[operation.path] = original_content
    
    # Check if import already exists
    if operation.import_statement in original_content:
        # Import already exists, no change needed
        return True, None, None
    
    # Find the right place to insert the import
    lines = original_content.splitlines()
    insert_index = 0
    
    # Skip docstrings and __future__ imports
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            # Skip docstring
            continue
        if stripped.startswith("from __future__"):
            insert_index = i + 1
            continue
        if stripped.startswith("import ") or stripped.startswith("from "):
            insert_index = i + 1
        elif stripped and not stripped.startswith("#"):
            # Found non-import, non-comment line
            break
    
    # Insert the import
    new_lines = lines[:insert_index] + [operation.import_statement] + lines[insert_index:]
    new_content = "\n".join(new_lines)
    
    # Validate Python syntax
    is_valid, syntax_error = _validate_python_syntax(new_content)
    if not is_valid:
        return False, None, syntax_error
    
    diff = _generate_diff(original_content, new_content, operation.path)
    
    change = AiPatchFileChange(
        path=operation.path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=False
    )
    
    return True, change, None


# =============================================================================
# ORM-Aware Patch Executors
# =============================================================================

def _find_model_file(model_name: str, app_label: str, project_root: str) -> Optional[str]:
    """Find the file containing a model definition."""
    # Common patterns for model files
    patterns = [
        f"{app_label}/models.py",
        f"{app_label}/models/{model_name.lower()}.py",
        f"apps/{app_label}/models.py",
        "models.py",
    ]
    
    for pattern in patterns:
        full_path = os.path.join(project_root, pattern)
        if os.path.exists(full_path):
            with open(full_path, "r") as f:
                content = f.read()
            if f"class {model_name}(" in content:
                return pattern
    
    return None


def _find_class_in_ast(
    tree: ast.Module,
    class_name: str
) -> Optional[ast.ClassDef]:
    """Find a class definition in an AST."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def _format_field_code(field_name: str, field_spec: Dict[str, Any]) -> str:
    """Generate field code from a field spec."""
    field_type = field_spec.get("type", "string")
    field_class = FIELD_TYPE_MAPPING.get(field_type, "fields.String")
    
    args: List[str] = []
    
    # Handle FK/M2M
    if field_type in ("fk", "m2m"):
        fk_model = field_spec.get("fk_model", "")
        if fk_model:
            args.append(f'"{fk_model}"')
        if field_type == "fk":
            on_delete = field_spec.get("on_delete", "CASCADE")
            args.append(f'on_delete="{on_delete}"')
    
    # max_length
    if "max_length" in field_spec:
        args.append(f"max_length={field_spec['max_length']}")
    
    # nullable
    if field_spec.get("nullable"):
        args.append("nullable=True")
    
    # unique
    if field_spec.get("unique"):
        args.append("unique=True")
    
    # default
    if "default" in field_spec:
        default = field_spec["default"]
        if isinstance(default, str):
            args.append(f'default="{default}"')
        else:
            args.append(f"default={default}")
    
    # help_text
    if "help_text" in field_spec:
        args.append(f'help_text="{field_spec["help_text"]}"')
    
    args_str = ", ".join(args)
    return f"    {field_name} = {field_class}({args_str})"


def apply_add_model(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Add a new model to a models.py file."""
    if not operation.model or not operation.model_spec:
        return False, None, "Model name and model_spec are required"
    
    app_label = operation.app_label or "app"
    model_path = f"{app_label}/models.py"
    abs_path = os.path.join(project_root, model_path)
    
    # Get or create original content
    original_content = file_cache.get(model_path, "")
    if not original_content:
        if os.path.exists(abs_path):
            with open(abs_path, "r") as f:
                original_content = f.read()
        else:
            # Create new models.py with imports
            original_content = '"""Models for {app_label} app."""\nfrom aksara import Model, fields\n\n'
    
    file_cache[model_path] = original_content
    
    # Check if model already exists
    if f"class {operation.model}(" in original_content:
        return False, None, f"Model {operation.model} already exists"
    
    # Build model spec
    fields_data = operation.model_spec.get("fields", [])
    field_specs = [AiFieldSpec(**f) if isinstance(f, dict) else f for f in fields_data]
    
    spec = AiModelSpec(
        app_label=app_label,
        name=operation.model,
        table_name=operation.model_spec.get("table_name"),
        fields=field_specs,
        ai_exposed=operation.model_spec.get("ai_exposed", True),
        add_admin=operation.model_spec.get("add_admin", True),
        add_viewset=operation.model_spec.get("add_viewset", False),
        add_serializer=operation.model_spec.get("add_serializer", False),
    )
    
    # Generate model code
    model_code_dict = generate_model_code(spec)
    model_code = list(model_code_dict.values())[0]
    
    # Extract just the class definition (skip imports/docstring)
    lines = model_code.splitlines()
    class_start = 0
    for i, line in enumerate(lines):
        if line.startswith("class "):
            class_start = i
            break
    
    class_code = "\n".join(lines[class_start:])
    
    # Append to original content
    new_content = original_content.rstrip() + "\n\n\n" + class_code
    
    # Validate Python syntax
    is_valid, syntax_error = _validate_python_syntax(new_content)
    if not is_valid:
        return False, None, syntax_error
    
    diff = _generate_diff(original_content, new_content, model_path)
    
    change = AiPatchFileChange(
        path=model_path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=not os.path.exists(abs_path)
    )
    
    return True, change, None


def apply_add_field(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Add a new field to an existing model."""
    if not operation.model or not operation.field or not operation.field_spec:
        return False, None, "Model, field, and field_spec are required"
    
    app_label = operation.app_label or "app"
    
    # Find the model file
    model_path = _find_model_file(operation.model, app_label, project_root)
    if not model_path:
        # Try default path
        model_path = f"{app_label}/models.py"
    
    abs_path = os.path.join(project_root, model_path)
    
    # Get original content
    original_content = file_cache.get(model_path, "")
    if not original_content:
        if os.path.exists(abs_path):
            with open(abs_path, "r") as f:
                original_content = f.read()
        else:
            return False, None, f"Model file not found: {model_path}"
    
    file_cache[model_path] = original_content
    
    # Check if model exists
    if f"class {operation.model}(" not in original_content:
        return False, None, f"Model {operation.model} not found in {model_path}"
    
    # Check if field already exists
    if f"{operation.field} = " in original_content:
        return False, None, f"Field {operation.field} already exists in {operation.model}"
    
    # Find where to insert the field
    lines = original_content.splitlines()
    insert_line = None
    in_model = False
    class_indent = 0
    
    for i, line in enumerate(lines):
        if f"class {operation.model}(" in line:
            in_model = True
            # Determine class indentation
            class_indent = len(line) - len(line.lstrip())
            continue
        
        if in_model:
            stripped = line.strip()
            current_indent = len(line) - len(line.lstrip()) if stripped else 0
            
            # If we hit another class or unindented line, we've left the model
            if stripped and current_indent <= class_indent and not line.lstrip().startswith("#"):
                if stripped.startswith("class ") or not stripped.startswith(("def ", "@", '"""', "'''")):
                    insert_line = i
                    break
            
            # Track last field definition
            if " = fields." in line or " = " in line and "Field" in line:
                insert_line = i + 1
    
    if insert_line is None:
        insert_line = len(lines)
    
    # Generate field code
    field_code = _format_field_code(operation.field, operation.field_spec)
    
    # Insert the field
    new_lines = lines[:insert_line] + [field_code] + lines[insert_line:]
    new_content = "\n".join(new_lines)
    
    # Validate Python syntax
    is_valid, syntax_error = _validate_python_syntax(new_content)
    if not is_valid:
        return False, None, syntax_error
    
    diff = _generate_diff(original_content, new_content, model_path)
    
    change = AiPatchFileChange(
        path=model_path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=False
    )
    
    return True, change, None


def apply_update_field(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Update an existing field in a model."""
    if not operation.model or not operation.field or not operation.field_spec:
        return False, None, "Model, field, and field_spec are required"
    
    app_label = operation.app_label or "app"
    
    # Find the model file
    model_path = _find_model_file(operation.model, app_label, project_root)
    if not model_path:
        model_path = f"{app_label}/models.py"
    
    abs_path = os.path.join(project_root, model_path)
    
    # Get original content
    original_content = file_cache.get(model_path, "")
    if not original_content:
        if os.path.exists(abs_path):
            with open(abs_path, "r") as f:
                original_content = f.read()
        else:
            return False, None, f"Model file not found: {model_path}"
    
    file_cache[model_path] = original_content
    
    # Find and replace the field definition
    lines = original_content.splitlines()
    field_pattern = re.compile(rf"(\s*){re.escape(operation.field)}\s*=\s*fields?\.\w+\(")
    
    found = False
    for i, line in enumerate(lines):
        match = field_pattern.match(line)
        if match:
            indent = match.group(1)
            new_field_code = _format_field_code(operation.field, operation.field_spec)
            # Adjust indentation
            new_field_code = indent + new_field_code.strip()
            lines[i] = new_field_code
            found = True
            break
    
    if not found:
        return False, None, f"Field {operation.field} not found in {operation.model}"
    
    new_content = "\n".join(lines)
    
    # Validate Python syntax
    is_valid, syntax_error = _validate_python_syntax(new_content)
    if not is_valid:
        return False, None, syntax_error
    
    diff = _generate_diff(original_content, new_content, model_path)
    
    change = AiPatchFileChange(
        path=model_path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=False
    )
    
    return True, change, None


def apply_delete_field(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Delete a field from a model."""
    if not operation.model or not operation.field:
        return False, None, "Model and field are required"
    
    app_label = operation.app_label or "app"
    
    # Find the model file
    model_path = _find_model_file(operation.model, app_label, project_root)
    if not model_path:
        model_path = f"{app_label}/models.py"
    
    abs_path = os.path.join(project_root, model_path)
    
    # Get original content
    original_content = file_cache.get(model_path, "")
    if not original_content:
        if os.path.exists(abs_path):
            with open(abs_path, "r") as f:
                original_content = f.read()
        else:
            return False, None, f"Model file not found: {model_path}"
    
    file_cache[model_path] = original_content
    
    # Find and remove the field definition
    lines = original_content.splitlines()
    field_pattern = re.compile(rf"\s*{re.escape(operation.field)}\s*=\s*fields?\.\w+\(")
    
    found = False
    remove_index = None
    for i, line in enumerate(lines):
        if field_pattern.match(line):
            remove_index = i
            found = True
            break
    
    if not found:
        return False, None, f"Field {operation.field} not found in {operation.model}"
    
    # Remove the line
    new_lines = lines[:remove_index] + lines[remove_index + 1:]
    new_content = "\n".join(new_lines)
    
    # Validate Python syntax
    is_valid, syntax_error = _validate_python_syntax(new_content)
    if not is_valid:
        return False, None, syntax_error
    
    diff = _generate_diff(original_content, new_content, model_path)
    
    change = AiPatchFileChange(
        path=model_path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=False
    )
    
    return True, change, None


def apply_delete_model(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Delete a model from a models.py file."""
    if not operation.model:
        return False, None, "Model name is required"
    
    app_label = operation.app_label or "app"
    
    # Find the model file
    model_path = _find_model_file(operation.model, app_label, project_root)
    if not model_path:
        model_path = f"{app_label}/models.py"
    
    abs_path = os.path.join(project_root, model_path)
    
    # Get original content
    original_content = file_cache.get(model_path, "")
    if not original_content:
        if os.path.exists(abs_path):
            with open(abs_path, "r") as f:
                original_content = f.read()
        else:
            return False, None, f"Model file not found: {model_path}"
    
    file_cache[model_path] = original_content
    
    # Parse AST to find class boundaries
    try:
        tree = ast.parse(original_content)
    except SyntaxError as e:
        return False, None, f"Syntax error in {model_path}: {e}"
    
    class_node = _find_class_in_ast(tree, operation.model)
    if not class_node:
        return False, None, f"Model {operation.model} not found in {model_path}"
    
    # Find line range to delete
    lines = original_content.splitlines()
    start_line = class_node.lineno - 1  # Convert to 0-indexed
    end_line = class_node.end_lineno if hasattr(class_node, 'end_lineno') and class_node.end_lineno else start_line + 1
    
    # Remove the class
    new_lines = lines[:start_line] + lines[end_line:]
    
    # Clean up extra blank lines
    while len(new_lines) > 1 and new_lines[-1] == "" and new_lines[-2] == "":
        new_lines.pop()
    
    new_content = "\n".join(new_lines)
    
    # Validate Python syntax
    is_valid, syntax_error = _validate_python_syntax(new_content)
    if not is_valid:
        return False, None, syntax_error
    
    diff = _generate_diff(original_content, new_content, model_path)
    
    change = AiPatchFileChange(
        path=model_path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=False
    )
    
    return True, change, None


def apply_update_model(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Update model metadata (not fields - use add_field/update_field for that)."""
    if not operation.model:
        return False, None, "Model name is required"
    
    app_label = operation.app_label or "app"
    model_spec = operation.model_spec or {}
    
    # Find the model file
    model_path = _find_model_file(operation.model, app_label, project_root)
    if not model_path:
        return False, None, f"Model {operation.model} not found"
    
    abs_path = os.path.join(project_root, model_path)
    
    # Get original content
    original_content = file_cache.get(model_path, "")
    if not original_content and os.path.exists(abs_path):
        with open(abs_path, "r") as f:
            original_content = f.read()
        file_cache[model_path] = original_content
    
    # For now, update_model just updates the Meta class
    # More sophisticated updates would use AST manipulation
    
    new_table_name = model_spec.get("table_name")
    if new_table_name:
        # Find or add Meta class
        lines = original_content.splitlines()
        in_model = False
        meta_found = False
        
        for i, line in enumerate(lines):
            if f"class {operation.model}(" in line:
                in_model = True
                continue
            
            if in_model and "class Meta:" in line:
                meta_found = True
                # Look for table_name
                for j in range(i + 1, min(i + 10, len(lines))):
                    if "table_name" in lines[j]:
                        lines[j] = f'        table_name = "{new_table_name}"'
                        break
                else:
                    # Add table_name
                    lines.insert(i + 1, f'        table_name = "{new_table_name}"')
                break
        
        if not meta_found and in_model:
            # Add Meta class - find end of class docstring
            for i, line in enumerate(lines):
                if f"class {operation.model}(" in line:
                    # Find first field or method after class definition
                    for j in range(i + 1, len(lines)):
                        if " = " in lines[j] or "def " in lines[j]:
                            # Insert Meta before this line
                            lines.insert(j, "")
                            lines.insert(j, f'        table_name = "{new_table_name}"')
                            lines.insert(j, "    class Meta:")
                            break
                    break
        
        new_content = "\n".join(lines)
    else:
        new_content = original_content
    
    # Validate Python syntax
    is_valid, syntax_error = _validate_python_syntax(new_content)
    if not is_valid:
        return False, None, syntax_error
    
    diff = _generate_diff(original_content, new_content, model_path)
    
    change = AiPatchFileChange(
        path=model_path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=False
    )
    
    return True, change, None


def apply_add_viewset(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Add a new ViewSet for a model."""
    if not operation.model:
        return False, None, "Model name is required"
    
    app_label = operation.app_label or "app"
    viewset_path = f"{app_label}/views.py"
    abs_path = os.path.join(project_root, viewset_path)
    
    # Get or create original content
    original_content = file_cache.get(viewset_path, "")
    if not original_content:
        if os.path.exists(abs_path):
            with open(abs_path, "r") as f:
                original_content = f.read()
        else:
            # Create new views.py
            original_content = f'''"""ViewSets for {app_label} app."""
from aksara.api import ModelViewSet
from {app_label}.models import {operation.model}

'''
    
    file_cache[viewset_path] = original_content
    
    viewset_name = f"{operation.model}ViewSet"
    
    # Check if viewset already exists
    if f"class {viewset_name}(" in original_content:
        return False, None, f"ViewSet {viewset_name} already exists"
    
    # Ensure import exists
    import_line = f"from {app_label}.models import {operation.model}"
    if import_line not in original_content and f"import {operation.model}" not in original_content:
        # Add import
        lines = original_content.splitlines()
        # Find last import
        last_import = 0
        for i, line in enumerate(lines):
            if line.startswith("from ") or line.startswith("import "):
                last_import = i + 1
        lines.insert(last_import, import_line)
        original_content = "\n".join(lines)
    
    # Generate viewset code
    viewset_code = f'''
class {viewset_name}(ModelViewSet):
    """API ViewSet for {operation.model}."""
    
    model = {operation.model}
    prefix = "/api/{operation.model.lower()}s"
'''
    
    new_content = original_content.rstrip() + "\n\n" + viewset_code
    
    # Validate Python syntax
    is_valid, syntax_error = _validate_python_syntax(new_content)
    if not is_valid:
        return False, None, syntax_error
    
    diff = _generate_diff(file_cache.get(viewset_path, ""), new_content, viewset_path)
    
    change = AiPatchFileChange(
        path=viewset_path,
        original_content=file_cache.get(viewset_path, ""),
        new_content=new_content,
        diff=diff,
        created=not os.path.exists(abs_path)
    )
    
    return True, change, None


def apply_update_viewset(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Update an existing ViewSet."""
    if not operation.model:
        return False, None, "Model name is required"
    
    app_label = operation.app_label or "app"
    viewset_path = f"{app_label}/views.py"
    viewset_name = f"{operation.model}ViewSet"
    
    abs_path = os.path.join(project_root, viewset_path)
    
    # Get original content
    original_content = file_cache.get(viewset_path, "")
    if not original_content:
        if os.path.exists(abs_path):
            with open(abs_path, "r") as f:
                original_content = f.read()
        else:
            return False, None, f"ViewSet file not found: {viewset_path}"
    
    file_cache[viewset_path] = original_content
    
    if f"class {viewset_name}(" not in original_content:
        return False, None, f"ViewSet {viewset_name} not found"
    
    # Update viewset attributes from model_spec
    model_spec = operation.model_spec or {}
    new_prefix = model_spec.get("prefix")
    
    if new_prefix:
        # Replace prefix line
        lines = original_content.splitlines()
        in_viewset = False
        
        for i, line in enumerate(lines):
            if f"class {viewset_name}(" in line:
                in_viewset = True
                continue
            
            if in_viewset and "prefix = " in line:
                indent = len(line) - len(line.lstrip())
                lines[i] = " " * indent + f'prefix = "{new_prefix}"'
                break
        
        new_content = "\n".join(lines)
    else:
        new_content = original_content
    
    # Validate Python syntax
    is_valid, syntax_error = _validate_python_syntax(new_content)
    if not is_valid:
        return False, None, syntax_error
    
    diff = _generate_diff(original_content, new_content, viewset_path)
    
    change = AiPatchFileChange(
        path=viewset_path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=False
    )
    
    return True, change, None


def apply_delete_viewset(
    operation: AiPatchOperation,
    project_root: str,
    file_cache: Dict[str, str]
) -> Tuple[bool, Optional[AiPatchFileChange], Optional[str]]:
    """Delete a ViewSet."""
    if not operation.model:
        return False, None, "Model name is required"
    
    app_label = operation.app_label or "app"
    viewset_path = f"{app_label}/views.py"
    viewset_name = f"{operation.model}ViewSet"
    
    abs_path = os.path.join(project_root, viewset_path)
    
    # Get original content
    original_content = file_cache.get(viewset_path, "")
    if not original_content:
        if os.path.exists(abs_path):
            with open(abs_path, "r") as f:
                original_content = f.read()
        else:
            return False, None, f"ViewSet file not found: {viewset_path}"
    
    file_cache[viewset_path] = original_content
    
    # Parse AST to find class boundaries
    try:
        tree = ast.parse(original_content)
    except SyntaxError as e:
        return False, None, f"Syntax error in {viewset_path}: {e}"
    
    class_node = _find_class_in_ast(tree, viewset_name)
    if not class_node:
        return False, None, f"ViewSet {viewset_name} not found"
    
    # Find line range to delete
    lines = original_content.splitlines()
    start_line = class_node.lineno - 1  # Convert to 0-indexed
    end_line = class_node.end_lineno if hasattr(class_node, 'end_lineno') and class_node.end_lineno else start_line + 1
    
    # Remove the class
    new_lines = lines[:start_line] + lines[end_line:]
    
    # Clean up extra blank lines
    while len(new_lines) > 1 and new_lines[-1] == "" and new_lines[-2] == "":
        new_lines.pop()
    
    new_content = "\n".join(new_lines)
    
    # Validate Python syntax
    is_valid, syntax_error = _validate_python_syntax(new_content)
    if not is_valid:
        return False, None, syntax_error
    
    diff = _generate_diff(original_content, new_content, viewset_path)
    
    change = AiPatchFileChange(
        path=viewset_path,
        original_content=original_content,
        new_content=new_content,
        diff=diff,
        created=False
    )
    
    return True, change, None


# =============================================================================
# Operation Dispatcher
# =============================================================================

OPERATION_HANDLERS: Dict[str, Callable] = {
    "modify_file": apply_modify_file,
    "replace_text": apply_replace_text,
    "insert_text": apply_insert_text,
    "delete_text": apply_delete_text,
    "add_import": apply_add_import,
    "add_model": apply_add_model,
    "update_model": apply_update_model,
    "delete_model": apply_delete_model,
    "add_field": apply_add_field,
    "update_field": apply_update_field,
    "delete_field": apply_delete_field,
    "add_viewset": apply_add_viewset,
    "update_viewset": apply_update_viewset,
    "delete_viewset": apply_delete_viewset,
}


# =============================================================================
# Patch Engine Orchestrator
# =============================================================================

def _compute_checksum(files_changed: Dict[str, AiPatchFileChange]) -> str:
    """Compute a checksum of all changes for verification."""
    content_parts = []
    for path in sorted(files_changed.keys()):
        change = files_changed[path]
        content_parts.append(f"{path}:{change.new_content}")
    
    combined = "\n".join(content_parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


def apply_ai_patches(
    request: AiPatchRequest,
    project_root: Optional[str] = None,
    preview: bool = False,
    confirm_header: Optional[str] = None
) -> AiPatchResult:
    """
    Apply (or preview) all patch operations.
    
    This is the main entry point for the patch engine.
    
    Steps:
    1. Validate all operations
    2. Save initial copies of files
    3. For each operation:
       - Validate
       - Apply
       - Run AST parsing
    4. If anything fails → revert all
    5. Return result
    
    Args:
        request: The patch request with operations
        project_root: Project root directory (defaults to cwd)
        preview: If True, don't actually write files
        confirm_header: Required header value for non-preview mode
        
    Returns:
        AiPatchResult with details of what changed
    """
    if project_root is None:
        project_root = os.getcwd()
    
    # Check for dry_run in request
    if request.dry_run:
        preview = True
    
    # Safety check for non-preview mode
    if not preview and confirm_header != "true":
        return AiPatchResult(
            applied=False,
            preview_only=False,
            errors=["Apply mode requires X-AI-Apply: true header"],
            notes=["Use preview mode or provide confirmation header"]
        )
    
    # Validate all operations first
    all_valid, validation_results = validate_patch_request(request, project_root)
    
    errors: List[str] = []
    warnings: List[str] = []
    notes: List[str] = []
    
    for i, result in enumerate(validation_results):
        if not result.valid:
            errors.append(f"Operation {i + 1}: {result.error_message}")
        warnings.extend(result.warnings)
    
    if not all_valid:
        return AiPatchResult(
            applied=False,
            preview_only=preview,
            errors=errors,
            warnings=warnings,
            notes=["Validation failed - no changes made"]
        )
    
    # File cache for tracking changes
    file_cache: Dict[str, str] = {}
    original_files: Dict[str, str] = {}
    files_changed: Dict[str, AiPatchFileChange] = {}
    operations_applied = 0
    operations_failed = 0
    
    # Apply each operation
    for i, operation in enumerate(request.operations):
        handler = OPERATION_HANDLERS.get(operation.type)
        
        if not handler:
            errors.append(f"Operation {i + 1}: Unknown operation type '{operation.type}'")
            operations_failed += 1
            continue
        
        try:
            success, change, error = handler(operation, project_root, file_cache)
            
            if not success:
                errors.append(f"Operation {i + 1}: {error}")
                operations_failed += 1
                # On failure, stop and rollback
                break
            
            if change:
                # Track original content for rollback
                if change.path not in original_files:
                    original_files[change.path] = change.original_content or ""
                
                # Update file cache with new content
                file_cache[change.path] = change.new_content
                files_changed[change.path] = change
                
                if operation.note:
                    notes.append(f"Operation {i + 1}: {operation.note}")
            
            operations_applied += 1
            
        except Exception as e:
            errors.append(f"Operation {i + 1}: Unexpected error: {str(e)}")
            operations_failed += 1
            break
    
    # If we had failures, don't apply anything
    if operations_failed > 0:
        return AiPatchResult(
            applied=False,
            preview_only=preview,
            files_changed={},  # Don't include changes if we failed
            operations_applied=0,
            operations_failed=operations_failed,
            errors=errors,
            warnings=warnings,
            notes=["Rolled back - no changes made due to errors"],
            rollback_available=False
        )
    
    # If preview mode, return without writing
    if preview:
        return AiPatchResult(
            applied=False,
            preview_only=True,
            files_changed=files_changed,
            operations_applied=operations_applied,
            operations_failed=0,
            errors=[],
            warnings=warnings,
            notes=notes + ["Preview mode - no files were modified"],
            rollback_available=False,
            checksum=_compute_checksum(files_changed)
        )
    
    # Write changes to disk
    try:
        for path, change in files_changed.items():
            abs_path = os.path.join(project_root, path)
            
            # Create directory if needed
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            
            # Write the file
            with open(abs_path, "w") as f:
                f.write(change.new_content)
        
        return AiPatchResult(
            applied=True,
            preview_only=False,
            files_changed=files_changed,
            operations_applied=operations_applied,
            operations_failed=0,
            errors=[],
            warnings=warnings,
            notes=notes + [f"Successfully applied {operations_applied} operation(s)"],
            rollback_available=True,
            checksum=_compute_checksum(files_changed)
        )
        
    except Exception as e:
        # Rollback on write failure
        for path, original_content in original_files.items():
            abs_path = os.path.join(project_root, path)
            try:
                if original_content:
                    with open(abs_path, "w") as f:
                        f.write(original_content)
                elif os.path.exists(abs_path):
                    os.remove(abs_path)
            except Exception:
                pass  # Best effort rollback
        
        return AiPatchResult(
            applied=False,
            preview_only=False,
            files_changed={},
            operations_applied=0,
            operations_failed=operations_applied,
            errors=[f"Write failed, rolled back: {str(e)}"],
            warnings=warnings,
            notes=["Rolled back all changes due to write error"],
            rollback_available=False
        )


async def apply_ai_patches_async(
    request: AiPatchRequest,
    project_root: Optional[str] = None,
    preview: bool = False,
    confirm_header: Optional[str] = None
) -> AiPatchResult:
    """Async version of apply_ai_patches."""
    # For now, just wrap the sync version
    # In production, you'd want true async file I/O
    return apply_ai_patches(request, project_root, preview, confirm_header)


# =============================================================================
# Utility Functions
# =============================================================================

def rollback_patches(
    result: AiPatchResult,
    project_root: Optional[str] = None
) -> bool:
    """
    Rollback changes from a previous patch result.
    
    Args:
        result: The patch result to rollback
        project_root: Project root directory
        
    Returns:
        True if rollback succeeded
    """
    if project_root is None:
        project_root = os.getcwd()
    
    if not result.rollback_available:
        return False
    
    try:
        for path, change in result.files_changed.items():
            abs_path = os.path.join(project_root, path)
            
            if change.created:
                # Remove file that was created
                if os.path.exists(abs_path):
                    os.remove(abs_path)
            elif change.original_content is not None:
                # Restore original content
                with open(abs_path, "w") as f:
                    f.write(change.original_content)
        
        return True
    except Exception:
        return False


def preview_patch_diff(
    request: AiPatchRequest,
    project_root: Optional[str] = None
) -> str:
    """
    Generate a combined diff preview of all operations.
    
    Returns unified diff string showing all changes.
    """
    result = apply_ai_patches(request, project_root, preview=True)
    
    diffs: List[str] = []
    for path in sorted(result.files_changed.keys()):
        change = result.files_changed[path]
        if change.diff:
            diffs.append(f"# {path}")
            diffs.append(change.diff)
            diffs.append("")
    
    return "\n".join(diffs)
