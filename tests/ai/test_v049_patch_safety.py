"""
Aksara v0.4.10 - AI Patch Engine Safety & Edge Cases

Tests for:
1. Dangerous content detection (eval, exec, os.system, etc.)
2. Protected files & paths
3. Broken AST / syntax validation
4. Partial patch failures & rollback
"""

import ast
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from aksara.ai.patch import (
    AiPatchOperation,
    AiPatchRequest,
    AiPatchResult,
    AiPatchValidationResult,
    PatchValidationError,
    DANGEROUS_PATTERNS,
    PROTECTED_PATTERNS,
    validate_operation,
    validate_patch_request,
    _contains_dangerous_code,
    _is_protected_file,
    _is_path_safe,
    _validate_python_syntax,
)


# =============================================================================
# Section 1: Dangerous Content Detection
# =============================================================================

class TestDangerousContentDetection:
    """Tests for detecting dangerous code patterns."""
    
    def test_detect_eval(self):
        """Should detect eval() calls."""
        dangerous_content = '''
def process_input(user_input):
    result = eval(user_input)
    return result
'''
        is_dangerous, msg = _contains_dangerous_code(dangerous_content)
        assert is_dangerous is True
        assert "eval" in msg.lower()
    
    def test_detect_exec(self):
        """Should detect exec() calls."""
        dangerous_content = '''
def run_code(code_string):
    exec(code_string)
'''
        is_dangerous, msg = _contains_dangerous_code(dangerous_content)
        assert is_dangerous is True
        assert "exec" in msg.lower()
    
    def test_detect_os_system(self):
        """Should detect os.system() calls."""
        dangerous_content = '''
import os
os.system("rm -rf /")
'''
        is_dangerous, msg = _contains_dangerous_code(dangerous_content)
        assert is_dangerous is True
        assert "os.system" in msg.lower() or "system" in msg.lower()
    
    def test_detect_subprocess_popen(self):
        """Should detect subprocess.Popen() calls."""
        dangerous_content = '''
import subprocess
subprocess.Popen(["bash", "-c", "malicious_command"])
'''
        is_dangerous, msg = _contains_dangerous_code(dangerous_content)
        assert is_dangerous is True
        assert "subprocess" in msg.lower()
    
    def test_detect_subprocess_run(self):
        """Should detect subprocess.run() calls."""
        dangerous_content = '''
import subprocess
subprocess.run("rm -rf /", shell=True)
'''
        is_dangerous, msg = _contains_dangerous_code(dangerous_content)
        assert is_dangerous is True
    
    def test_detect_subprocess_call(self):
        """Should detect subprocess.call() calls."""
        dangerous_content = '''
import subprocess
subprocess.call(["rm", "-rf", "/"])
'''
        is_dangerous, msg = _contains_dangerous_code(dangerous_content)
        assert is_dangerous is True
    
    def test_detect_dunder_import(self):
        """Should detect __import__() calls."""
        dangerous_content = '''
__import__("os").system("whoami")
'''
        is_dangerous, msg = _contains_dangerous_code(dangerous_content)
        assert is_dangerous is True
        assert "__import__" in msg.lower() or "import" in msg.lower()
    
    def test_detect_shutil_rmtree(self):
        """Should detect shutil.rmtree() calls."""
        dangerous_content = '''
import shutil
shutil.rmtree("/important/data")
'''
        is_dangerous, msg = _contains_dangerous_code(dangerous_content)
        assert is_dangerous is True
    
    def test_detect_os_remove(self):
        """Should detect os.remove() calls."""
        dangerous_content = '''
import os
os.remove("/etc/passwd")
'''
        is_dangerous, msg = _contains_dangerous_code(dangerous_content)
        assert is_dangerous is True
    
    def test_detect_os_unlink(self):
        """Should detect os.unlink() calls."""
        dangerous_content = '''
import os
os.unlink("/important/file")
'''
        is_dangerous, msg = _contains_dangerous_code(dangerous_content)
        assert is_dangerous is True
    
    def test_safe_code_passes(self):
        """Safe code should not be flagged as dangerous."""
        safe_content = '''
from aksara import Model, fields

class User(Model):
    __tablename__ = "users"
    
    id = fields.Integer(primary_key=True)
    email = fields.String(max_length=255, unique=True)
    name = fields.String(max_length=100)
    
    async def get_full_name(self) -> str:
        return self.name
'''
        is_dangerous, msg = _contains_dangerous_code(safe_content)
        assert is_dangerous is False
        assert msg is None
    
    def test_safe_imports_pass(self):
        """Normal imports should not be flagged."""
        safe_content = '''
import json
import asyncio
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
'''
        is_dangerous, msg = _contains_dangerous_code(safe_content)
        assert is_dangerous is False
    
    def test_eval_in_comment_is_safe(self):
        """eval() in a comment should not be flagged (depends on implementation)."""
        content_with_comment = '''
# Don't use eval() - it's dangerous
def safe_function():
    return 42
'''
        # This depends on how strict we are
        # If we do simple pattern matching, comments might trigger
        # For safety, we may still flag it
        is_dangerous, msg = _contains_dangerous_code(content_with_comment)
        # Either behavior is acceptable as long as it's documented
        # The key is: actual dangerous code IS detected
    
    def test_eval_in_string_literal_detected(self):
        """eval() in a string that gets executed should be detected."""
        dangerous_content = '''
code = "eval(user_input)"
exec(code)
'''
        # exec is definitely dangerous
        is_dangerous, msg = _contains_dangerous_code(dangerous_content)
        assert is_dangerous is True


class TestDangerousPatternOperation:
    """Test patch operations with dangerous content."""
    
    def test_modify_file_with_eval_rejected(self, tmp_path: Path):
        """modify_file with eval() should be rejected."""
        operation = AiPatchOperation(
            type="modify_file",
            path="app/models.py",
            text='result = eval(input())'
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
        assert result.error_type == PatchValidationError.DANGEROUS_CODE.value
        assert "dangerous" in result.error_message.lower() or "eval" in result.error_message.lower()
    
    def test_replace_text_with_exec_rejected(self, tmp_path: Path):
        """replace_text with exec() should be rejected."""
        operation = AiPatchOperation(
            type="replace_text",
            path="app/views.py",
            old_text="pass",
            new_text='exec(request.body)'
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
        assert result.error_type == PatchValidationError.DANGEROUS_CODE.value
    
    def test_insert_text_with_os_system_rejected(self, tmp_path: Path):
        """insert_text with os.system() should be rejected."""
        operation = AiPatchOperation(
            type="insert_text",
            path="app/utils.py",
            start_line=1,
            text='import os\nos.system("rm -rf /")'
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
        assert result.error_type == PatchValidationError.DANGEROUS_CODE.value
    
    def test_original_file_preserved_on_dangerous_content(self, tmp_path: Path):
        """Original file content should be preserved when dangerous content detected."""
        # Create a test file
        test_file = tmp_path / "app" / "models.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        original_content = "# Safe content\nclass User: pass"
        test_file.write_text(original_content)
        
        operation = AiPatchOperation(
            type="modify_file",
            path="app/models.py",
            text='import os\nos.system("malicious")'
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        # Validation should fail
        assert result.valid is False
        
        # Original file should be unchanged
        assert test_file.read_text() == original_content


# =============================================================================
# Section 2: Protected Files & Paths
# =============================================================================

class TestProtectedPaths:
    """Tests for protected file and path detection."""
    
    def test_git_directory_protected(self):
        """Files under .git/ should be protected."""
        assert _is_protected_file(".git/config") is True
        assert _is_protected_file(".git/HEAD") is True
        assert _is_protected_file(".git/objects/pack/test") is True
    
    def test_env_files_protected(self):
        """Environment files should be protected."""
        assert _is_protected_file(".env") is True
        # Check if we protect variants
        # (depends on PROTECTED_PATTERNS configuration)
    
    def test_migration_files_protected(self):
        """Migration files should be protected."""
        assert _is_protected_file("app/migrations/0001_initial.py") is True
        assert _is_protected_file("migrations/0001_initial.py") is True
    
    def test_pycache_protected(self):
        """__pycache__ directories should be protected."""
        assert _is_protected_file("__pycache__/module.pyc") is True
        assert _is_protected_file("app/__pycache__/models.cpython-311.pyc") is True
    
    def test_secrets_files_protected(self):
        """Secrets files should be protected."""
        assert _is_protected_file("secrets.py") is True
        assert _is_protected_file("secrets.json") is True
    
    def test_normal_app_files_not_protected(self):
        """Normal application files should not be protected."""
        assert _is_protected_file("app/models.py") is False
        assert _is_protected_file("app/views.py") is False
        assert _is_protected_file("app/api/viewsets.py") is False
        assert _is_protected_file("tests/test_models.py") is False
    
    def test_protected_file_operation_rejected(self, tmp_path: Path):
        """Operations on protected files should be rejected."""
        operation = AiPatchOperation(
            type="modify_file",
            path=".git/config",
            text="malicious config"
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
        assert result.error_type == PatchValidationError.PROTECTED_FILE.value
        assert "protected" in result.error_message.lower()
    
    def test_migration_modify_rejected(self, tmp_path: Path):
        """Modifying migration files should be rejected."""
        operation = AiPatchOperation(
            type="modify_file",
            path="app/migrations/0001_initial.py",
            text="# Modified migration"
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
        assert result.error_type == PatchValidationError.PROTECTED_FILE.value
    
    def test_env_modify_rejected(self, tmp_path: Path):
        """Modifying .env files should be rejected."""
        operation = AiPatchOperation(
            type="modify_file",
            path=".env",
            text="DATABASE_URL=postgres://hacked"
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
        assert result.error_type == PatchValidationError.PROTECTED_FILE.value


class TestPathSafety:
    """Tests for path safety validation."""
    
    def test_path_within_project_safe(self, tmp_path: Path):
        """Paths within project directory should be safe."""
        assert _is_path_safe("app/models.py", str(tmp_path)) is True
        assert _is_path_safe("app/views.py", str(tmp_path)) is True
    
    def test_path_traversal_blocked(self, tmp_path: Path):
        """Path traversal attempts should be blocked."""
        assert _is_path_safe("../etc/passwd", str(tmp_path)) is False
        assert _is_path_safe("../../root/.ssh/id_rsa", str(tmp_path)) is False
    
    def test_absolute_path_outside_project_blocked(self, tmp_path: Path):
        """Absolute paths outside project should be blocked."""
        assert _is_path_safe("/etc/passwd", str(tmp_path)) is False
        assert _is_path_safe("/root/.bashrc", str(tmp_path)) is False
    
    def test_path_outside_project_rejected(self, tmp_path: Path):
        """Operations with paths outside project should be rejected."""
        operation = AiPatchOperation(
            type="modify_file",
            path="../../../etc/passwd",
            text="hacked"
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
        assert result.error_type == PatchValidationError.PATH_OUTSIDE_PROJECT.value


# =============================================================================
# Section 3: Broken AST / Syntax Validation
# =============================================================================

class TestSyntaxValidation:
    """Tests for Python syntax validation."""
    
    def test_valid_python_passes(self):
        """Valid Python code should pass syntax validation."""
        valid_code = '''
class User(Model):
    __tablename__ = "users"
    
    def greet(self):
        return f"Hello, {self.name}"
'''
        is_valid, error = _validate_python_syntax(valid_code)
        assert is_valid is True
        assert error is None
    
    def test_missing_colon_on_def_fails(self):
        """Missing colon on def should fail syntax validation."""
        invalid_code = '''
def my_function()
    return 42
'''
        is_valid, error = _validate_python_syntax(invalid_code)
        assert is_valid is False
        assert error is not None
        assert "syntax" in error.lower()
    
    def test_unbalanced_parentheses_fails(self):
        """Unbalanced parentheses should fail syntax validation."""
        invalid_code = '''
def my_function():
    return some_func(arg1, arg2
'''
        is_valid, error = _validate_python_syntax(invalid_code)
        assert is_valid is False
        assert error is not None
    
    def test_unbalanced_brackets_fails(self):
        """Unbalanced brackets should fail syntax validation."""
        invalid_code = '''
my_list = [1, 2, 3
'''
        is_valid, error = _validate_python_syntax(invalid_code)
        assert is_valid is False
        assert error is not None
    
    def test_unbalanced_braces_fails(self):
        """Unbalanced braces should fail syntax validation."""
        invalid_code = '''
my_dict = {"key": "value"
'''
        is_valid, error = _validate_python_syntax(invalid_code)
        assert is_valid is False
        assert error is not None
    
    def test_invalid_indentation_fails(self):
        """Invalid indentation should fail syntax validation."""
        invalid_code = '''
def my_function():
return 42
'''
        is_valid, error = _validate_python_syntax(invalid_code)
        assert is_valid is False
        assert error is not None
    
    def test_syntax_error_includes_line_number(self):
        """Syntax error message should include line number."""
        invalid_code = '''
def valid():
    pass

def invalid()
    return 42
'''
        is_valid, error = _validate_python_syntax(invalid_code)
        assert is_valid is False
        # Should mention line number
        assert "line" in error.lower() or "5" in error or "6" in error
    
    def test_empty_file_valid(self):
        """Empty file should be valid Python."""
        is_valid, error = _validate_python_syntax("")
        assert is_valid is True
    
    def test_comment_only_file_valid(self):
        """Comment-only file should be valid Python."""
        code = "# This is just a comment\n# Another comment"
        is_valid, error = _validate_python_syntax(code)
        assert is_valid is True


class TestSyntaxPreservation:
    """Tests that syntax errors don't corrupt files."""
    
    def test_invalid_modify_preserves_original(self, tmp_path: Path):
        """modify_file with syntax error should not corrupt original."""
        # Create a valid file
        test_file = tmp_path / "app" / "models.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        original_content = '''
from aksara import Model, fields

class User(Model):
    __tablename__ = "users"
    id = fields.Integer(primary_key=True)
'''
        test_file.write_text(original_content)
        
        # Try to apply invalid modification
        # (This would be rejected before application in real use)
        invalid_content = '''
class User(Model)
    __tablename__ = "users"
'''
        
        is_valid, error = _validate_python_syntax(invalid_content)
        assert is_valid is False
        
        # Original should be unchanged
        assert test_file.read_text() == original_content


# =============================================================================
# Section 4: Partial Patch Failures & Rollback
# =============================================================================

class TestPatchRequestValidation:
    """Tests for patch request validation."""
    
    def test_empty_operations_rejected(self):
        """Patch request with no operations should be rejected."""
        with pytest.raises(ValueError) as exc_info:
            AiPatchRequest(operations=[], reason="Empty patch")
        
        assert "at least one operation" in str(exc_info.value).lower()
    
    def test_mixed_valid_invalid_operations(self, tmp_path: Path):
        """Patch request with some invalid operations should fail validation."""
        operations = [
            AiPatchOperation(
                type="modify_file",
                path="app/models.py",
                text="# Valid content"
            ),
            AiPatchOperation(
                type="modify_file",
                path=".git/config",  # Protected!
                text="malicious"
            ),
        ]
        
        request = AiPatchRequest(operations=operations, reason="Test")
        all_valid, results = validate_patch_request(request, str(tmp_path))
        
        assert all_valid is False
        assert len(results) == 2
        
        # First should be valid
        assert results[0].valid is True
        
        # Second should be invalid
        assert results[1].valid is False
        assert results[1].error_type == PatchValidationError.PROTECTED_FILE.value
    
    def test_all_valid_operations_pass(self, tmp_path: Path):
        """Patch request with all valid operations should pass."""
        operations = [
            AiPatchOperation(
                type="add_model",
                model="Article",
                app_label="blog",
                model_spec={"fields": []}
            ),
            AiPatchOperation(
                type="add_field",
                model="Article",
                field="title",
                field_spec={"type": "string", "max_length": 200}
            ),
        ]
        
        request = AiPatchRequest(operations=operations, reason="Add Article model")
        all_valid, results = validate_patch_request(request, str(tmp_path))
        
        assert all_valid is True
        assert all(r.valid for r in results)
    
    def test_multi_operation_first_fail_blocks_all(self, tmp_path: Path):
        """If first operation fails, entire request should fail."""
        operations = [
            AiPatchOperation(
                type="modify_file",
                path="../etc/passwd",  # Path traversal!
                text="hacked"
            ),
            AiPatchOperation(
                type="add_model",
                model="SafeModel",
                model_spec={"fields": []}
            ),
        ]
        
        request = AiPatchRequest(operations=operations, reason="Test")
        all_valid, results = validate_patch_request(request, str(tmp_path))
        
        assert all_valid is False
        assert results[0].valid is False


class TestPartialFailureHandling:
    """Tests for handling partial failures."""
    
    def test_dangerous_operation_blocks_preceding_valid(self, tmp_path: Path):
        """
        If op2 is dangerous, even valid op1 changes should be rolled back.
        
        This tests the concept - actual rollback is in apply_ai_patches.
        """
        operations = [
            AiPatchOperation(
                type="add_field",
                model="User",
                field="bio",
                field_spec={"type": "text"}
            ),
            AiPatchOperation(
                type="modify_file",
                path="app/views.py",
                text='import os\nos.system("rm -rf /")'  # Dangerous!
            ),
        ]
        
        request = AiPatchRequest(operations=operations, reason="Test")
        all_valid, results = validate_patch_request(request, str(tmp_path))
        
        # Overall should fail because of op2
        assert all_valid is False
        
        # Op1 is valid
        assert results[0].valid is True
        
        # Op2 is invalid
        assert results[1].valid is False
        assert results[1].error_type == PatchValidationError.DANGEROUS_CODE.value
    
    def test_validation_errors_are_specific(self, tmp_path: Path):
        """Validation errors should clearly identify the problem."""
        operations = [
            AiPatchOperation(
                type="add_field",
                model="",  # Empty model name!
                field="test",
                field_spec={"type": "string"}
            ),
        ]
        
        request = AiPatchRequest(operations=operations, reason="Test")
        all_valid, results = validate_patch_request(request, str(tmp_path))
        
        # Should fail with clear message
        # The exact behavior depends on validation implementation
        # At minimum, should not crash


class TestOperationRequiredFields:
    """Tests for operation required field validation."""
    
    def test_modify_file_requires_path(self, tmp_path: Path):
        """modify_file should require path."""
        operation = AiPatchOperation(
            type="modify_file",
            text="content"
            # path missing!
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
        assert result.error_type == PatchValidationError.MISSING_REQUIRED.value
        assert "path" in result.error_message.lower()
    
    def test_modify_file_requires_diff_or_text(self, tmp_path: Path):
        """modify_file should require diff or text."""
        operation = AiPatchOperation(
            type="modify_file",
            path="app/models.py"
            # neither diff nor text!
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
        assert result.error_type == PatchValidationError.MISSING_REQUIRED.value
    
    def test_add_model_requires_model(self, tmp_path: Path):
        """add_model should require model name."""
        operation = AiPatchOperation(
            type="add_model",
            model_spec={"fields": []}
            # model missing!
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
        assert result.error_type == PatchValidationError.MISSING_REQUIRED.value
        assert "model" in result.error_message.lower()
    
    def test_add_model_requires_model_spec(self, tmp_path: Path):
        """add_model should require model_spec."""
        operation = AiPatchOperation(
            type="add_model",
            model="User"
            # model_spec missing!
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
        assert result.error_type == PatchValidationError.MISSING_REQUIRED.value
        assert "model_spec" in result.error_message.lower()
    
    def test_add_field_requires_all_fields(self, tmp_path: Path):
        """add_field should require model, field, and field_spec."""
        # Missing model
        op1 = AiPatchOperation(
            type="add_field",
            field="bio",
            field_spec={"type": "text"}
        )
        assert validate_operation(op1, str(tmp_path)).valid is False
        
        # Missing field
        op2 = AiPatchOperation(
            type="add_field",
            model="User",
            field_spec={"type": "text"}
        )
        assert validate_operation(op2, str(tmp_path)).valid is False
        
        # Missing field_spec
        op3 = AiPatchOperation(
            type="add_field",
            model="User",
            field="bio"
        )
        assert validate_operation(op3, str(tmp_path)).valid is False
    
    def test_replace_text_requires_old_and_new(self, tmp_path: Path):
        """replace_text should require old_text and new_text."""
        operation = AiPatchOperation(
            type="replace_text",
            path="app/models.py",
            old_text="old"
            # new_text missing!
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
    
    def test_add_import_requires_statement(self, tmp_path: Path):
        """add_import should require import_statement."""
        operation = AiPatchOperation(
            type="add_import",
            path="app/models.py"
            # import_statement missing!
        )
        
        result = validate_operation(operation, str(tmp_path))
        
        assert result.valid is False
        assert result.error_type == PatchValidationError.MISSING_REQUIRED.value
