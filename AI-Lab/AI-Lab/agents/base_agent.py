"""
base_agent.py - AI Agent 抽象基类
===================================
统一接口定义：send_message() / get_response()
内置消息历史管理和系统提示词配置。
所有具体角色 Agent 均继承此基类。
"""

import traceback
from abc import ABC, abstractmethod
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal


class BaseAgent(QObject):
    """AI Agent 抽象基类

    定义所有 AI 角色的统一接口和通用行为。

    信号:
        response_ready: AI 回复完成信号 (role, content)
        stream_chunk: 流式输出信号 (role, chunk)
        error_occurred: 错误信号 (role, error_message)
        typing_started: 开始输入信号 (role)
        typing_finished: 结束输入信号 (role)
    """

    response_ready = pyqtSignal(str, str)    # (角色, 回复内容)
    stream_chunk = pyqtSignal(str, str)      # (角色, 文本片段)
    error_occurred = pyqtSignal(str, str)    # (角色, 错误消息)
    typing_started = pyqtSignal(str)         # (角色)
    typing_finished = pyqtSignal(str)        # (角色)

    def __init__(self, role: str, model_config: dict, system_prompt: str = "", parent=None):
        """初始化 Agent

        Args:
            role: 角色标识 (CKO/PM/Arch/Designer/Coder/Tester)
            model_config: 模型配置 {"provider": "...", "model": "..."}
            system_prompt: 系统提示词
            parent: Qt 父对象
        """
        super().__init__(parent)
        self.role = role
        self.model_config = model_config
        self.system_prompt = system_prompt
        self._messages = []
        self._is_active = False
        self.max_history_length = 50  # 限制消息历史长度，防止内存增长
        self.tools = []  # 注册的工具列表，用于原生 Function Calling
        self._tools_schema_cache = None  # 工具JSON Schema缓存

        # 初始化消息历史
        if system_prompt:
            self._messages.append({
                "role": "system",
                "content": system_prompt,
            })

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度（基于Jaccard相似度）

        Args:
            text1: 第一个文本
            text2: 第二个文本

        Returns:
            相似度分数 0.0-1.0
        """
        # 简单实现：基于词集的Jaccard相似度
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)

    def _is_duplicate_request(self, content: str, threshold: float = 0.7) -> bool:
        """检查当前请求是否与最近的历史消息重复

        Args:
            content: 当前请求内容
            threshold: 相似度阈值，超过则认为重复

        Returns:
            是否为重复请求
        """
        if not self._messages:
            return False

        # 检查最近的用户消息（最多查看最近3条）
        recent_user_messages = []
        for msg in reversed(self._messages):
            if msg["role"] == "user":
                recent_user_messages.append(msg["content"])
                if len(recent_user_messages) >= 3:
                    break

        if not recent_user_messages:
            return False

        # 计算与最近用户消息的最大相似度
        max_similarity = 0.0
        for recent_content in recent_user_messages:
            similarity = self._calculate_text_similarity(content, recent_content)
            max_similarity = max(max_similarity, similarity)

        return max_similarity >= threshold

    def _handle_duplicate_request(self, content: str) -> str:
        """处理重复请求（子类可重写此方法）

        Args:
            content: 重复的请求内容

        Returns:
            处理重复请求的响应
        """
        # 默认行为：返回提示信息
        return f"【检测到相似请求】此请求与最近的历史消息相似，请基于之前的讨论继续。"

    def register_tool(self, tool_callable, name=None, description=None, parameters_schema=None):
        """注册一个工具，用于原生 Function Calling

        Args:
            tool_callable: 可调用的 Python 函数
            name: 工具名称（默认为函数名）
            description: 工具描述
            parameters_schema: JSON Schema 格式的参数定义
        """
        import inspect
        import json

        tool_name = name or tool_callable.__name__
        tool_desc = description or (tool_callable.__doc__ or "No description")

        # 自动从函数签名提取参数 schema（简化版）
        if parameters_schema is None:
            sig = inspect.signature(tool_callable)
            params = {}
            required = []
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                param_type = param.annotation if param.annotation != inspect.Parameter.empty else str
                param_default = param.default if param.default != inspect.Parameter.empty else None

                # 简化类型映射
                type_map = {
                    str: "string",
                    int: "integer",
                    float: "number",
                    bool: "boolean",
                    list: "array",
                    dict: "object"
                }
                param_type_str = type_map.get(param_type, "string")

                param_schema = {"type": param_type_str}
                if param_default is not None:
                    param_schema["default"] = param_default
                else:
                    required.append(param_name)

                params[param_name] = param_schema

            parameters_schema = {
                "type": "object",
                "properties": params,
                "required": required if required else None
            }

        tool_def = {
            "name": tool_name,
            "description": tool_desc,
            "callable": tool_callable,
            "parameters": parameters_schema
        }
        self.tools.append(tool_def)
        # 清除工具schema缓存，因为工具列表已更改
        self._tools_schema_cache = None
        return tool_name

    def update_system_prompt(self, new_prompt: str):
        """Dynamic System Prompt Injection"""
        if self._messages and self._messages[0]["role"] == "system":
            self._messages[0]["content"] = new_prompt
        else:
            self._messages.insert(0, {"role": "system", "content": new_prompt})

    def _trim_message_history(self):
        """修剪消息历史，保留系统提示和最近的对话"""
        if len(self._messages) <= self.max_history_length:
            return

        # 始终保留系统提示（如果有）
        system_messages = [msg for msg in self._messages if msg["role"] == "system"]
        other_messages = [msg for msg in self._messages if msg["role"] != "system"]

        # 保留最新的消息
        keep_count = self.max_history_length - len(system_messages)
        if keep_count > 0 and len(other_messages) > keep_count:
            other_messages = other_messages[-keep_count:]

        self._messages = system_messages + other_messages

    def set_domain_persona(self, task_type: str):
        """Dynamic Persona Injection based on Task Type"""
        persona_map = {
            "SOFTWARE": {
                "Arch": "System Architect", "Designer": "UI/UX Designer", "Coder": "Full-Stack Developer", "Tester": "QA Engineer"
            },
            "ENGINEERING": {
                "Arch": "Chief Engineer", "Designer": "CAD Specialist", "Coder": "Calculation Engineer", "Tester": "Safety Inspector"
            },
            "DESIGN": {
                "Arch": "Feasibility Analyst", "Designer": "Industrial Designer", "Coder": "Prototype Engineer", "Tester": "User Researcher"
            },
            "RESEARCH": {
                "Arch": "Methodology Expert", "Designer": "Data Visualizer", "Coder": "Data Analyst", "Tester": "Peer Reviewer"
            }
        }
        
        domain_role = persona_map.get(task_type, {}).get(self.role, self.role)
        
        injection = (
            f"\n\n[SYSTEM UPDATE]\n"
            f"Current Project Mode: {task_type}\n"
            f"Your Role Adaptation: {domain_role}\n"
            f"Please adjust your expertise and output format accordingly."
        )
        self.update_system_prompt(injection)

    @property
    def is_active(self) -> bool:
        """Agent 是否正在处理请求"""
        return self._is_active

    def _get_tools_schema(self):
        """获取工具的JSON Schema（带缓存）"""
        if self._tools_schema_cache is not None:
            return self._tools_schema_cache

        tools_schema = []
        for tool_def in self.tools:
            tools_schema.append({
                "type": "function",
                "function": {
                    "name": tool_def["name"],
                    "description": tool_def["description"],
                    "parameters": tool_def["parameters"]
                }
            })

        self._tools_schema_cache = tools_schema
        return tools_schema

    def _execute_tool_with_timeout(self, tool_def, args, timeout_seconds=30):
        """带超时控制的工具执行（使用 ThreadPoolExecutor 避免孤儿线程）

        Args:
            tool_def: 工具定义字典
            args: 工具参数字典
            timeout_seconds: 超时时间（秒）

        Returns:
            工具执行结果字符串

        Raises:
            TimeoutError: 如果工具执行超时
            Exception: 工具执行过程中的其他异常
        """
        import concurrent.futures
        import queue
        import threading

        # 创建一个单独的线程池执行器，避免使用全局线程池
        # 使用 daemon=True 确保线程不会阻止程序退出
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix=f"ToolExecutor-{tool_def.get('name', 'unknown')}"
        )
        future = executor.submit(tool_def['callable'], **args)

        try:
            # 等待结果，超时后抛出 TimeoutError
            result = future.result(timeout=timeout_seconds)
            return result
        except concurrent.futures.TimeoutError:
            # 取消 future（如果还在运行）
            future.cancel()
            # 尝试等待一小段时间让任务响应取消
            try:
                # 等待最多 0.5 秒，如果任务还没结束，我们继续执行
                concurrent.futures.wait([future], timeout=0.5)
            except:
                pass
            raise TimeoutError(f"Tool execution timed out after {timeout_seconds} seconds")
        except Exception as e:
            # 其他异常直接抛出
            raise e
        finally:
            # 无论成功与否，都关闭执行器
            # wait=False 表示不等待线程完成，因为我们希望超时后线程可以继续运行但最终会被回收
            # 由于线程是 daemon=True（默认），主线程退出时它们会被强制结束
            executor.shutdown(wait=False)

    def _call_api_with_tools(self, messages: list) -> dict:
        """带有工具调用循环的 API 调用（默认实现，子类可覆盖）

        Args:
            messages: 完整的消息历史列表

        Returns:
            字典，包含 'content' 和 'tool_calls' 字段。如果没有工具调用，
            则返回的字典中 'tool_calls' 为空列表。如果有工具调用，执行工具后
            立即返回，tool_calls 包含工具调用信息（原始调用，不含结果）。
        """
        # 获取工具的JSON Schema（使用缓存）
        tools_schema = self._get_tools_schema()

        # 最大递归深度防止无限循环
        max_iterations = 10
        for iteration in range(max_iterations):
            # 调用子类的 _call_api，传递工具 schema（如果支持）
            import tenacity
            
            def log_retry(retry_state):
                print(f"[{self.role}] API Error/RateLimit. Retrying in {retry_state.next_action.sleep}s (Attempt {retry_state.attempt_number})...")
                
            @tenacity.retry(
                wait=tenacity.wait_exponential(multiplier=1.5, min=2, max=12),
                stop=tenacity.stop_after_attempt(5),
                retry=tenacity.retry_if_exception_type(Exception),
                before_sleep=log_retry
            )
            def _execute_api():
                try:
                    # 尝试调用支持工具的 _call_api（如果子类实现）
                    return self._call_api(messages, tools=tools_schema if tools_schema else None)
                except TypeError:
                    # 子类 _call_api 不支持 tools 参数，回退到无工具调用
                    return self._call_api(messages)
            
            response = _execute_api()

            # 假设 response 是一个字典，包含 'content' 和 'tool_calls' 字段
            # 或者是一个字符串（无工具调用）
            if isinstance(response, dict):
                content = response.get('content', '')
                tool_calls = response.get('tool_calls', [])
                if tool_calls:
                    # 执行工具调用并将结果追加到消息历史
                    executed_tool_calls = []
                    for tool_call in tool_calls:
                        # 支持两种工具调用格式：直接字段或嵌套 function 字段
                        if 'function' in tool_call:
                            # OpenAI 格式：tool_call['function']['name']、['arguments']
                            func_name = tool_call['function'].get('name')
                            args_str = tool_call['function'].get('arguments', '{}')
                        else:
                            # 扁平格式：tool_call['name']、['arguments']
                            func_name = tool_call.get('name')
                            args_str = tool_call.get('arguments', '{}')

                        # 解析 JSON 参数字符串
                        try:
                            import json
                            args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        except:
                            args = {}
                        # 查找对应的工具定义
                        tool_def = next((t for t in self.tools if t['name'] == func_name), None)
                        if tool_def:
                            try:
                                # 执行工具（带超时控制）
                                result = self._execute_tool_with_timeout(tool_def, args, timeout_seconds=30)
                                # 将工具结果添加到消息历史
                                messages.append({
                                    "role": "tool",
                                    "content": str(result),
                                    "tool_call_id": tool_call.get('id', ''),
                                    "name": func_name
                                })
                                # 记录执行成功的工具调用信息
                                executed_tool_calls.append({
                                    "name": func_name,
                                    "args": args,
                                    "result": str(result)
                                })
                            except Exception as e:
                                error_msg = f"Error: {str(e)}"
                                messages.append({
                                    "role": "tool",
                                    "content": error_msg,
                                    "tool_call_id": tool_call.get('id', ''),
                                    "name": func_name
                                })
                                executed_tool_calls.append({
                                    "name": func_name,
                                    "args": args,
                                    "result": error_msg
                                })
                        else:
                            error_msg = f"Tool '{func_name}' not found"
                            messages.append({
                                "role": "tool",
                                "content": error_msg,
                                "tool_call_id": tool_call.get('id', ''),
                                "name": func_name
                            })
                            executed_tool_calls.append({
                                "name": func_name,
                                "args": args,
                                "result": error_msg
                            })
                    # 执行完所有工具调用后，立即返回，不再继续循环
                    # 返回原始工具调用列表，调用方可以根据需要处理
                    return {"content": content, "tool_calls": executed_tool_calls}
                else:
                    # 没有工具调用，返回字典
                    return {"content": content, "tool_calls": []}
            else:
                # 返回字符串，无工具调用
                return {"content": response, "tool_calls": []}

        # 达到最大迭代次数
        return {"content": "Tool call loop exceeded maximum iterations.", "tool_calls": []}

    def send_message(self, content: str) -> str:
        """发送消息并获取回复（同步方法，由 QThread 调用）

        Args:
            content: 用户或系统发送的消息内容

        Returns:
            AI 的回复文本。如果存在工具调用，返回以 '__TOOL_RESULT__:' 开头的 JSON 字符串，
            包含工具调用结果。
        """
        self._is_active = True
        self.typing_started.emit(self.role)

        # 检查是否为重复请求（仅对PM角色启用）
        if self.role == "PM" and self._is_duplicate_request(content):
            duplicate_response = self._handle_duplicate_request(content)
            # 仍然需要添加到历史记录
            self._messages.append({
                "role": "user",
                "content": content,
            })
            self._messages.append({
                "role": "assistant",
                "content": duplicate_response,
            })
            self._emit_stream_chunks(duplicate_response)
            self.response_ready.emit(self.role, duplicate_response)
            self._is_active = False
            self.typing_finished.emit(self.role)
            return duplicate_response

        # 添加用户消息到历史
        self._messages.append({
            "role": "user",
            "content": content,
        })

        try:
            # 调用带有工具调用支持的 API 方法，返回字典
            response_dict = self._call_api_with_tools(self._messages)
            content_text = response_dict.get('content', '')
            tool_calls = response_dict.get('tool_calls', [])

            # 检查是否有工具调用被执行（tool_calls 列表非空）
            if tool_calls:
                # 有工具调用，构造一个特殊格式的字符串，包含工具调用信息
                # 我们将工具调用结果编码为 JSON 字符串，以便调用方解析
                import json
                tool_result = {
                    "content": content_text,
                    "tool_calls": tool_calls
                }
                result_str = "__TOOL_RESULT__:" + json.dumps(tool_result, ensure_ascii=False)
                # 注意：我们不在消息历史中添加这个特殊字符串，而是添加原始内容
                if content_text:
                    self._messages.append({
                        "role": "assistant",
                        "content": content_text,
                    })
                else:
                    # 如果没有内容，可能只有工具调用，我们添加一个占位符
                    self._messages.append({
                        "role": "assistant",
                        "content": "[工具调用执行完毕]",
                    })
            else:
                # 没有工具调用，正常处理
                result_str = content_text
                self._messages.append({
                    "role": "assistant",
                    "content": content_text,
                })

            # 如果是工具调用结果，不进行流式传输
            if not result_str.startswith("__TOOL_RESULT__:"):
                self._emit_stream_chunks(result_str)
            self.response_ready.emit(self.role, result_str)
            return result_str

        except Exception as e:
            error_msg = f"[{self.role}] API 调用失败: {str(e)}\n{traceback.format_exc()}"
            self.error_occurred.emit(self.role, error_msg)
            return f"⚠️ 错误: {str(e)}"

        finally:
            self._is_active = False
            self.typing_finished.emit(self.role)

    @abstractmethod
    def _call_api(self, messages: list, tools: list = None) -> str:
        """调用具体的 AI API（子类实现）

        Args:
            messages: 完整的消息历史列表
            tools: 可选的工具定义列表，用于原生 Function Calling

        Returns:
            API 返回的文本回复（或包含 content 和 tool_calls 的字典）
        """
        raise NotImplementedError

    def add_context(self, content: str, role: str = "system"):
        """手动向消息历史中注入上下文

        Args:
            content: 上下文内容
            role: 消息角色 (system/user/assistant)
        """
        self._messages.append({
            "role": role,
            "content": content,
        })

    def get_messages(self) -> list:
        """获取完整消息历史"""
        return self._messages.copy()

    def clear_history(self):
        """清除消息历史（保留系统提示词）"""
        system_msgs = [m for m in self._messages if m["role"] == "system"]
        self._messages = system_msgs

    def stop(self):
        """中止当前任务"""
        self._is_active = False

    def _emit_stream_chunks(self, content: str, chunk_size: int = 50):
        """将内容分割成块并发射流式信号

        Args:
            content: 要流式传输的内容
            chunk_size: 每个块的大致字符数（按单词边界分割）
        """
        if not content:
            return

        # 按单词分割，保持单词完整性
        words = content.split(' ')
        chunk = []
        current_length = 0

        for word in words:
            chunk.append(word)
            current_length += len(word) + 1  # +1 for space
            if current_length >= chunk_size:
                chunk_text = ' '.join(chunk)
                self.stream_chunk.emit(self.role, chunk_text)
                chunk = []
                current_length = 0

        # 发射剩余部分
        if chunk:
            chunk_text = ' '.join(chunk)
            self.stream_chunk.emit(self.role, chunk_text)
