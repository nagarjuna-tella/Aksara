"""
Tests for v0.5.2 AST-based AI sandbox checks.
"""

from __future__ import annotations

from aksara.ai.patch import _contains_dangerous_code


class TestAstSandboxBypasses:
    """Tests for AST-based dangerous code detection."""

    def test_detects_getattr_import_bypass(self):
        """getattr(__import__(...), ...) should be blocked."""
        code = "getattr(__import__('os'), 'system')('id')"

        is_dangerous, message = _contains_dangerous_code(code)

        assert is_dangerous is True
        assert "getattr" in message.lower() or "import" in message.lower()

    def test_detects_importlib_import_module_bypass(self):
        """importlib.import_module(...).run() should be blocked."""
        code = "import importlib\nimportlib.import_module('subprocess').run(['id'])"

        is_dangerous, message = _contains_dangerous_code(code)

        assert is_dangerous is True
        assert "dynamic import" in message.lower() or "subprocess" in message.lower()

    def test_detects_base64_eval_bypass(self):
        """Decoded eval payloads should be blocked."""
        code = "import base64\neval(base64.b64decode(payload))"

        is_dangerous, message = _contains_dangerous_code(code)

        assert is_dangerous is True
        assert "eval" in message.lower()

    def test_detects_os_popen(self):
        """os.popen should be blocked by the AST layer as well."""
        code = "import os\nos.popen('id')"

        is_dangerous, message = _contains_dangerous_code(code)

        assert is_dangerous is True
        assert "os.popen" in message.lower() or "popen" in message.lower()

    def test_detects_ctypes_cdll(self):
        """ctypes.CDLL should be blocked."""
        code = "import ctypes\nctypes.CDLL(None)"

        is_dangerous, message = _contains_dangerous_code(code)

        assert is_dangerous is True
        assert "ctypes.cdll" in message.lower() or "cdll" in message.lower()

    def test_safe_code_passes(self):
        """Normal model code should remain allowed."""
        code = "class User:\n    def full_name(self):\n        return self.name"

        is_dangerous, message = _contains_dangerous_code(code)

        assert is_dangerous is False
        assert message is None

    def test_syntax_error_does_not_crash_detector(self):
        """Syntax errors should not crash the AST dangerous-code check."""
        code = "def broken(:\n    pass"

        is_dangerous, message = _contains_dangerous_code(code)

        assert is_dangerous is False
        assert message is None