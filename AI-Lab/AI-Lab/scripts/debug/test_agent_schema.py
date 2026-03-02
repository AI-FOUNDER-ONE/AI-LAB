import os
from agents.designer_agent import DesignerAgent
import json
import traceback

try:
    agent = DesignerAgent()
    schemas = agent._get_tools_schema()
    print("DesignerAgent schemas:", json.dumps(schemas, indent=2, ensure_ascii=False))

    # Test API call
    msg = [
        {"role": "system", "content": agent.system_prompt},
        {"role": "user", "content": "设计一个贪吃蛇游戏界面。"}
    ]
    
    # Bypass tenactiy to get real traceback
    from openai import OpenAI
    from config import API_KEYS
    client = OpenAI(api_key=API_KEYS.get("deepseek"), base_url="https://api.deepseek.com")
    
    print("Sending to API...")
    res = client.chat.completions.create(
        model=agent.model_config["model"],
        messages=msg,
        temperature=0.7,
        max_tokens=8000,
        tools=schemas,
        tool_choice="auto"
    )
    print("API Success!")
except Exception as e:
    traceback.print_exc()
