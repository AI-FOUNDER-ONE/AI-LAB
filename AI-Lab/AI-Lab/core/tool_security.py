"""
tool_security.py - 工具安全模块
================================

包含工具权限定义和基础安全管理器。
"""

import time
import traceback
from enum import Enum
from typing import Dict, List, Set, Any, Callable


class ToolPermission(Enum):
    """工具权限级别"""
    READ_ONLY = "read_only"      # 只读权限
    LOCAL_EXECUTION = "local_execution"  # 本地执行（受限）
    FULL_ACCESS = "full_access"  # 完全访问（危险）


class ToolSecurityManager:
    """工具安全管理器：沙箱执行和权限控制"""

    def __init__(self):
        self.registered_tools: Dict[str, Dict] = {}  # 工具名称 -> 工具定义
        self.role_permissions: Dict[str, Set[str]] = {}  # 角色 -> 允许的工具集合
        self.execution_history: List[Dict] = []  # 执行历史

    def register_tool(self, tool_name: str, tool_func: Callable,
                     allowed_roles: List[str] = None,
                     permission_level: ToolPermission = ToolPermission.LOCAL_EXECUTION,
                     description: str = "") -> bool:
        """注册工具，设置权限"""
        if tool_name in self.registered_tools:
            return False

        self.registered_tools[tool_name] = {
            "function": tool_func,
            "permission_level": permission_level,
            "description": description,
            "allowed_roles": allowed_roles or []  # 空列表表示所有角色可用
        }

        # 更新角色权限
        if allowed_roles:
            for role in allowed_roles:
                if role not in self.role_permissions:
                    self.role_permissions[role] = set()
                self.role_permissions[role].add(tool_name)

        return True

    def can_execute(self, role: str, tool_name: str) -> bool:
        """检查角色是否有权限执行工具"""
        if tool_name not in self.registered_tools:
            return False

        tool_info = self.registered_tools[tool_name]
        allowed_roles = tool_info["allowed_roles"]

        # 如果允许的角色列表为空，表示所有角色可用
        if not allowed_roles:
            return True

        return role in allowed_roles

    def execute_tool_safely(self, role: str, tool_name: str, args: Dict) -> Dict[str, Any]:
        """安全执行工具（带沙箱）"""
        if not self.can_execute(role, tool_name):
            return {"success": False, "error": f"角色 '{role}' 无权执行工具 '{tool_name}'"}

        if tool_name not in self.registered_tools:
            return {"success": False, "error": f"工具 '{tool_name}' 未注册"}

        tool_info = self.registered_tools[tool_name]
        tool_func = tool_info["function"]
        permission_level = tool_info["permission_level"]

        # 记录执行开始
        exec_id = len(self.execution_history)
        start_time = time.time()

        try:
            # 根据权限级别应用不同的安全措施
            if permission_level == ToolPermission.READ_ONLY:
                # 只读工具：可以安全执行
                result = tool_func(**args)
            elif permission_level == ToolPermission.LOCAL_EXECUTION:
                # 本地执行：限制性沙箱
                result = self._execute_in_sandbox(tool_func, args)
            else:  # FULL_ACCESS
                # 完全访问：直接执行（危险）
                result = tool_func(**args)

            # 记录执行成功
            execution_record = {
                "id": exec_id,
                "timestamp": time.time(),
                "role": role,
                "tool": tool_name,
                "args": args,
                "success": True,
                "result": str(result)[:500],  # 截断长结果
                "duration": time.time() - start_time
            }
            self.execution_history.append(execution_record)

            return {"success": True, "result": result}

        except Exception as e:
            # 记录执行失败
            execution_record = {
                "id": exec_id,
                "timestamp": time.time(),
                "role": role,
                "tool": tool_name,
                "args": args,
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time
            }
            self.execution_history.append(execution_record)

            return {"success": False, "error": str(e)}

    def _execute_in_sandbox(self, tool_func: Callable, args: Dict) -> Any:
        """在沙箱中执行工具（基于子进程的隔离）"""
        import multiprocessing
        import pickle
        import traceback
        from multiprocessing import TimeoutError as MP_TimeoutError

        # 创建通信队列
        result_queue = multiprocessing.Queue()
        error_queue = multiprocessing.Queue()

        # 定义在子进程中执行的包装函数
        def worker(func_bytes: bytes, args_bytes: bytes, result_q, error_q):
            """子进程工作函数"""
            try:
                # 反序列化函数和参数
                import pickle
                func = pickle.loads(func_bytes)
                args_dict = pickle.loads(args_bytes)

                # 执行函数
                result = func(**args_dict)

                # 序列化结果
                result_q.put(("success", pickle.dumps(result)))

            except Exception as e:
                # 捕获异常并发送
                error_info = {
                    "type": type(e).__name__,
                    "message": str(e),
                    "traceback": traceback.format_exc()
                }
                error_q.put(("error", pickle.dumps(error_info)))

        try:
            # 序列化函数和参数
            # 注意：函数必须是可pickle的（不能是lambda或闭包）
            func_bytes = pickle.dumps(tool_func)
            args_bytes = pickle.dumps(args)

            # 创建子进程
            process = multiprocessing.Process(
                target=worker,
                args=(func_bytes, args_bytes, result_queue, error_queue),
                daemon=True  # 主进程退出时子进程也会退出
            )

            process.start()

            # 等待结果，设置超时（30秒）
            timeout = 30
            process.join(timeout=timeout)

            if process.is_alive():
                # 超时，终止进程
                process.terminate()
                process.join(timeout=5)  # 等待终止
                if process.is_alive():
                    process.kill()  # 强制终止
                raise TimeoutError(f"工具执行超时（{timeout}秒）")

            # 检查结果
            if not result_queue.empty():
                status, result_bytes = result_queue.get()
                if status == "success":
                    return pickle.loads(result_bytes)

            if not error_queue.empty():
                status, error_bytes = error_queue.get()
                if status == "error":
                    error_info = pickle.loads(error_bytes)
                    error_msg = f"{error_info['type']}: {error_info['message']}"
                    raise RuntimeError(f"工具执行错误: {error_msg}")

            # 如果没有结果也没有错误，抛出异常
            raise RuntimeError("工具执行未返回结果")

        except (pickle.PickleError, EOFError) as e:
            # 序列化错误
            raise RuntimeError(f"工具无法序列化: {str(e)}")
        except Exception as e:
            # 其他错误
            raise RuntimeError(f"沙箱执行失败: {str(e)}")