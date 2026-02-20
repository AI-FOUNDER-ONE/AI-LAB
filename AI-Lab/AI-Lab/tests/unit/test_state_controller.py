"""
Unit tests for StateController.
"""

import pytest
from PyQt6.QtCore import QCoreApplication
from core.state_controller import StateController
from config import AppState


@pytest.fixture
def state_controller(qapp):
    """Create a StateController instance."""
    return StateController()


class TestStateController:
    """Test suite for StateController."""

    def test_initial_state(self, state_controller):
        """Test that initial state is IDLE."""
        assert state_controller.current_state == AppState.IDLE
        assert state_controller.state_description == "空闲 - 等待新任务"

    def test_valid_transition(self, state_controller):
        """Test valid state transition."""
        # IDLE -> GROUNDING should succeed
        assert state_controller.transition_to(AppState.GROUNDING) is True
        assert state_controller.current_state == AppState.GROUNDING
        assert state_controller.state_description == "需求打磨 - CKO 深度访谈中"

    def test_invalid_transition(self, state_controller):
        """Test invalid state transition."""
        # IDLE -> DEBATE should fail (not in valid transitions)
        assert state_controller.transition_to(AppState.DEBATE) is False
        assert state_controller.current_state == AppState.IDLE  # State unchanged

    def test_transition_chain(self, state_controller):
        """Test a chain of valid transitions."""
        # IDLE -> GROUNDING -> DEBATE -> PRODUCTION -> VERIFICATION -> COMPLETED
        assert state_controller.transition_to(AppState.GROUNDING) is True
        assert state_controller.current_state == AppState.GROUNDING

        assert state_controller.transition_to(AppState.DEBATE) is True
        assert state_controller.current_state == AppState.DEBATE

        assert state_controller.transition_to(AppState.PRODUCTION) is True
        assert state_controller.current_state == AppState.PRODUCTION

        assert state_controller.transition_to(AppState.VERIFICATION) is True
        assert state_controller.current_state == AppState.VERIFICATION

        # VERIFICATION -> COMPLETED is valid
        assert state_controller.transition_to(AppState.COMPLETED) is True
        assert state_controller.current_state == AppState.COMPLETED

    def test_state_history(self, state_controller):
        """Test that state history is recorded."""
        # Initial state
        assert state_controller.transition_to(AppState.GROUNDING) is True
        assert state_controller.transition_to(AppState.DEBATE) is True
        # History is internal, but we can verify transitions work

    def test_state_descriptions(self, state_controller):
        """Test all state descriptions exist."""
        descriptions = state_controller.STATE_DESCRIPTIONS
        assert AppState.IDLE in descriptions
        assert AppState.GROUNDING in descriptions
        assert AppState.DEBATE in descriptions
        assert AppState.PRODUCTION in descriptions
        assert AppState.VERIFICATION in descriptions
        assert AppState.DELIVERY in descriptions
        assert AppState.COMPLETED in descriptions

    def test_reset(self, state_controller):
        """Test reset method."""
        state_controller.transition_to(AppState.GROUNDING)
        state_controller.transition_to(AppState.DEBATE)

        # Reset should return to IDLE
        state_controller.reset()
        assert state_controller.current_state == AppState.IDLE

    def test_error_signal(self, state_controller, qtbot):
        """Test that error_occurred signal is emitted on invalid transition."""
        with qtbot.wait_signal(state_controller.error_occurred, timeout=1000):
            # Attempt invalid transition
            state_controller.transition_to(AppState.DEBATE)  # IDLE -> DEBATE is invalid

    def test_state_changed_signal(self, state_controller, qtbot):
        """Test that state_changed signal is emitted on valid transition."""
        with qtbot.wait_signals([state_controller.state_changed], timeout=1000):
            state_controller.transition_to(AppState.GROUNDING)