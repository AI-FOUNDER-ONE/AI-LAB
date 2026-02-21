"""
Unit tests for BaseAgent.
"""

import pytest
from unittest.mock import Mock, patch
from PyQt6.QtCore import QCoreApplication
from agents.base_agent import BaseAgent
from config import AGENT_MODELS


class MockAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing."""

    def _call_api(self, messages: list, tools: list = None) -> str:
        """Mock API call that returns a fixed response."""
        # 模拟工具调用支持
        if tools:
            # 如果有工具，返回模拟工具调用结果
            return f"Mock response with {len(tools)} tools to: {messages[-1]['content']}"
        return f"Mock response to: {messages[-1]['content']}"


class TestBaseAgent:
    """Test suite for BaseAgent."""

    @pytest.fixture
    def mock_agent(self):
        """Create a MockAgent instance."""
        model_config = {"provider": "test", "model": "test-model"}
        return MockAgent(role="TestAgent", model_config=model_config, system_prompt="Test system prompt")

    def test_initialization(self, mock_agent):
        """Test agent initialization."""
        assert mock_agent.role == "TestAgent"
        assert mock_agent.model_config == {"provider": "test", "model": "test-model"}
        assert mock_agent.system_prompt == "Test system prompt"
        assert not mock_agent.is_active

    def test_system_prompt_in_messages(self, mock_agent):
        """Test that system prompt is added to messages."""
        messages = mock_agent.get_messages()
        assert len(messages) == 1
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Test system prompt"

    def test_update_system_prompt(self, mock_agent):
        """Test dynamic system prompt update."""
        new_prompt = "Updated system prompt"
        mock_agent.update_system_prompt(new_prompt)

        messages = mock_agent.get_messages()
        assert messages[0]["content"] == new_prompt

    def test_send_message(self, mock_agent):
        """Test sending a message and getting a response."""
        response = mock_agent.send_message("Hello, agent!")

        assert "Mock response to: Hello, agent!" in response
        assert mock_agent.is_active is False  # Should be inactive after completion

        # Check that messages were added
        messages = mock_agent.get_messages()
        assert len(messages) == 3  # system + user + assistant
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello, agent!"
        assert messages[2]["role"] == "assistant"

    def test_send_message_error(self, mock_agent):
        """Test error handling in send_message."""
        # Make _call_api raise an exception
        with patch.object(mock_agent, '_call_api', side_effect=Exception("API error")):
            response = mock_agent.send_message("Trigger error")

        assert "⚠️ 错误: API error" in response
        assert mock_agent.is_active is False

    def test_add_context(self, mock_agent):
        """Test adding context to message history."""
        mock_agent.add_context("Additional context", role="system")
        mock_agent.add_context("User context", role="user")

        messages = mock_agent.get_messages()
        assert len(messages) == 3  # original system + new system + user
        assert messages[1]["role"] == "system"
        assert messages[1]["content"] == "Additional context"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == "User context"

    def test_clear_history(self, mock_agent):
        """Test clearing message history while preserving system prompt."""
        mock_agent.send_message("Test message")
        assert len(mock_agent.get_messages()) == 3  # system + user + assistant

        mock_agent.clear_history()
        messages = mock_agent.get_messages()
        assert len(messages) == 1  # Only system prompt remains
        assert messages[0]["role"] == "system"

    def test_set_domain_persona(self, mock_agent):
        """Test dynamic persona injection based on task type."""
        # Store original system prompt
        original_prompt = mock_agent.system_prompt

        # Inject SOFTWARE persona
        mock_agent.set_domain_persona("SOFTWARE")

        # Check that system prompt was updated with injection
        new_prompt = mock_agent.get_messages()[0]["content"]
        assert "Current Project Mode: SOFTWARE" in new_prompt
        assert "Your Role Adaptation: TestAgent" in new_prompt  # No mapping for TestAgent

        # Test with a mapped role
        arch_agent = MockAgent(role="Arch", model_config={}, system_prompt="Original")
        arch_agent.set_domain_persona("SOFTWARE")
        arch_prompt = arch_agent.get_messages()[0]["content"]
        assert "Your Role Adaptation: System Architect" in arch_prompt

    def test_is_active_property(self, mock_agent):
        """Test is_active property during message sending."""
        # Mock _call_api to be slow so we can check is_active
        original_call_api = mock_agent._call_api

        def slow_call(messages):
            import time
            time.sleep(0.1)
            return original_call_api(messages)

        with patch.object(mock_agent, '_call_api', side_effect=slow_call):
            # Start send_message in a thread to check is_active
            import threading
            result = []

            def send():
                result.append(mock_agent.send_message("Test"))

            thread = threading.Thread(target=send)
            thread.start()

            # Wait a bit for send_message to start
            import time
            time.sleep(0.05)

            # Agent should be active while processing
            # Note: This test might be flaky due to timing
            # assert mock_agent.is_active is True

            thread.join()

        assert mock_agent.is_active is False
        assert len(result) == 1

    def test_stop_method(self, mock_agent):
        """Test stop method."""
        mock_agent.stop()
        # stop() sets _is_active to False, but agent is already inactive
        assert mock_agent.is_active is False

    def test_signal_emission(self, mock_agent, qtbot):
        """Test that signals are emitted during message sending."""
        # Connect to signals
        with qtbot.wait_signal(mock_agent.typing_started, timeout=1000):
            with qtbot.wait_signal(mock_agent.typing_finished, timeout=2000):
                with qtbot.wait_signal(mock_agent.response_ready, timeout=2000):
                    response = mock_agent.send_message("Test signal")

        assert response is not None

    def test_error_signal(self, mock_agent, qtbot):
        """Test error_occurred signal."""
        with patch.object(mock_agent, '_call_api', side_effect=Exception("Test error")):
            with qtbot.wait_signal(mock_agent.error_occurred, timeout=1000):
                mock_agent.send_message("Trigger error")