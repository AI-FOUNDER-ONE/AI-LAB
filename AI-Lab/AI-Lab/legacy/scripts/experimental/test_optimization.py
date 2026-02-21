
import sys
import os
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.commander_crew_v2 import CommanderCrew, WarRoomContext, DebateRouter, WarRoomMessage

class TestOptimization(unittest.TestCase):
    def setUp(self):
        # Mock QApplication for QObject/QThread
        from PyQt6.QtWidgets import QApplication
        if not QApplication.instance():
            self.app = QApplication(sys.argv)
        
        self.commander = CommanderCrew()
        # Manually instantiate worker for testing methods
        from core.commander_crew_v2 import DebateWorker
        self.worker = DebateWorker("debate", self.commander.ctx, self.commander.router, "", parent=self.commander)
        
        # Mock agents for testing
        self.worker.agents = {
            "Arch": MagicMock(role="Arch"),
            "Designer": MagicMock(role="Designer"),
            "Coder": MagicMock(role="Coder"),
            "PM": MagicMock(role="PM")
        }
        
        self.ctx = self.commander.ctx
        self.router = self.commander.router

    def test_dynamic_prompt_injection(self):
        """Test Opt 1: Dynamic Prompt Injection based on task_type"""
        print("\n[TEST] Dynamic Prompt Injection")
        
        # 1. Research Task
        self.ctx.task_type = "RESEARCH"
        prompt_arch = self.worker._build_debate_prompt("Arch", 1)
        self.assertIn("【Arch 特别指令】", prompt_arch)
        self.assertIn("首席分析师", prompt_arch)
        
        prompt_coder = self.worker._build_debate_prompt("Coder", 1)
        self.assertIn("【Coder 特别指令】", prompt_coder)
        self.assertIn("数据技术专家", prompt_coder)

        # 2. Design Task
        self.ctx.task_type = "DESIGN"
        prompt_arch_design = self.worker._build_debate_prompt("Arch", 1)
        self.assertIn("创意总监", prompt_arch_design)
        
        print("[OK] Dynamic Prompt Injection Verified")

    def test_parallel_debate_order(self):
        """Test Opt 3: DebateRouter returns nested lists"""
        print("\n[TEST] Parallel Debate Order")
        
        # Research -> [Arch, Designer]
        self.ctx.task_type = "RESEARCH"
        order = self.router.get_debate_order(1)
        print(f"  Research Order: {order}")
        self.assertTrue(any(isinstance(item, list) for item in order))
        self.assertIn(["Arch", "Designer"], order) # Checks if the list ["Arch", "Designer"] is in the list
        
        # Engineering -> [Arch, Designer]
        self.ctx.task_type = "ENGINEERING"
        order_eng = self.router.get_debate_order(1)
        print(f"  Engineering Order: {order_eng}")
         # Checks if the list ["Arch", "Designer"] is in the list. 
         # Note: list equality checks content.
        found_parallel = False
        for item in order_eng:
            if isinstance(item, list) and set(item) == {"Arch", "Designer"}:
                found_parallel = True
        self.assertTrue(found_parallel, "Should contain ['Arch', 'Designer'] (or equivalent)")
        
        print("[OK] Parallel Debate Order Verified")

    @patch("core.commander_crew_v2.DebateWorker._execute_single_agent")
    def test_parallel_execution(self, mock_execute):
        """Test Opt 3: Parallel Execution Logic"""
        print("\n[TEST] Parallel Execution Logic")
        
        # Mock execute to sleep slightly to simulate parallel work
        def side_effect(agent, prompt):
            time.sleep(0.1)
            return f"Response from {agent.role}"
        mock_execute.side_effect = side_effect
        
        roles = ["Arch", "Designer"]
        
        start_time = time.time()
        responses = self.worker._execute_parallel_agents(roles, 1, "PM", "Init")
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"  Execution took {duration:.2f}s (Expected ~0.1s if parallel, ~0.2s if serial)")
        
        # Should be faster than 0.2s if parallel
        self.assertLess(duration, 0.18) 
        self.assertEqual(responses["Arch"], "Response from Arch")
        self.assertEqual(responses["Designer"], "Response from Designer")
        
        print("[OK] Parallel Execution Verified")

    def test_convergence_detection(self):
        """Test Opt 4: Convergence Detection"""
        print("\n[TEST] Convergence Detection")
        
        # Log 3 agreements from different roles
        self.ctx.history.clear()
        self.ctx.add_message("Arch", "我完全同意这个方案")
        self.ctx.add_message("Designer", "方案可行，没有异议")
        self.ctx.add_message("Coder", "技术上可行，I agree")
        
        # Add filler to meet limit requirements
        self.ctx.add_message("PM", "Filler 1")
        self.ctx.add_message("PM", "Filler 2")
        
        is_converged = self.ctx.check_convergence(limit=5)
        print(f"  Converged: {is_converged}")
        self.assertTrue(is_converged)
        
        # Log mixed
        self.ctx.history.clear()
        self.ctx.add_message("Arch", "我同意")
        self.ctx.add_message("Designer", "我反对")
        self.ctx.add_message("Coder", "我同意")
        # Only 2 agree roles
        is_converged_mixed = self.ctx.check_convergence(limit=5)
        print(f"  Converged (Mixed): {is_converged_mixed}")
        self.assertFalse(is_converged_mixed)

        print("[OK] Convergence Detection Verified")

if __name__ == "__main__":
    unittest.main()
