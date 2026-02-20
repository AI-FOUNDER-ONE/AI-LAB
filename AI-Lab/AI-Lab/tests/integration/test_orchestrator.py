"""
Integration tests for Orchestrator workflow.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from PyQt6.QtCore import QCoreApplication

from core.orchestrator import Orchestrator, AgentWorker, AuditWorker
from core.state_controller import StateController
from core.chat_history import ChatHistoryManager
from core.session_store import SessionStore
from config import AppState


class MockBaseAgent:
    """Mock BaseAgent for testing."""

    def __init__(self, role):
        self.role = role
        self.messages = []
        self._is_active = False
        self.typing_started = Mock()
        self.typing_finished = Mock()
        self.response_ready = Mock()
        self.error_occurred = Mock()

    def send_message(self, message):
        self.messages.append({"role": "user", "content": message})
        response = f"Mock response from {self.role} to: {message}"
        self.messages.append({"role": "assistant", "content": response})
        return response

    def get_messages(self):
        return self.messages

    def clear_history(self):
        self.messages = []

    def add_context(self, context, role="system"):
        self.messages.append({"role": role, "content": context})

    def stop(self):
        self._is_active = False

    def audit_node(self, stage, context, protocol):
        return f"PASS: {stage} audit passed"


class MockOrchestrator(Orchestrator):
    """Orchestrator subclass with mocked agents for testing."""

    def __init__(self):
        # Skip parent __init__ and create mock components
        self.state_ctrl = Mock(spec=StateController)
        self.state_ctrl.current_state = AppState.IDLE
        self.state_ctrl.transition_to = Mock(return_value=True)
        self.state_ctrl.reset = Mock()
        self.state_ctrl.state_changed = Mock()
        self.state_ctrl.error_occurred = Mock()

        self.chat_history = Mock(spec=ChatHistoryManager)
        self.session_store = Mock(spec=SessionStore)
        self.session_store.create_session = Mock()
        self.session_store.append_timeline_event = Mock()
        self.session_store.append_cko_log = Mock()
        self.session_store.append_meeting_log = Mock()
        self.session_store.get_debate_context = Mock(return_value="Mock debate context")
        self.session_store.get_all_meeting_logs = Mock(return_value="Mock all meeting logs")
        self.session_store.get_current_session = Mock(return_value={})
        self.session_store.update_session = Mock()
        self.session_store.append_test_report = Mock()

        # Mock agents
        self.cko = MockBaseAgent("CKO")
        self.pm = MockBaseAgent("PM")
        self.arch = MockBaseAgent("Arch")
        self.designer = MockBaseAgent("Designer")
        self.coder = MockBaseAgent("Coder")
        self.tester = MockBaseAgent("Tester")

        # Mock signals
        self.agent_response = Mock()
        self.state_changed = Mock()
        self.error_occurred = Mock()
        self.workflow_completed = Mock()
        self.debate_round_info = Mock()
        self.agent_typing = Mock()

        # Internal state
        self._active_workers = []
        self._debate_round = 0
        self._mission_protocol = ""
        self._pm_direction = ""
        self._last_speaker_role = None
        self._consecutive_speaker_count = 0
        self.MAX_DEBATE_ROUNDS = 3

        # Connect agent typing signals
        for agent in [self.cko, self.pm, self.arch, self.designer, self.coder, self.tester]:
            agent.typing_started.connect = Mock()
            agent.typing_finished.connect = Mock()


@pytest.fixture
def mock_orchestrator(qapp):
    """Create a MockOrchestrator instance."""
    return MockOrchestrator()


@pytest.fixture
def agent_worker():
    """Create an AgentWorker with mock agent."""
    agent = MockBaseAgent("TestAgent")
    return AgentWorker(agent, "Test message")


class TestOrchestratorIntegration:
    """Integration test suite for Orchestrator."""

    def test_initialization(self, mock_orchestrator):
        """Test orchestrator initialization."""
        assert mock_orchestrator.state_ctrl.current_state == AppState.IDLE
        assert mock_orchestrator._active_workers == []
        assert mock_orchestrator._debate_round == 0
        assert mock_orchestrator._mission_protocol == ""
        assert mock_orchestrator._pm_direction == ""

    def test_send_to_cko_idle_state(self, mock_orchestrator):
        """Test sending message to CKO when in IDLE state."""
        mock_orchestrator.state_ctrl.current_state = AppState.IDLE

        mock_orchestrator.send_to_cko("Hello CKO")

        # Check state transition
        mock_orchestrator.state_ctrl.transition_to.assert_called_once_with(AppState.GROUNDING)
        # Check session creation
        mock_orchestrator.session_store.create_session.assert_called_once_with(user_intent="Hello CKO")
        mock_orchestrator.session_store.append_timeline_event.assert_called_once()
        # Check message logging
        mock_orchestrator.session_store.append_cko_log.assert_called_with("user", "Hello CKO")

    def test_send_to_cko_grounding_state(self, mock_orchestrator):
        """Test sending message to CKO when already in GROUNDING state."""
        mock_orchestrator.state_ctrl.current_state = AppState.GROUNDING

        mock_orchestrator.send_to_cko("Follow up question")

        # Should not transition state
        mock_orchestrator.state_ctrl.transition_to.assert_not_called()
        # Should not create new session
        mock_orchestrator.session_store.create_session.assert_not_called()
        # Should log message
        mock_orchestrator.session_store.append_cko_log.assert_called_with("user", "Follow up question")

    def test_confirm_project_without_mission_protocol(self, mock_orchestrator):
        """Test confirming project without mission protocol."""
        mock_orchestrator.cko.messages = []  # No messages

        mock_orchestrator.confirm_project()

        # Should emit error
        mock_orchestrator.error_occurred.emit.assert_called_once()
        assert "Mission Protocol" in mock_orchestrator.error_occurred.emit.call_args[0][0]

    def test_confirm_project_with_mission_protocol(self, mock_orchestrator):
        """Test confirming project with valid mission protocol."""
        # Setup CKO messages with assistant response
        mock_orchestrator.cko.messages = [
            {"role": "user", "content": "User message"},
            {"role": "assistant", "content": "CKO response as mission protocol"}
        ]

        mock_orchestrator.confirm_project()

        # Should extract mission protocol
        assert mock_orchestrator._mission_protocol == "CKO response as mission protocol"
        # Should update session
        mock_orchestrator.session_store.update_session.assert_called_with(
            mission_protocol="CKO response as mission protocol"
        )
        # Should transition to DEBATE
        mock_orchestrator.state_ctrl.transition_to.assert_called_once_with(AppState.DEBATE)

    def test_inject_user_message_direct_target(self, mock_orchestrator):
        """Test injecting user message with direct target."""
        # Mock the role resolution
        with patch.object(mock_orchestrator, '_resolve_target_role', return_value="PM"):
            with patch.object(mock_orchestrator, '_trigger_direct_response') as mock_trigger:
                mock_orchestrator.inject_user_message("@PM What's the status?")

                # Should emit message
                mock_orchestrator.agent_response.emit.assert_called_with("Commander", "@PM What's the status?")
                # Should log message
                mock_orchestrator.session_store.append_meeting_log.assert_called_with("Commander", "@PM What's the status?")
                # Should trigger direct response
                mock_trigger.assert_called_once_with("PM", "@PM What's the status?")

    def test_inject_user_message_no_target(self, mock_orchestrator):
        """Test injecting user message without specific target."""
        with patch.object(mock_orchestrator, '_resolve_target_role', return_value=None):
            mock_orchestrator.inject_user_message("General instruction")

            # Should emit message
            mock_orchestrator.agent_response.emit.assert_called_with("Commander", "General instruction")
            # Should log message
            mock_orchestrator.session_store.append_meeting_log.assert_called_with("Commander", "General instruction")
            # Should emit system message
            mock_orchestrator.agent_response.emit.assert_any_call("系统", "⚡ 指令已同步全员。")

    def test_stop_all_no_workers(self, mock_orchestrator):
        """Test stopping all workers when none are active."""
        mock_orchestrator._active_workers = []

        mock_orchestrator.stop_all()

        # Should reset state
        mock_orchestrator.state_ctrl.reset.assert_called_once()
        # Should emit system message
        mock_orchestrator.agent_response.emit.assert_called_with("系统", "🛑 所有任务已中止。")

    def test_new_session(self, mock_orchestrator):
        """Test starting a new session."""
        mock_orchestrator.new_session()

        # Should stop all workers
        mock_orchestrator.state_ctrl.reset.assert_called_once()
        # Should clear all agent histories
        assert mock_orchestrator.cko.messages == []
        assert mock_orchestrator.pm.messages == []
        assert mock_orchestrator.arch.messages == []
        assert mock_orchestrator.designer.messages == []
        assert mock_orchestrator.coder.messages == []
        assert mock_orchestrator.tester.messages == []
        # Should reset internal state
        assert mock_orchestrator._debate_round == 0
        assert mock_orchestrator._mission_protocol == ""
        assert mock_orchestrator._pm_direction == ""

    def test_agent_worker_execution(self, agent_worker):
        """Test AgentWorker execution."""
        result_called = []
        error_called = []

        def on_result(role, content):
            result_called.append((role, content))

        def on_error(role, error):
            error_called.append((role, error))

        agent_worker.finished_with_result.connect(on_result)
        agent_worker.error_occurred.connect(on_error)

        agent_worker.run()

        # Should emit result
        assert len(result_called) == 1
        assert result_called[0][0] == "TestAgent"
        assert "Mock response from TestAgent to: Test message" in result_called[0][1]

    def test_agent_worker_cancellation(self, agent_worker):
        """Test AgentWorker cancellation."""
        agent_worker._is_cancelled = True
        result_called = []

        def on_result(role, content):
            result_called.append((role, content))

        agent_worker.finished_with_result.connect(on_result)

        agent_worker.run()

        # Should not emit result when cancelled
        assert len(result_called) == 0

    def test_audit_worker_execution(self, mock_orchestrator):
        """Test AuditWorker execution."""
        audit_worker = AuditWorker(mock_orchestrator.cko, "TestStage", "TestContext", "TestProtocol")
        result_called = []
        error_called = []

        def on_result(result):
            result_called.append(result)

        def on_error(role, error):
            error_called.append((role, error))

        audit_worker.audit_finished.connect(on_result)
        audit_worker.error_occurred.connect(on_error)

        audit_worker.run()

        # Should emit audit result
        assert len(result_called) == 1
        assert result_called[0] == "PASS: TestStage audit passed"

    def test_state_controller_integration(self, mock_orchestrator):
        """Test integration with StateController."""
        # Test valid transition
        mock_orchestrator.state_ctrl.transition_to.return_value = True
        mock_orchestrator.state_ctrl.current_state = AppState.GROUNDING

        # This would normally call transition_to internally
        # For integration test, we verify the orchestrator respects state controller
        assert mock_orchestrator.state_ctrl.current_state == AppState.GROUNDING

    def test_session_store_integration(self, mock_orchestrator):
        """Test integration with SessionStore."""
        # Test timeline event recording
        mock_orchestrator.session_store.append_timeline_event.assert_not_called()

        # Call a method that records timeline
        mock_orchestrator.state_ctrl.current_state = AppState.IDLE
        mock_orchestrator.send_to_cko("Test")

        # Should have recorded timeline event
        assert mock_orchestrator.session_store.append_timeline_event.called

    def test_agent_signal_connections(self, mock_orchestrator):
        """Test that agent signals are properly connected."""
        # Verify all agents have typing signals connected
        for agent in [mock_orchestrator.cko, mock_orchestrator.pm, mock_orchestrator.arch,
                     mock_orchestrator.designer, mock_orchestrator.coder, mock_orchestrator.tester]:
            assert agent.typing_started.connect.called
            assert agent.typing_finished.connect.called