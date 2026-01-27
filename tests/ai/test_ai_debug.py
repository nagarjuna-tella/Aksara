"""
Tests for Aksara AI Debug Assistant (v0.4.1).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.requests import Request
from starlette.testclient import TestClient

from aksara.ai.debug import (
    AiDebugContext,
    AiDebugSuggestion,
    AiExceptionInfo,
    AiRequestInfo,
    AiStackFrame,
    AiEnvInfo,
    AiViewInfo,
    AiToolRef,
    BaseAiDebugAdvisor,
    RuleBasedAiDebugAdvisor,
    build_ai_debug_context,
    classify_exception,
    default_advisor,
)


# =============================================================================
# Test Exception Classification
# =============================================================================


class TestClassifyException:
    """Tests for exception classification."""
    
    def test_classify_validation_error(self):
        """Test classification of validation errors."""
        from pydantic import ValidationError, BaseModel
        
        class TestModel(BaseModel):
            name: str
        
        try:
            TestModel()
        except ValidationError as e:
            result = classify_exception(e)
            assert result["is_validation_error"] is True
    
    def test_classify_key_error(self):
        """Test classification of KeyError (not validation)."""
        exc = KeyError("missing_key")
        result = classify_exception(exc)
        assert result["is_validation_error"] is False
        assert result["is_db_error"] is False
    
    def test_classify_db_error_by_message(self):
        """Test classification of database errors by message."""
        exc = Exception("relation 'users' does not exist in database")
        result = classify_exception(exc)
        assert result["is_db_error"] is True
    
    def test_classify_auth_error(self):
        """Test classification of auth errors."""
        exc = Exception("unauthorized access")
        result = classify_exception(exc)
        assert result["is_auth_error"] is True
    
    def test_classify_not_found(self):
        """Test classification of not found errors."""
        exc = Exception("Resource not found")
        result = classify_exception(exc)
        assert result["is_not_found"] is True
    
    def test_classify_timeout(self):
        """Test classification of timeout errors."""
        exc = TimeoutError("Connection timed out")
        result = classify_exception(exc)
        assert result["is_timeout"] is True
    
    def test_classify_connection_error(self):
        """Test classification of connection errors."""
        exc = ConnectionRefusedError("Connection refused")
        result = classify_exception(exc)
        assert result["is_connection_error"] is True


# =============================================================================
# Test Pydantic Models
# =============================================================================


class TestAiDebugModels:
    """Tests for AI debug Pydantic models."""
    
    def test_ai_stack_frame_creation(self):
        """Test AiStackFrame model creation."""
        frame = AiStackFrame(
            filename="/path/to/file.py",
            lineno=42,
            name="my_function",
            line="print('hello')",
            is_library=False,
        )
        assert frame.filename == "/path/to/file.py"
        assert frame.lineno == 42
        assert frame.name == "my_function"
        assert frame.is_library is False
    
    def test_ai_exception_info_creation(self):
        """Test AiExceptionInfo model creation."""
        info = AiExceptionInfo(
            type="ValueError",
            message="Invalid value",
            full_type="builtins.ValueError",
            is_validation_error=True,
        )
        assert info.type == "ValueError"
        assert info.is_validation_error is True
        assert info.is_db_error is False
    
    def test_ai_request_info_creation(self):
        """Test AiRequestInfo model creation."""
        info = AiRequestInfo(
            method="POST",
            url="http://localhost/api/users",
            path="/api/users",
            path_params={"id": 1},
            query_params={"page": "1"},
        )
        assert info.method == "POST"
        assert info.path_params == {"id": 1}
    
    def test_ai_debug_suggestion_confidence_bounds(self):
        """Test AiDebugSuggestion confidence bounds."""
        # Valid confidence
        suggestion = AiDebugSuggestion(
            title="Test",
            description="Test description",
            confidence=0.8,
            category="code",
        )
        assert suggestion.confidence == 0.8
        
        # Test bounds
        with pytest.raises(ValueError):
            AiDebugSuggestion(
                title="Test",
                description="Test description",
                confidence=1.5,  # Out of bounds
                category="code",
            )
    
    def test_ai_debug_context_to_llm_prompt(self):
        """Test LLM prompt generation from context."""
        context = AiDebugContext(
            timestamp="2024-01-01T00:00:00Z",
            exception=AiExceptionInfo(
                type="ValueError",
                message="Invalid input",
                full_type="builtins.ValueError",
            ),
            status_code=400,
            request=AiRequestInfo(
                method="POST",
                url="http://localhost/api/test",
                path="/api/test",
            ),
            environment=AiEnvInfo(
                python_version="3.11.0",
                aksara_version="0.4.1",
                debug_mode=True,
            ),
            suggestions=[
                AiDebugSuggestion(
                    title="Check Input",
                    description="Validate the input data",
                    confidence=0.9,
                    category="validation",
                )
            ],
        )
        
        prompt = context.to_llm_prompt()
        assert "ValueError" in prompt
        assert "Invalid input" in prompt
        assert "POST" in prompt
        assert "Check Input" in prompt
        assert "90%" in prompt


# =============================================================================
# Test Rule-Based Advisor
# =============================================================================


class TestRuleBasedAdvisor:
    """Tests for RuleBasedAiDebugAdvisor."""
    
    def test_advisor_validation_error_suggestions(self):
        """Test advisor generates suggestions for validation errors."""
        advisor = RuleBasedAiDebugAdvisor()
        
        context = AiDebugContext(
            timestamp="2024-01-01T00:00:00Z",
            exception=AiExceptionInfo(
                type="ValidationError",
                message="Field 'name' is required",
                full_type="pydantic.ValidationError",
                is_validation_error=True,
            ),
            status_code=422,
            request=AiRequestInfo(
                method="POST",
                url="http://localhost/api/test",
                path="/api/test",
            ),
            environment=AiEnvInfo(
                python_version="3.11.0",
                aksara_version="0.4.1",
                debug_mode=True,
            ),
        )
        
        suggestions = advisor.analyze(context)
        assert len(suggestions) > 0
        assert any("required" in s.title.lower() or "missing" in s.title.lower() for s in suggestions)
    
    def test_advisor_db_error_suggestions(self):
        """Test advisor generates suggestions for database errors."""
        advisor = RuleBasedAiDebugAdvisor()
        
        context = AiDebugContext(
            timestamp="2024-01-01T00:00:00Z",
            exception=AiExceptionInfo(
                type="ProgrammingError",
                message="relation 'users' does not exist",
                full_type="asyncpg.ProgrammingError",
                is_db_error=True,
            ),
            status_code=500,
            request=AiRequestInfo(
                method="GET",
                url="http://localhost/api/users",
                path="/api/users",
            ),
            environment=AiEnvInfo(
                python_version="3.11.0",
                aksara_version="0.4.1",
                debug_mode=True,
            ),
        )
        
        suggestions = advisor.analyze(context)
        assert len(suggestions) > 0
        assert any("table" in s.title.lower() or "migration" in s.description.lower() for s in suggestions)
    
    def test_advisor_auth_error_suggestions(self):
        """Test advisor generates suggestions for auth errors."""
        advisor = RuleBasedAiDebugAdvisor()
        
        context = AiDebugContext(
            timestamp="2024-01-01T00:00:00Z",
            exception=AiExceptionInfo(
                type="HTTPException",
                message="Not authenticated",
                full_type="fastapi.HTTPException",
                is_auth_error=True,
            ),
            status_code=401,
            request=AiRequestInfo(
                method="GET",
                url="http://localhost/api/secret",
                path="/api/secret",
            ),
            environment=AiEnvInfo(
                python_version="3.11.0",
                aksara_version="0.4.1",
                debug_mode=True,
            ),
        )
        
        suggestions = advisor.analyze(context)
        assert len(suggestions) > 0
        assert any("authentication" in s.title.lower() or "permission" in s.title.lower() for s in suggestions)
    
    def test_advisor_attribute_error_pattern(self):
        """Test advisor handles AttributeError pattern."""
        advisor = RuleBasedAiDebugAdvisor()
        
        context = AiDebugContext(
            timestamp="2024-01-01T00:00:00Z",
            exception=AiExceptionInfo(
                type="AttributeError",
                message="'NoneType' object has no attribute 'name'",
                full_type="builtins.AttributeError",
            ),
            status_code=500,
            request=AiRequestInfo(
                method="GET",
                url="http://localhost/api/test",
                path="/api/test",
            ),
            environment=AiEnvInfo(
                python_version="3.11.0",
                aksara_version="0.4.1",
                debug_mode=True,
            ),
        )
        
        suggestions = advisor.analyze(context)
        assert len(suggestions) > 0
        assert any("name" in s.title.lower() or "attribute" in s.title.lower() for s in suggestions)
    
    def test_advisor_key_error_pattern(self):
        """Test advisor handles KeyError pattern."""
        advisor = RuleBasedAiDebugAdvisor()
        
        context = AiDebugContext(
            timestamp="2024-01-01T00:00:00Z",
            exception=AiExceptionInfo(
                type="KeyError",
                message="'missing_key'",
                full_type="builtins.KeyError",
            ),
            status_code=500,
            request=AiRequestInfo(
                method="GET",
                url="http://localhost/api/test",
                path="/api/test",
            ),
            environment=AiEnvInfo(
                python_version="3.11.0",
                aksara_version="0.4.1",
                debug_mode=True,
            ),
        )
        
        suggestions = advisor.analyze(context)
        assert len(suggestions) > 0
        assert any("key" in s.title.lower() or "dictionary" in s.title.lower() for s in suggestions)
    
    def test_advisor_import_error_pattern(self):
        """Test advisor handles ImportError pattern."""
        advisor = RuleBasedAiDebugAdvisor()
        
        context = AiDebugContext(
            timestamp="2024-01-01T00:00:00Z",
            exception=AiExceptionInfo(
                type="ModuleNotFoundError",
                message="No module named 'missing_package'",
                full_type="builtins.ModuleNotFoundError",
            ),
            status_code=500,
            request=AiRequestInfo(
                method="GET",
                url="http://localhost/api/test",
                path="/api/test",
            ),
            environment=AiEnvInfo(
                python_version="3.11.0",
                aksara_version="0.4.1",
                debug_mode=True,
            ),
        )
        
        suggestions = advisor.analyze(context)
        assert len(suggestions) > 0
        assert any("missing_package" in s.title.lower() or "module" in s.title.lower() for s in suggestions)
    
    def test_advisor_max_suggestions(self):
        """Test advisor returns max 5 suggestions."""
        advisor = RuleBasedAiDebugAdvisor()
        
        # Create a context that would trigger many suggestions
        context = AiDebugContext(
            timestamp="2024-01-01T00:00:00Z",
            exception=AiExceptionInfo(
                type="Exception",
                message="validation required missing type expected extra unexpected",
                full_type="builtins.Exception",
                is_validation_error=True,
            ),
            status_code=422,
            request=AiRequestInfo(
                method="POST",
                url="http://localhost/api/test",
                path="/api/test",
            ),
            environment=AiEnvInfo(
                python_version="3.11.0",
                aksara_version="0.4.1",
                debug_mode=True,
            ),
        )
        
        suggestions = advisor.analyze(context)
        assert len(suggestions) <= 5
    
    def test_advisor_get_related_tools(self):
        """Test advisor returns related tools for db errors."""
        advisor = RuleBasedAiDebugAdvisor()
        
        context = AiDebugContext(
            timestamp="2024-01-01T00:00:00Z",
            exception=AiExceptionInfo(
                type="ProgrammingError",
                message="relation does not exist",
                full_type="asyncpg.ProgrammingError",
                is_db_error=True,
            ),
            status_code=500,
            request=AiRequestInfo(
                method="GET",
                url="http://localhost/api/test",
                path="/api/test",
            ),
            environment=AiEnvInfo(
                python_version="3.11.0",
                aksara_version="0.4.1",
                debug_mode=True,
            ),
        )
        
        tools = advisor.get_related_tools(context)
        assert len(tools) > 0
        assert all(isinstance(t, AiToolRef) for t in tools)


# =============================================================================
# Test Build AI Debug Context
# =============================================================================


class TestBuildAiDebugContext:
    """Tests for build_ai_debug_context function."""
    
    @pytest.mark.asyncio
    async def test_build_context_basic(self):
        """Test building basic AI debug context."""
        # Create a mock request
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "query_string": b"page=1",
            "headers": [(b"content-type", b"application/json")],
            "server": ("localhost", 8000),
        }
        request = Request(scope)
        
        exc = ValueError("Test error")
        
        context = await build_ai_debug_context(request, exc, 500)
        
        assert context.status_code == 500
        assert context.exception.type == "ValueError"
        assert context.exception.message == "Test error"
        assert context.request.method == "GET"
        assert context.request.path == "/api/test"
        assert context.environment.python_version is not None
        # Generic ValueError may not generate suggestions (that's OK)
    
    @pytest.mark.asyncio
    async def test_build_context_with_traceback(self):
        """Test building context with traceback."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "query_string": b"",
            "headers": [],
            "server": ("localhost", 8000),
        }
        request = Request(scope)
        
        try:
            raise ValueError("Test error with traceback")
        except ValueError as exc:
            context = await build_ai_debug_context(request, exc, 500)
            
            assert len(context.traceback_frames) > 0
            assert context.traceback_text != ""
            assert "ValueError" in context.traceback_text
    
    @pytest.mark.asyncio
    async def test_build_context_http_exception(self):
        """Test building context for HTTPException."""
        from fastapi import HTTPException
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "query_string": b"",
            "headers": [],
            "server": ("localhost", 8000),
        }
        request = Request(scope)
        
        exc = HTTPException(status_code=404, detail="Resource not found")
        
        context = await build_ai_debug_context(request, exc, 404)
        
        assert context.status_code == 404
        assert context.exception.detail == "Resource not found"
        assert context.exception.is_not_found is True
    
    @pytest.mark.asyncio
    async def test_build_context_with_custom_advisor(self):
        """Test building context with custom advisor."""
        
        class CustomAdvisor(BaseAiDebugAdvisor):
            def analyze(self, context):
                return [AiDebugSuggestion(
                    title="Custom Suggestion",
                    description="This is a custom suggestion",
                    confidence=1.0,
                    category="custom",
                )]
            
            def get_related_tools(self, context):
                return []
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "query_string": b"",
            "headers": [],
            "server": ("localhost", 8000),
        }
        request = Request(scope)
        
        exc = ValueError("Test")
        
        context = await build_ai_debug_context(request, exc, 500, advisor=CustomAdvisor())
        
        assert len(context.suggestions) == 1
        assert context.suggestions[0].title == "Custom Suggestion"
        assert context.suggestions[0].confidence == 1.0


# =============================================================================
# Test Default Advisor Instance
# =============================================================================


class TestDefaultAdvisor:
    """Tests for the default advisor instance."""
    
    def test_default_advisor_exists(self):
        """Test that default_advisor is available."""
        assert default_advisor is not None
        assert isinstance(default_advisor, RuleBasedAiDebugAdvisor)


# =============================================================================
# Test Integration with Debug Page
# =============================================================================


class TestDebugPageIntegration:
    """Tests for AI debug integration with debug page."""
    
    def test_build_ai_debug_html_with_context(self):
        """Test _build_ai_debug_html generates proper HTML."""
        from aksara.debug.handlers import _build_ai_debug_html
        
        context = AiDebugContext(
            timestamp="2024-01-01T00:00:00Z",
            exception=AiExceptionInfo(
                type="ValueError",
                message="Test error",
                full_type="builtins.ValueError",
                is_validation_error=True,
            ),
            status_code=400,
            request=AiRequestInfo(
                method="POST",
                url="http://localhost/api/test",
                path="/api/test",
            ),
            environment=AiEnvInfo(
                python_version="3.11.0",
                aksara_version="0.4.1",
                debug_mode=True,
            ),
            suggestions=[
                AiDebugSuggestion(
                    title="Test Suggestion",
                    description="Test description",
                    code_snippet="print('hello')",
                    confidence=0.9,
                    category="code",
                )
            ],
        )
        
        html = _build_ai_debug_html(context)
        
        assert "AI Debug" in html
        assert "Test Suggestion" in html
        assert "Test description" in html
        assert "print(&#x27;hello&#x27;)" in html  # HTML escaped
        assert "90%" in html  # Confidence
        assert "Validation Error" in html  # Classification tag
        assert "copyPrompt" in html  # Copy button
        assert "copyJson" in html  # Copy JSON button
    
    def test_build_ai_debug_html_none_context(self):
        """Test _build_ai_debug_html with None context returns empty."""
        from aksara.debug.handlers import _build_ai_debug_html
        
        html = _build_ai_debug_html(None)
        assert html == ""
    
    def test_build_ai_debug_html_no_suggestions(self):
        """Test _build_ai_debug_html with no suggestions."""
        from aksara.debug.handlers import _build_ai_debug_html
        
        context = AiDebugContext(
            timestamp="2024-01-01T00:00:00Z",
            exception=AiExceptionInfo(
                type="ValueError",
                message="Test error",
                full_type="builtins.ValueError",
            ),
            status_code=400,
            request=AiRequestInfo(
                method="POST",
                url="http://localhost/api/test",
                path="/api/test",
            ),
            environment=AiEnvInfo(
                python_version="3.11.0",
                aksara_version="0.4.1",
                debug_mode=True,
            ),
            suggestions=[],
        )
        
        html = _build_ai_debug_html(context)
        
        assert "No suggestions available" in html


# =============================================================================
# Test Settings
# =============================================================================


class TestAiDebugSettings:
    """Tests for AI debug settings."""
    
    def test_ai_debug_enabled_default(self):
        """Test ai_debug_enabled defaults to True."""
        from aksara.conf import Settings
        
        settings = Settings()
        assert settings.ai_debug_enabled is True
    
    def test_ai_debug_advisor_class_default(self):
        """Test ai_debug_advisor_class defaults to None."""
        from aksara.conf import Settings
        
        settings = Settings()
        assert settings.ai_debug_advisor_class is None
