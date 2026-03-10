"""
shell_executor.py - 沙箱 Shell 执行器
=====================================
在受限沙箱中执行白名单内命令，禁止链式/危险命令，工作目录锁定，超时与输出截断。
"""

import os
import shlex
import subprocess
from typing import Dict, Any, List

# 命令白名单：首词或「git + 子命令」必须匹配其一
ALLOWED_COMMANDS = [
    "python", "python3", "pip", "pip3",
    "pytest", "pylint", "mypy", "flake8",
    "cat", "ls", "head", "tail", "wc", "grep", "find",
    "git status", "git diff", "git log",
]

# 单词允许集合（不含 git 子命令）
_SINGLE_ALLOWED = {
    "python", "python3", "pip", "pip3",
    "pytest", "pylint", "mypy", "flake8",
    "cat", "ls", "head", "tail", "wc", "grep", "find",
}
# git 仅允许的子命令
_GIT_ALLOWED_SUBS = {"status", "diff", "log"}

# 禁止出现的子串（链式、管道、危险命令）
FORBIDDEN_PATTERNS = [
    "&&", "||", ";", "|",
    "rm -rf", "rm -fr", "sudo", "curl", "wget", "chmod", "chown",
]
# 禁止的首命令（避免 rm、sudo 等以参数形式出现）
_FORBIDDEN_FIRST = {"rm", "sudo", "curl", "wget", "chmod", "chown", "cd"}

MAX_OUTPUT_CHARS = 10000
MAX_TIMEOUT_SECONDS = 60


def _normalize_command_prefix(tokens: List[str]) -> str:
    """返回用于白名单匹配的前缀：首词 或 'git <sub>'。"""
    if not tokens:
        return ""
    first = tokens[0].strip().lower()
    if first == "git" and len(tokens) > 1:
        return f"git {tokens[1].strip().lower()}"
    return first


def _is_command_allowed(tokens: List[str]) -> bool:
    if not tokens:
        return False
    first = tokens[0].strip().lower()
    if first in _FORBIDDEN_FIRST:
        return False
    prefix = _normalize_command_prefix(tokens)
    if prefix in _SINGLE_ALLOWED:
        return True
    if prefix.startswith("git ") and prefix in ("git status", "git diff", "git log"):
        return True
    return False


def _check_forbidden(command: str) -> str:
    """若存在禁止模式则返回非空错误信息。"""
    raw = (command or "").strip()
    for pat in FORBIDDEN_PATTERNS:
        if pat in raw:
            return f"禁止包含: {pat!r}"
    return ""


def shell_executor(
    command: str,
    workspace_dir: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    """在沙箱中执行 shell 命令。

    - 仅允许白名单内命令前缀；禁止链式（&&/||/;）、管道、rm -rf、sudo、curl、wget、chmod、chown 等。
    - 工作目录锁定为 workspace_dir（由调用方保证路径合法）。
    - 超时硬限制 60 秒；stdout/stderr 各最多 10000 字符。

    Args:
        command: 单条命令字符串（将用 shlex.split 解析，不使用 shell）。
        workspace_dir: 工作目录，必须存在且为本次任务工作区。
        timeout: 超时秒数，最大 60。

    Returns:
        {"stdout": str, "stderr": str, "return_code": int, "timed_out": bool, "command": str}
    """
    command = (command or "").strip()
    workspace_dir = (workspace_dir or "").strip()
    if not command:
        return {
            "stdout": "",
            "stderr": "命令为空",
            "return_code": -1,
            "timed_out": False,
            "command": "",
        }
    if not workspace_dir or not os.path.isdir(workspace_dir):
        return {
            "stdout": "",
            "stderr": "工作目录无效或不存在",
            "return_code": -1,
            "timed_out": False,
            "command": command,
        }

    err = _check_forbidden(command)
    if err:
        return {
            "stdout": "",
            "stderr": err,
            "return_code": -1,
            "timed_out": False,
            "command": command,
        }

    try:
        args = shlex.split(command)
    except ValueError as e:
        return {
            "stdout": "",
            "stderr": f"命令解析失败: {e}",
            "return_code": -1,
            "timed_out": False,
            "command": command,
        }

    if not _is_command_allowed(args):
        return {
            "stdout": "",
            "stderr": f"命令不在白名单内，允许前缀: {ALLOWED_COMMANDS}",
            "return_code": -1,
            "timed_out": False,
            "command": command,
        }

    timeout = max(1, min(int(timeout), MAX_TIMEOUT_SECONDS))

    try:
        result = subprocess.run(
            args,
            shell=False,
            cwd=workspace_dir,
            capture_output=True,
            timeout=timeout,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        stdout = (result.stdout or "")[:MAX_OUTPUT_CHARS]
        stderr = (result.stderr or "")[:MAX_OUTPUT_CHARS]
        return {
            "stdout": stdout,
            "stderr": stderr,
            "return_code": result.returncode,
            "timed_out": False,
            "command": command,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"执行超时（{timeout}s）",
            "return_code": -1,
            "timed_out": True,
            "command": command,
        }
    except FileNotFoundError as e:
        return {
            "stdout": "",
            "stderr": f"未找到可执行文件: {e}",
            "return_code": -1,
            "timed_out": False,
            "command": command,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "return_code": -1,
            "timed_out": False,
            "command": command,
        }
