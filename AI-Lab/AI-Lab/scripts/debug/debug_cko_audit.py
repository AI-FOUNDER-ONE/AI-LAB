"""
debug_cko_audit.py - Reproduce CKO Audit Failure with Gemini
============================================================
"""
import logging
import sys
from PyQt6.QtCore import QCoreApplication
from agents.cko_agent import CKOAgent

# Setup Qt App
app = QCoreApplication(sys.argv)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Initializing CKOAgent (assuming Gemini provider)...")
    cko = CKOAgent()
    
    # Force provider to hiapi if not already (for testing the specific bug)
    cko.model_config["provider"] = "hiapi"
    cko.model_config["model"] = "gemini-3-pro" 
    
    print(f"Model Config: {cko.model_config}")
    
    mission = """
    {
      "objective": "Build a website",
      "constraints": ["Python", "FastAPI"]
    }
    """
    
    context = """
    I propose using Django.
    """
    
    logger.info("Running CKO Audit...")
    try:
        result = cko.audit_node("Debate Phase", context, mission)
        print("\n--- Audit Result ---")
        print(result)
        print("--------------------")
    except Exception as e:
        logger.error(f"Audit Failed as expected: {e}")
        # We expect an AttributeError or similar here

if __name__ == "__main__":
    main()
