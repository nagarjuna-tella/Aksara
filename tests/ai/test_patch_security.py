import pytest
from aksara.ai.patch import validate_patch_ast
from aksara.exceptions import PatchRejectedError

def test_reject_os_system():
    code = "import os\nos.system('rm -rf /')"
    valid, msg = validate_patch_ast(code)
    assert not valid
    assert "Dangerous pattern detected" in msg

def test_reject_builtins_eval():
    code = "__builtins__['eval']('print(1)')"
    valid, msg = validate_patch_ast(code)
    assert not valid
    assert "Dangerous pattern detected" in msg

def test_reject_subprocess_import():
    code = "import subprocess as sp\nsp.run(['ls'])"
    valid, msg = validate_patch_ast(code)
    assert not valid
    assert "Dangerous pattern detected" in msg

def test_reject_attribute_subclasses():
    code = "().__class__.__bases__[0].__subclasses__()"
    valid, msg = validate_patch_ast(code)
    assert not valid
    assert "Dangerous pattern detected" in msg

def test_accept_legitimate_patch():
    code = "a = 1\nb = [x for x in range(10)]\nprint(a)"
    valid, msg = validate_patch_ast(code)
    assert valid
    assert msg == ""

def test_reject_syntax_error():
    code = "def foo(:\n    pass"
    valid, msg = validate_patch_ast(code)
    assert not valid
    assert "Syntax error" in msg
