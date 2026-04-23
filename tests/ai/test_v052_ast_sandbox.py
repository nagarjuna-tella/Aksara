"""
Tests for v0.5.2 AST-based AI sandbox checks.
"""

from __future__ import annotations

from aksara.ai.patch import validate_patch_ast


class TestAstSandboxBypasses:
    """Tests for AST-based dangerous code detection."""

    def test_detects_getattr_import_bypass(self):
        """getattr(__import__(...), ...) should be blocked."""
        code = "getattr(__import__('os'), 'system')('id')"

        valid, msg = validate_patch_ast(code)

        assert not valid
        assert "getattr" in msg.lower() or "import" in msg.lower()

    def test_detects_importlib_import_module_bypass(self):
        """importlib.import_module(...).run() should be blocked."""
        code = "import importlib\nimportlib.import_module('subprocess').run(['id'])"

        valid, msg = validate_patch_ast(code)

        assert not valid
        assert "import statements" in msg.lower() or "subprocess" in msg.lower()

    def test_detects_base64_eval_bypass(self):
        """Decoded eval payloads should be blocked."""
        code = "import base64\neval(base64.b64decode(payload))"

        valid, msg = validate_patch_ast(code)

        assert not valid
        assert "import statements" in msg.lower() or "eval" in msg.lower()

    def test_detects_os_popen(self):
        """os.popen should be blocked by the AST layer as well."""
        code = "import os\nos.popen('id')"

        valid, msg = validate_patch_ast(code)

        assert not valid
        assert "import statements" in msg.lower() or "popen" in msg.lower()

    def test_detects_ctypes_cdll(self):
        """ctypes.CDLL should be blocked."""
        code = "import ctypes\nctypes.CDLL(None)"

        valid, msg = validate_patch_ast(code)

        assert not valid
        assert "import statements" in msg.lower() or "cdll" in msg.lower()

    def test_safe_code_passes(self):
        """Normal model code should remain allowed."""
        code = "class User:\n    def full_name(self):\n        return self.name"

        valid, msg = validate_patch_ast(code)

        assert valid
        assert msg == ""

    def test_syntax_error_does_not_crash_detector(self):
        """Syntax errors should not crash the AST dangerous-code check."""
        code = "def broken(:\n    pass"

        valid, msg = validate_patch_ast(code)

        assert not valid
        assert "Syntax error" in msg