
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agents.crew_agents import create_agents
from tools.validation_tool import ValidationTool, PytestRunnerTool, TypeCheckTool

class TestTesterTools(unittest.TestCase):
    def setUp(self):
        # Create agents
        self.agents = create_agents()
        self.tester = self.agents["Tester"]

    def test_tester_has_new_tools(self):
        """Verify Tester agent has Pytest and Mypy tools."""
        print("\n[TEST] Verifying Tester Tools...")
        
        tool_names = [t.name for t in self.tester.tools]
        print(f"  Tester Tools: {tool_names}")
        
        self.assertIn("python_code_validator", tool_names)
        self.assertIn("pytest_runner", tool_names)
        self.assertIn("mypy_checker", tool_names)
        
        print("[OK] Tester has all required tools.")

    def test_tool_instantiation(self):
        """Verify tools can be instantiated and have correct schema."""
        print("\n[TEST] Verifying Tool Instantiation...")
        
        pytest_tool = PytestRunnerTool()
        mypy_tool = TypeCheckTool()
        
        self.assertEqual(pytest_tool.name, "pytest_runner")
        self.assertEqual(mypy_tool.name, "mypy_checker")
        
        print(f"  Pytest Tool Args: {pytest_tool.args_schema.schema()}")
        print(f"  Mypy Tool Args: {mypy_tool.args_schema.schema()}")
        
        print("[OK] Tools instantiated correctly.")

if __name__ == "__main__":
    unittest.main()
