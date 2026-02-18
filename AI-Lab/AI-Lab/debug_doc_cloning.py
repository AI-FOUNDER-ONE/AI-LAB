"""
debug_doc_cloning.py - 测试文档克隆逻辑
====================================

该脚本用于手动验证 core/doc_logic_engine.py 的功能。
"""

import os
import json
import logging
from dotenv import load_dotenv
from core.doc_logic_engine import DocumentLogicEngine
from config import API_KEYS

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    
    # 尝试初始化客户端 (优先使用 Qwen 或 OpenAI)
    client = None
    model = None
    
    # 尝试 Qwen
    qwen_key = API_KEYS.get("qwen")
    if qwen_key:
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=qwen_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            model = "qwen-max"
            logger.info("使用 Qwen (通义千问) 模型")
        except ImportError:
            logger.error("请安装 openai: pip install openai")
            return
    
    if not client:
        # 尝试 OpenAI
        openai_key = API_KEYS.get("openai")
        if openai_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=openai_key)
                model = "gpt-4o"
                logger.info("使用 OpenAI (GPT-4o) 模型")
            except Exception:
                pass
                
    if not client:
        # 尝试 HiAPI (Gemini)
        hiapi_key = API_KEYS.get("hiapi")
        if hiapi_key:
            try:
                from openai import OpenAI
                client = OpenAI(
                    api_key=hiapi_key,
                    base_url="https://api.hiapi.cn/v1" # 假设 HiAPI 兼容 OpenAI 格式
                )
                model = "gemini-1.5-pro-latest" # 使用个通用 gemini 模型名
                logger.info("使用 HiAPI (Gemini) 模型")
            except Exception:
                pass

    if not client:
        logger.error("未找到可用的 API Key (Qwen, OpenAI, HiAPI)")
        return

    engine = DocumentLogicEngine(client, model)

    # --- 测试数据 ---
    prototype_text = """
    项目可行性报告
    1. 背景与意义
    本项目旨在解决当前手工文档处理效率低下的问题...
    2. 技术方案
    采用 Python + LLM 技术栈...
    3. 效益分析
    预计提升效率 50%...
    """

    new_content_raw = """
    我们要搞个自动写文档的工具。
    现在大家写文档太慢了，而且格式乱七八糟。
    如果用 AI 来弄，应该能快很多，至少节省一半时间吧。
    技术上嘛，就用那个 Azure OpenAI 或者是 Gemini 都可以。
    主要是要能把旧文档的格式给学过来。
    """

    logger.info("--- 开始测试: 原型分析 ---")
    try:
        structure = engine.analyze_prototype(prototype_text)
        logger.info(f"原型结构:\n{json.dumps(structure, ensure_ascii=False, indent=2)}")
    except Exception as e:
        logger.error(f"原型分析失败: {e}")
        return

    logger.info("--- 开始测试: 内容重组 ---")
    try:
        result = engine.process_content_to_template(new_content_raw, structure)
        logger.info(f"重组结果:\n{json.dumps(result, ensure_ascii=False, indent=2)}")
    except Exception as e:
        logger.error(f"内容重组失败: {e}")

if __name__ == "__main__":
    main()
