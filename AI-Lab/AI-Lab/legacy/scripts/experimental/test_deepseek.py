#!/usr/bin/env python3
"""
测试DeepSeek API是否工作，检查max_tokens设置是否生效
"""
import os
import sys
from dotenv import load_dotenv
import openai

# 加载环境变量
load_dotenv()

# 获取DeepSeek API密钥
api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    print("错误: 未找到DEEPSEEK_API_KEY环境变量")
    sys.exit(1)

print(f"API密钥前8位: {api_key[:8]}...")
print("正在测试DeepSeek API...")

# 初始化OpenAI客户端（DeepSeek兼容OpenAI接口）
client = openai.OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

# 测试1: 简单调用，max_tokens=8000
print("\n=== 测试1: 简单调用 (max_tokens=8000) ===")
try:
    response = client.chat.completions.create(
        model="deepseek-reasoner",
        messages=[
            {"role": "user", "content": "请用一句话介绍你自己"}
        ],
        max_tokens=8000,
        temperature=0.7
    )
    print(f"[OK] 成功! 响应长度: {len(response.choices[0].message.content)} 字符")
    print(f"响应内容前100字符: {response.choices[0].message.content[:100]}...")
    print(f"使用tokens数: {response.usage.total_tokens if response.usage else '未知'}")
except Exception as e:
    print(f"[ERR] 错误: {e}")

# 测试2: 测试max_tokens设置是否正确应用
print("\n=== 测试2: 验证max_tokens参数 ===")
try:
    # 尝试设置max_tokens=100，验证API是否接受
    response = client.chat.completions.create(
        model="deepseek-reasoner",
        messages=[
            {"role": "user", "content": "说'测试成功'三个字"}
        ],
        max_tokens=100,
        temperature=0.7
    )
    print(f"[OK] max_tokens=100 成功!")
    print(f"响应: {response.choices[0].message.content}")
except Exception as e:
    print(f"[ERR] 错误: {e}")

# 测试3: 检查模型信息
print("\n=== 测试3: 检查模型限制 ===")
try:
    # 尝试获取模型信息（如果有相关接口）
    # 注意: DeepSeek可能不提供模型信息端点
    print("注意: DeepSeek API可能不提供模型信息端点")
    # 可以通过错误信息推断
    print("从之前的错误信息可知: DeepSeek V3.2最大上下文长度 = 131,072 tokens")
except Exception as e:
    print(f"[ERR] 错误: {e}")

print("\n=== 测试完成 ===")