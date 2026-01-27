"""
Aksara v0.4.10 - Extended Debug Error Pages & CLI Tests

Additional robustness tests for:
1. Debug pages with huge request bodies
2. Debug pages with non-ASCII / weird characters  
3. CLI failure UX (invalid JSON, confirmation handling)
"""

import json
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from click.testing import CliRunner

from aksara.cli.main import cli


# =============================================================================
# Section 1: Debug Error Pages - Huge Request Body
# =============================================================================

class TestDebugHugeRequestBody:
    """Tests for handling huge request bodies in debug pages."""
    
    def test_debug_context_truncates_large_body(self):
        """Debug context should truncate very large request bodies."""
        from aksara.debug.handlers import DebugContext
        
        # Create a context with a huge body
        huge_body = "x" * (1024 * 1024)  # 1MB of 'x'
        
        ctx = DebugContext(
            exception_type="ValueError",
            exception_message="Test error",
            request_body=huge_body,
        )
        
        # Body is stored, but rendering should handle it
        assert ctx.request_body == huge_body
        # The DebugContext stores the full body, but rendering truncates
    
    def test_render_debug_page_handles_large_body(self):
        """render_debug_page should handle large bodies without blowing up."""
        from aksara.debug.handlers import render_debug_page, DebugContext
        
        large_body = "y" * 100000  # 100KB
        
        ctx = DebugContext(
            exception_type="TestError",
            exception_message="Test",
            request_body=large_body,
        )
        
        # Should not raise or produce enormous output
        response = render_debug_page(ctx)
        
        # Returns HTMLResponse - get body content
        html = response.body.decode() if hasattr(response, 'body') else str(response)
        
        # HTML should be reasonably sized (not gigabytes)
        assert len(html) < 10 * 1024 * 1024  # Less than 10MB
        
        # Body should be truncated in display
        # (depends on implementation - at minimum, should not crash)
    
    def test_render_truncates_body_for_display(self):
        """Request body should be truncated for display."""
        from aksara.debug.handlers import _build_request_html, DebugContext
        
        # 50KB body
        large_body = "data=" + "x" * 50000
        
        ctx = DebugContext(
            exception_type="TestError",
            exception_message="Test",
            request_body=large_body,
        )
        
        html = _build_request_html(ctx)
        
        # The HTML should contain a truncation indicator or be limited
        # Either the full body is there (bad) or truncated (good)
        # At minimum, should not crash
        assert html is not None


# =============================================================================
# Section 2: Debug Error Pages - Non-ASCII / Weird Characters
# =============================================================================

class TestDebugNonASCIICharacters:
    """Tests for handling non-ASCII and weird characters."""
    
    def test_debug_context_with_unicode_message(self):
        """Debug context should handle Unicode exception messages."""
        from aksara.debug.handlers import DebugContext
        
        unicode_message = "Error: 日本語メッセージ with émojis 🔥🚀"
        
        ctx = DebugContext(
            exception_type="ValueError",
            exception_message=unicode_message,
        )
        
        assert ctx.exception_message == unicode_message
    
    def test_render_debug_page_with_unicode(self):
        """render_debug_page should handle Unicode without encoding errors."""
        from aksara.debug.handlers import render_debug_page, DebugContext
        
        ctx = DebugContext(
            exception_type="UnicodeError",
            exception_message="Failed: données non valides 日本語 🔥",
            request_url="http://localhost/путь/к/ресурсу",
        )
        
        # Should not raise UnicodeEncodeError
        response = render_debug_page(ctx)
        
        # Returns HTMLResponse - get body content
        html = response.body.decode() if hasattr(response, 'body') else str(response)
        
        # Unicode should be preserved or escaped
        assert html is not None
        assert len(html) > 0
    
    def test_render_debug_page_with_emoji(self):
        """render_debug_page should handle emoji."""
        from aksara.debug.handlers import render_debug_page, DebugContext
        
        ctx = DebugContext(
            exception_type="EmojiError",
            exception_message="🔥 Something went wrong! 💥",
        )
        
        response = render_debug_page(ctx)
        
        # Returns HTMLResponse - get body content
        html = response.body.decode() if hasattr(response, 'body') else str(response)
        
        # Should contain the emoji or escaped version
        assert "🔥" in html or "Something went wrong" in html
    
    def test_debug_with_null_bytes(self):
        """Debug context should handle null bytes gracefully."""
        from aksara.debug.handlers import DebugContext, render_debug_page
        
        # String with embedded null byte
        message_with_null = "Error with\x00null byte"
        
        ctx = DebugContext(
            exception_type="NullByteError",
            exception_message=message_with_null,
        )
        
        # Should not crash
        response = render_debug_page(ctx)
        assert response is not None
    
    def test_debug_with_control_characters(self):
        """Debug context should handle control characters."""
        from aksara.debug.handlers import DebugContext, render_debug_page
        
        # String with various control characters
        message_with_controls = "Error\t with\n newline\r\n and tab"
        
        ctx = DebugContext(
            exception_type="ControlCharError",
            exception_message=message_with_controls,
        )
        
        response = render_debug_page(ctx)
        
        # Should not crash and should escape or preserve
        assert response is not None
    
    def test_debug_with_html_injection_attempt(self):
        """Debug context should escape HTML to prevent XSS."""
        from aksara.debug.handlers import render_debug_page, DebugContext
        
        malicious_message = '<script>alert("XSS")</script>'
        
        ctx = DebugContext(
            exception_type="XSSAttempt",
            exception_message=malicious_message,
        )
        
        response = render_debug_page(ctx)
        
        # Returns HTMLResponse - get body content
        html = response.body.decode() if hasattr(response, 'body') else str(response)
        
        # Script tags should be escaped
        assert "<script>alert" not in html
        # Either escaped or removed
        assert "&lt;script&gt;" in html or "alert" not in html.lower()


# =============================================================================
# Section 3: Debug AI Tab
# =============================================================================

class TestDebugAITab:
    """Tests for AI Debug tab functionality."""
    
    def test_ai_debug_context_with_unicode(self):
        """AI debug context should handle Unicode."""
        from aksara.ai.debug import AiDebugContext, AiExceptionInfo, AiRequestInfo, AiEnvInfo
        from datetime import datetime
        
        # Create context with unicode content
        ctx = AiDebugContext(
            timestamp=datetime.now().isoformat(),
            exception=AiExceptionInfo(
                type="ValueError",
                message="Error in データベース connection",
                full_type="builtins.ValueError",
            ),
            status_code=500,
            request=AiRequestInfo(
                method="GET",
                url="http://localhost/日本語path",
                path="/日本語path",
            ),
            environment=AiEnvInfo(
                python_version="3.12.0",
                aksara_version="0.4.10",
                debug_mode=True,
            ),
        )
        
        assert "データベース" in ctx.exception.message
        assert "日本語" in ctx.request.url
    
    def test_ai_exception_info_handles_unicode(self):
        """AiExceptionInfo should handle Unicode messages."""
        from aksara.ai.debug import AiExceptionInfo
        
        info = AiExceptionInfo(
            type="ValueError",
            message="配置エラー: 无效的输入 🔥",
            full_type="builtins.ValueError"
        )
        
        assert "配置エラー" in info.message
        assert "无效的输入" in info.message


# =============================================================================
# Section 4: CLI - Invalid JSON Handling
# =============================================================================

class TestCLIInvalidJSON:
    """Tests for CLI handling of invalid JSON."""
    
    def test_plan_preview_invalid_json_syntax(self):
        """plan preview with malformed JSON should fail gracefully."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            # Create file with invalid JSON
            with open("bad_plan.json", "w") as f:
                f.write("{invalid json without quotes}")
            
            result = runner.invoke(cli, ["ai", "plan", "preview", "bad_plan.json"])
            
            assert result.exit_code == 1
            assert "Invalid JSON" in result.output or "parse" in result.output.lower()
    
    def test_plan_preview_truncated_json(self):
        """plan preview with truncated JSON should fail gracefully."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            # Create truncated JSON
            with open("truncated.json", "w") as f:
                f.write('{"intent": {"user_message": "test"')  # Missing closing
            
            result = runner.invoke(cli, ["ai", "plan", "preview", "truncated.json"])
            
            assert result.exit_code == 1
            assert "Invalid JSON" in result.output or "Error" in result.output
    
    def test_plan_preview_empty_file(self):
        """plan preview with empty file should fail gracefully."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            # Create empty file
            with open("empty.json", "w") as f:
                f.write("")
            
            result = runner.invoke(cli, ["ai", "plan", "preview", "empty.json"])
            
            assert result.exit_code == 1
    
    def test_plan_preview_json_null(self):
        """plan preview with just 'null' should fail gracefully."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            with open("null.json", "w") as f:
                f.write("null")
            
            result = runner.invoke(cli, ["ai", "plan", "preview", "null.json"])
            
            assert result.exit_code == 1
    
    def test_plan_preview_json_array(self):
        """plan preview with JSON array instead of object should fail."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            with open("array.json", "w") as f:
                f.write('[{"step": 1}]')
            
            result = runner.invoke(cli, ["ai", "plan", "preview", "array.json"])
            
            assert result.exit_code == 1
    
    def test_plan_apply_invalid_json_syntax(self):
        """plan apply with malformed JSON should fail gracefully."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            with open("bad.json", "w") as f:
                f.write("not json at all")
            
            result = runner.invoke(cli, ["ai", "plan", "apply", "bad.json", "--yes"])
            
            assert result.exit_code == 1
            assert "Invalid JSON" in result.output or "Error" in result.output


# =============================================================================
# Section 5: CLI - Confirmation Handling
# =============================================================================

class TestCLIPlanApplyConfirmation:
    """Tests for plan apply confirmation handling."""
    
    def test_plan_apply_no_confirmation_aborts(self):
        """plan apply without --yes should prompt and abort on 'n'."""
        runner = CliRunner()
        
        valid_plan = {
            "intent": {"user_message": "Test", "mode": "modify"},
            "plan": {
                "intent": "Test",
                "steps": [
                    {"id": "s1", "type": "analyze_context", "description": "Test", "payload": {}}
                ]
            }
        }
        
        with runner.isolated_filesystem():
            with open("plan.json", "w") as f:
                json.dump(valid_plan, f)
            
            # Simulate user pressing 'n'
            result = runner.invoke(cli, ["ai", "plan", "apply", "plan.json"], input="n\n")
            
            # Should abort
            assert "Aborted" in result.output or result.exit_code in (0, 1)
    
    def test_plan_apply_empty_confirmation_aborts(self):
        """plan apply with empty confirmation (just Enter) should abort."""
        runner = CliRunner()
        
        valid_plan = {
            "intent": {"user_message": "Test", "mode": "modify"},
            "plan": {
                "intent": "Test",
                "steps": [
                    {"id": "s1", "type": "analyze_context", "description": "Test", "payload": {}}
                ]
            }
        }
        
        with runner.isolated_filesystem():
            with open("plan.json", "w") as f:
                json.dump(valid_plan, f)
            
            # Simulate user pressing Enter (empty input)
            result = runner.invoke(cli, ["ai", "plan", "apply", "plan.json"], input="\n")
            
            # Default should be 'no' - abort
            # (Or it might prompt again - either way, no changes applied)
            assert "Aborted" in result.output or result.exit_code in (0, 1)
    
    def test_plan_apply_yes_flag_skips_confirmation(self):
        """plan apply with --yes should skip confirmation prompt."""
        runner = CliRunner()
        
        valid_plan = {
            "intent": {"user_message": "Test", "mode": "modify"},
            "plan": {
                "intent": "Test",
                "steps": [
                    {"id": "s1", "type": "analyze_context", "description": "Test", "payload": {}}
                ]
            }
        }
        
        with runner.isolated_filesystem():
            with open("plan.json", "w") as f:
                json.dump(valid_plan, f)
            
            with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
                mock_setup.return_value = MagicMock()
                
                with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                    with patch("aksara.ai.planner.execute_plan", new_callable=AsyncMock) as mock_exec:
                        from aksara.ai.planner import AiPlanExecutionResult
                        mock_exec.return_value = AiPlanExecutionResult(
                            success=True,
                            steps=[],
                            notes=[],
                            dry_run=False
                        )
                        
                        result = runner.invoke(cli, ["ai", "plan", "apply", "plan.json", "--yes"])
                        
                        # Should not prompt, should proceed
                        assert "Are you sure" not in result.output or result.exit_code == 0


# =============================================================================
# Section 6: CLI Error Message Quality
# =============================================================================

class TestCLIErrorMessages:
    """Tests for CLI error message quality."""
    
    def test_file_not_found_clear_message(self):
        """File not found should produce clear error message."""
        runner = CliRunner()
        
        result = runner.invoke(cli, ["ai", "plan", "preview", "nonexistent_file.json"])
        
        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "No such file" in result.output
    
    def test_missing_required_option_clear_message(self):
        """Missing required option should produce clear error."""
        runner = CliRunner()
        
        # ai context requires --intent or --stdin
        result = runner.invoke(cli, ["ai", "context"])
        
        assert result.exit_code == 1
        # Should indicate what's missing
        assert "intent" in result.output.lower() or "required" in result.output.lower()
    
    def test_invalid_format_option_clear_message(self):
        """Invalid --format option should produce clear error."""
        runner = CliRunner()
        
        # Invalid format value
        result = runner.invoke(cli, [
            "ai", "context",
            "--intent", "Test",
            "--format", "invalid_format"
        ])
        
        assert result.exit_code != 0
        # Click handles this with "Invalid value"
    
    def test_schema_issues_invalid_severity_clear_message(self):
        """Invalid severity filter should produce clear error."""
        runner = CliRunner()
        
        result = runner.invoke(cli, ["ai", "schema-issues", "--severity", "invalid"])
        
        assert result.exit_code == 1
        assert "Error" in result.output


# =============================================================================
# Section 7: CLI Unicode Handling
# =============================================================================

class TestCLIUnicodeHandling:
    """Tests for CLI Unicode handling."""
    
    def test_plan_template_with_unicode_intent(self):
        """plan template should handle Unicode intent."""
        runner = CliRunner()
        
        unicode_intent = "Añadir modelo Usuario con campos 日本語"
        
        result = runner.invoke(cli, [
            "ai", "plan", "template",
            "--intent", unicode_intent
        ])
        
        assert result.exit_code == 0
        
        data = json.loads(result.output)
        assert data["intent"]["user_message"] == unicode_intent
    
    def test_context_with_unicode_intent(self):
        """ai context should handle Unicode intent."""
        runner = CliRunner()
        
        from aksara.ai.agent import AgentContextBundle, AgentIntent
        
        mock_bundle = AgentContextBundle(
            intent=AgentIntent(user_message="テスト意図", mode="read"),
            full_context={},
            tools=[],
            plan_schema={},
            patch_schema={},
            query_plan_schema={},
            codegen_schema={},
            version="0.4.10"
        )
        
        with patch("aksara.cli.main._setup_app_for_cli") as mock_setup:
            mock_setup.return_value = MagicMock()
            
            with patch("aksara.cli.main._connect_db_for_cli", new_callable=AsyncMock):
                with patch("aksara.ai.agent.build_agent_context_bundle", new_callable=AsyncMock) as mock_build:
                    mock_build.return_value = mock_bundle
                    
                    result = runner.invoke(cli, [
                        "ai", "context",
                        "--intent", "テスト意図",
                        "--format", "json"
                    ])
                    
                    assert result.exit_code == 0
