"""
Pytest configuration and shared fixtures for AI-Lab-Commander tests.
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Disable telemetry for tests
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

# Disable actual API calls in tests
os.environ["TEST_MODE"] = "true"