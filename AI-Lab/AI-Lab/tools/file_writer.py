"""
file_writer.py - 工作区文件写入工具
====================================
结构化写入 workspace 文件，路径限定在 workspace 内，写入前备份已存在文件。
"""

import os
import time
from typing import Dict, Any, Optional

MAX_CONTENT_BYTES = 500 * 1024  # 500KB


def _resolve_and_validate_path(filepath: str, workspace_dir: str) -> Optional[str]:
    """解析为绝对路径并校验在 workspace 内，失败返回 None。"""
    if not workspace_dir or not (filepath or "").strip():
        return None
    base = os.path.normpath(workspace_dir.rstrip(os.sep))
    full = os.path.normpath(os.path.join(base, filepath.strip().lstrip("/")))
    try:
        real_base = os.path.realpath(base)
        real_full = os.path.realpath(full)
    except (ValueError, OSError):
        return None
    if not real_full.startswith(real_base):
        return None
    return full


def file_writer(
    filepath: str,
    content: str,
    workspace_dir: str,
    mode: str = "write",
    line_number: Optional[int] = None,
) -> Dict[str, Any]:
    """写入 workspace 文件。

    Args:
        filepath: 相对于 workspace_dir 的路径（如 "src/main.py"）
        content: 要写入的文本内容
        workspace_dir: 工作区根目录
        mode: "write"（覆盖）、"append"（追加）、"insert"（在指定行后插入，需 line_number）
        line_number: 仅 mode="insert" 时有效，在该行号之后插入 content

    Returns:
        {"path": str, "written": bool, "size": int, "message": str}
    """
    full = _resolve_and_validate_path(filepath, workspace_dir)
    if full is None:
        return {
            "path": filepath or "",
            "written": False,
            "size": 0,
            "message": "路径无效或在 workspace 外，拒绝写入",
        }
    raw = (content or "").encode("utf-8")
    if len(raw) > MAX_CONTENT_BYTES:
        return {
            "path": full,
            "written": False,
            "size": 0,
            "message": f"内容超过 {MAX_CONTENT_BYTES // 1024}KB 限制，拒绝写入",
        }
    mode = (mode or "write").lower()
    if mode not in ("write", "append", "insert"):
        return {"path": full, "written": False, "size": 0, "message": f"不支持的 mode: {mode}"}
    if mode == "insert" and line_number is None:
        return {"path": full, "written": False, "size": 0, "message": "insert 模式需要提供 line_number"}
    if mode == "insert" and not os.path.isfile(full):
        return {"path": full, "written": False, "size": 0, "message": "insert 模式要求文件已存在"}

    try:
        dirname = os.path.dirname(full)
        os.makedirs(dirname, exist_ok=True)
    except OSError as e:
        return {"path": full, "written": False, "size": 0, "message": f"创建目录失败: {e}"}

    # 写入前备份已存在文件到 workspace_dir/.backup/
    if os.path.isfile(full):
        try:
            base = os.path.normpath(workspace_dir.rstrip(os.sep))
            backup_base = os.path.join(base, ".backup")
            os.makedirs(backup_base, exist_ok=True)
            safe_name = filepath.strip().lstrip("/").replace(os.sep, "_").replace("/", "_")
            stamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_base, f"{safe_name}.{stamp}")
            with open(full, "rb") as f:
                backup_data = f.read()
            with open(backup_path, "wb") as f:
                f.write(backup_data)
        except OSError:
            pass  # 备份失败不阻断写入

    try:
        if mode == "write":
            with open(full, "w", encoding="utf-8") as f:
                f.write(content or "")
            size = os.path.getsize(full)
            return {"path": full, "written": True, "size": size, "message": "已覆盖写入"}

        if mode == "append":
            with open(full, "a", encoding="utf-8") as f:
                f.write(content or "")
            size = os.path.getsize(full)
            return {"path": full, "written": True, "size": size, "message": "已追加写入"}

        # insert: 在 line_number 行后插入
        with open(full, "r", encoding="utf-8") as f:
            lines = f.readlines()
        line_index = (line_number or 1) - 1
        if line_index < 0:
            line_index = 0
        if line_index > len(lines):
            line_index = len(lines)
        insert_content = (content or "") if not content.endswith("\n") else content
        new_lines = lines[: line_index + 1] + [insert_content] + lines[line_index + 1 :]
        with open(full, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        size = os.path.getsize(full)
        return {"path": full, "written": True, "size": size, "message": f"已在第 {line_number} 行后插入"}
    except OSError as e:
        return {"path": full, "written": False, "size": 0, "message": str(e)}
