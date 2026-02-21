"""
tool_schema_adapter.py - 工具链适配器
====================================
将现有的 Python 工具函数自动转换为 OpenAI/GLM 兼容的 JSON Schema 格式。
"""

import inspect
import json
from typing import Callable, Dict, Any, Optional


def tool_to_schema(tool_callable: Callable, name: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
    """
    将 Python 工具函数转换为 OpenAI/GLM 兼容的 JSON Schema。

    Args:
        tool_callable: 可调用的 Python 函数
        name: 工具名称（默认为函数名）
        description: 工具描述（默认为函数的 __doc__ 或占位符）

    Returns:
        JSON Schema 格式的工具定义，包含 name, description, parameters 等字段。
    """
    func_name = name or tool_callable.__name__
    func_desc = description or (tool_callable.__doc__ or "No description provided.")

    # 解析函数签名
    sig = inspect.signature(tool_callable)
    parameters = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param_name == 'self':
            continue

        # 参数类型映射
        param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
        param_default = param.default if param.default != inspect.Parameter.empty else None

        # 类型映射到 JSON Schema 类型
        type_mapping = {
            str: {"type": "string"},
            int: {"type": "integer"},
            float: {"type": "number"},
            bool: {"type": "boolean"},
            list: {"type": "array", "items": {"type": "string"}},
            dict: {"type": "object", "additionalProperties": True},
        }

        param_schema = type_mapping.get(param_type, {"type": "string"})

        # 添加默认值（如果有）
        if param_default is not None:
            param_schema["default"] = param_default
        else:
            required.append(param_name)

        # 添加描述（可从文档字符串解析，但简化处理）
        param_schema["description"] = f"参数 {param_name}"

        parameters[param_name] = param_schema

    # 构建完整的工具 schema
    tool_schema = {
        "type": "function",
        "function": {
            "name": func_name,
            "description": func_desc,
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required if required else None,
                "additionalProperties": False,
            }
        }
    }

    return tool_schema


def crew_tool_to_schema(crew_tool) -> Dict[str, Any]:
    """
    将 CrewAI BaseTool 实例转换为 JSON Schema。

    Args:
        crew_tool: CrewAI BaseTool 实例

    Returns:
        JSON Schema 格式的工具定义
    """
    # 提取 CrewAI 工具的信息
    name = getattr(crew_tool, 'name', crew_tool.__class__.__name__)
    description = getattr(crew_tool, 'description', 'No description')

    # 获取参数 schema（如果可用）
    args_schema = getattr(crew_tool, 'args_schema', None)
    if args_schema:
        # 假设 args_schema 是 Pydantic BaseModel
        try:
            schema_dict = args_schema.schema()
            parameters = schema_dict.get('properties', {})
            required = schema_dict.get('required', [])

            tool_schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": parameters,
                        "required": required if required else None,
                        "additionalProperties": False,
                    }
                }
            }
            return tool_schema
        except:
            pass

    # 回退到通用包装器
    def wrapped_tool(**kwargs):
        # 调用 CrewAI 工具的 _run 方法
        return crew_tool._run(**kwargs)

    return tool_to_schema(wrapped_tool, name, description)


# 示例用法
if __name__ == "__main__":
    # 示例工具函数
    def read_file(path: str, encoding: str = "utf-8") -> str:
        """读取文件内容

        Args:
            path: 文件路径
            encoding: 文件编码
        """
        with open(path, 'r', encoding=encoding) as f:
            return f.read()

    schema = tool_to_schema(read_file)
    print(json.dumps(schema, indent=2, ensure_ascii=False))