"""
file_reader.py - 工作区文件读取工具
====================================
读取 workspace 中已有文件的内容。路径限定在 workspace 内，防止路径穿越。
"""

import os
from typing import Dict, Any

MAX_FILE_SIZE_BYTES = 100 * 1024  # 100KB


def file_reader(filepath: str, workspace_dir: str) -> Dict[str, Any]:
    """读取 workspace 中的文件。

    Args:
        filepath: 相对于 workspace_dir 的路径（如 "src/main.py"）
        workspace_dir: 工作区根目录

    Returns:
        {"path": str, "content": str, "size": int, "exists": bool}
        二进制文件时额外 "binary": True，content 为 "[binary file, size: XXX bytes]"
        超长文本时 content 截断并带截断警告。
    """
    if not workspace_dir or not (filepath or "").strip():
        return {
            "path": filepath or "",
            "content": "",
            "size": 0,
            "exists": False,
        }
    base = os.path.normpath(workspace_dir.rstrip(os.sep))
    full = os.path.normpath(os.path.join(base, filepath.strip().lstrip("/")))
    try:
        real_base = os.path.realpath(base)
        real_full = os.path.realpath(full)
    except (ValueError, OSError):
        return {"path": full, "content": "", "size": 0, "exists": False}
    if not real_full.startswith(real_base):
        return {
            "path": full,
            "content": "",
            "size": 0,
            "exists": False,
        }
    if not os.path.isfile(full):
        return {
            "path": full,
            "content": "",
            "size": 0,
            "exists": False,
        }
    size = os.path.getsize(full)
    try:
        with open(full, "rb") as f:
            raw = f.read(MAX_FILE_SIZE_BYTES + 1)
    except OSError:
        return {"path": full, "content": "", "size": size, "exists": True}

    # 二进制检测：含 null 或无法 UTF-8 解码
    is_binary = b"\x00" in raw or not _is_utf8(raw)
    if is_binary:
        return {
            "path": full,
            "content": f"[binary file, size: {size} bytes]",
            "size": size,
            "exists": True,
            "binary": True,
        }

    text = raw.decode("utf-8", errors="replace")
    truncated = len(raw) > MAX_FILE_SIZE_BYTES
    if truncated:
        text = text[:MAX_FILE_SIZE_BYTES]
        if not text.endswith("\n"):
            text += "\n"
        text += f"\n... [truncated, total {size} bytes, limit {MAX_FILE_SIZE_BYTES}]\n"
    return {
        "path": full,
        "content": text,
        "size": size,
        "exists": True,
    }


def _is_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False
