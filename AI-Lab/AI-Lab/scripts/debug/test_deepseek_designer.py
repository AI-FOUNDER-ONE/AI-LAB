import os
from openai import OpenAI
from config import API_KEYS

deepseek_key = API_KEYS.get("deepseek")
if not deepseek_key:
    print("No deepseek key found!")
    exit(1)

client = OpenAI(
    api_key=deepseek_key,
    base_url="https://api.deepseek.com"
)

messages = [
    {"role": "system", "content": "You are a designer."},
    {"role": "user", "content": "Design a 2.5D snake game."}
]

tools = [
    {
        "type": "function",
        "function": {
            "name": "design_generator",
            "description": "Generate design image",
            "parameters": {
                "type": "object",
                "properties": {
                    "design_json": {"type": "string"},
                    "filename": {"type": "string"}
                },
                "required": ["design_json"]
            }
        }
    }
]

try:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.7,
        max_tokens=8000,
        tools=tools,
        tool_choice="auto"
    )
    print("Success:", response.choices[0].message)
except Exception as e:
    import traceback
    traceback.print_exc()
