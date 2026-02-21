
import os
import sys

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Mock PyQt6 objects if needed, but here we just want to see if the imports and object creation hang
print("=== [START] CrewManager Initialization Test (No GUI) ===")

print("Step 1: Importing CrewManager...")
try:
    from core.crew_manager import CrewManager
    print("CrewManager imported.")
except Exception as e:
    import traceback
    print(f"FAILED: Import error: {e}\n{traceback.format_exc()}")
    sys.exit(1)

print("Step 2: Instantiating CrewManager...")
try:
    # This will trigger the __init__ and all agent/task creations
    manager = CrewManager()
    print("CrewManager instantiated successfully.")
except Exception as e:
    import traceback
    print(f"FAILED: Instantiation error: {e}\n{traceback.format_exc()}")
    sys.exit(1)

print("Step 3: Testing start_mission call...")
try:
    manager.start_mission("你好")
    print("start_mission called (Thread should be running).")
except Exception as e:
    print(f"FAILED: start_mission error: {e}")

print("=== [END] CrewManager Initialization Test ===")
