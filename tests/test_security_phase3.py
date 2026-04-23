"""
Security Remediation Tests — Phase 3: AI Sandbox Hardening

Tests for:
- AST-based dangerous code detection
- Regex-based dangerous pattern detection
- Import/getattr/eval+decode obfuscation detection
"""

from __future__ import annotations

import pytest


# =============================================================================
# AST Dangerous Code Detection
# =============================================================================


class TestASTDangerousCodeCheck:
    """Tests for _ast_dangerous_code_check in aksara.ai.patch."""

    def test_detects_eval(self):
        """Should detect direct eval() calls."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check("result = eval('1+1')")
        assert any("eval" in v for v in violations)

    def test_detects_exec(self):
        """Should detect direct exec() calls."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check("exec('import os')")
        assert any("exec" in v for v in violations)

    def test_detects_compile(self):
        """Should detect compile() calls."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check("code = compile('pass', '<string>', 'exec')")
        assert any("compile" in v for v in violations)

    def test_detects_dunder_import(self):
        """Should detect __import__() calls."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check("mod = __import__('os')")
        assert any("__import__" in v for v in violations)

    def test_detects_os_system(self):
        """Should detect os.system() calls."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check("import os\nos.system('rm -rf /')")
        assert any("os.system" in v for v in violations)

    def test_detects_subprocess_run(self):
        """Should detect subprocess.run() calls."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check(
            "import subprocess\nsubprocess.run(['ls'])"
        )
        assert any("subprocess.run" in v for v in violations)

    def test_detects_subprocess_popen(self):
        """Should detect subprocess.Popen() calls."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check(
            "import subprocess\nsubprocess.Popen(['ls'])"
        )
        assert any("subprocess.Popen" in v or "Popen" in v for v in violations)

    def test_detects_shutil_rmtree(self):
        """Should detect shutil.rmtree() calls."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check(
            "import shutil\nshutil.rmtree('/tmp/data')"
        )
        assert any("shutil.rmtree" in v or "rmtree" in v for v in violations)

    def test_detects_importlib_import_module(self):
        """Should detect importlib.import_module() calls."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check(
            "import importlib\nimportlib.import_module('os')"
        )
        assert any("importlib" in v for v in violations)

    def test_detects_getattr_system(self):
        """Should detect getattr indirection to dangerous names."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check(
            "import os\ngetattr(os, 'system')('whoami')"
        )
        assert any("getattr" in v.lower() for v in violations)

    def test_detects_getattr_popen(self):
        """Should detect getattr(os, 'popen')."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check(
            "import os\nresult = getattr(os, 'popen')('ls')"
        )
        assert any("getattr" in v.lower() or "popen" in v for v in violations)

    def test_detects_eval_with_b64decode(self):
        """Should detect eval(base64.b64decode(...)) obfuscation pattern."""
        from aksara.ai.patch import _ast_dangerous_code_check

        code = (
            "import base64\n"
            "eval(base64.b64decode(b'cHJpbnQoIm93bmVkIik='))"
        )
        violations = _ast_dangerous_code_check(code)
        assert any("decoded" in v.lower() or "eval" in v for v in violations)

    def test_detects_exec_with_decode(self):
        """Should detect exec(bytes.decode(...)) pattern."""
        from aksara.ai.patch import _ast_dangerous_code_check

        code = "exec(b'print(1)'.decode('utf-8'))"
        violations = _ast_dangerous_code_check(code)
        assert any("decoded" in v.lower() or "exec" in v for v in violations)

    def test_allows_safe_code(self):
        """Should NOT flag safe code."""
        from aksara.ai.patch import _ast_dangerous_code_check

        safe_code = """
from aksara import Model, fields

class User(Model):
    class Meta:
        table_name = "users"
    
    name = fields.CharField(max_length=100)
    email = fields.EmailField()
    is_active = fields.BooleanField(default=True)
    
    def __str__(self):
        return self.name
"""
        violations = _ast_dangerous_code_check(safe_code)
        assert violations == []

    def test_allows_normal_imports(self):
        """Should NOT flag normal imports."""
        from aksara.ai.patch import _ast_dangerous_code_check

        safe_code = """
import json
import datetime
from pathlib import Path
from typing import Optional, List
"""
        violations = _ast_dangerous_code_check(safe_code)
        assert violations == []

    def test_handles_syntax_errors(self):
        """Should return empty list for code with syntax errors."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check("def broken(")
        assert violations == []

    def test_handles_empty_string(self):
        """Should return empty list for empty string."""
        from aksara.ai.patch import _ast_dangerous_code_check

        violations = _ast_dangerous_code_check("")
        assert violations == []


# =============================================================================
# Combined Pattern Detection (_contains_dangerous_code)
# =============================================================================


class TestContainsDangerousCode:
    """Tests for the combined regex + AST detection in _contains_dangerous_code."""

    def test_detect_os_system_regex(self):
        """Should detect os.system via regex fast path."""
        from aksara.ai.patch import _contains_dangerous_code

        is_dangerous, msg = _contains_dangerous_code("os.system('whoami')")
        assert is_dangerous is True
        assert msg is not None

    def test_detect_eval_regex(self):
        """Should detect eval via regex fast path."""
        from aksara.ai.patch import _contains_dangerous_code

        is_dangerous, msg = _contains_dangerous_code("eval('1+1')")
        assert is_dangerous is True

    def test_safe_code_passes(self):
        """Safe code should not be flagged."""
        from aksara.ai.patch import _contains_dangerous_code

        is_dangerous, msg = _contains_dangerous_code(
            "x = 1 + 2\nprint(x)"
        )
        assert is_dangerous is False
        assert msg is None

    def test_detect_getattr_obfuscation(self):
        """Should detect getattr-based obfuscation via AST check."""
        from aksara.ai.patch import _contains_dangerous_code

        code = "import os\ngetattr(os, 'system')('echo pwned')"
        is_dangerous, msg = _contains_dangerous_code(code)
        assert is_dangerous is True

    def test_detect_dynamic_import_then_call(self):
        """Should detect importlib.import_module('os').system('...')."""
        from aksara.ai.patch import _contains_dangerous_code

        code = "import importlib\nimportlib.import_module('os').system('ls')"
        is_dangerous, msg = _contains_dangerous_code(code)
        assert is_dangerous is True


# =============================================================================
# Helper Functions
# =============================================================================


class TestResolveCallName:
    """Tests for _resolve_call_name helper."""

    def test_resolves_simple_name(self):
        """Should resolve ast.Name to its id."""
        import ast
        from aksara.ai.patch import _resolve_call_name

        tree = ast.parse("foo()")
        call = tree.body[0].value
        assert _resolve_call_name(call.func) == "foo"

    def test_resolves_dotted_name(self):
        """Should resolve ast.Attribute to dotted name."""
        import ast
        from aksara.ai.patch import _resolve_call_name

        tree = ast.parse("os.path.join()")
        call = tree.body[0].value
        assert _resolve_call_name(call.func) == "os.path.join"

    def test_returns_none_for_complex(self):
        """Should return None for non-resolvable nodes."""
        import ast
        from aksara.ai.patch import _resolve_call_name

        tree = ast.parse("f()()")
        call = tree.body[0].value
        # The func is another Call node, not Name or Attribute
        assert _resolve_call_name(call.func) is None


class TestDangerousModulesCompleteness:
    """Verify that dangerous module/call sets are comprehensive."""

    def test_dangerous_ast_modules_includes_os(self):
        from aksara.ai.patch import DANGEROUS_AST_MODULES
        assert "os" in DANGEROUS_AST_MODULES

    def test_dangerous_ast_modules_includes_subprocess(self):
        from aksara.ai.patch import DANGEROUS_AST_MODULES
        assert "subprocess" in DANGEROUS_AST_MODULES

    def test_dangerous_ast_modules_includes_ctypes(self):
        from aksara.ai.patch import DANGEROUS_AST_MODULES
        assert "ctypes" in DANGEROUS_AST_MODULES

    def test_direct_dangerous_calls_includes_eval_exec(self):
        from aksara.ai.patch import DIRECT_DANGEROUS_CALLS
        assert "eval" in DIRECT_DANGEROUS_CALLS
        assert "exec" in DIRECT_DANGEROUS_CALLS
        assert "compile" in DIRECT_DANGEROUS_CALLS
        assert "__import__" in DIRECT_DANGEROUS_CALLS

    def test_attribute_dangerous_calls_comprehensive(self):
        from aksara.ai.patch import ATTRIBUTE_DANGEROUS_CALLS
        critical = [
            "os.system",
            "os.popen",
            "subprocess.run",
            "subprocess.Popen",
            "shutil.rmtree",
        ]
        for call in critical:
            assert call in ATTRIBUTE_DANGEROUS_CALLS, f"{call} missing from ATTRIBUTE_DANGEROUS_CALLS"

    def test_getattr_dangerous_names_comprehensive(self):
        from aksara.ai.patch import GETATTR_DANGEROUS_NAMES
        critical = ["system", "popen", "run", "Popen", "rmtree", "import_module"]
        for name in critical:
            assert name in GETATTR_DANGEROUS_NAMES, f"{name} missing from GETATTR_DANGEROUS_NAMES"
