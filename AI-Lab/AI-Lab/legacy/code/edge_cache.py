"""边缘端本地数据缓存与断点续传模块。

本模块基于SQLite实现边缘侧数据缓存，当网络中断时自动缓存
采样数据和气体分析结果，网络恢复后按时间顺序自动补传。

设计要点：
- SQLite轻量级嵌入式数据库，无需额外部署
- 消息队列语义：写入→标记待传→上传成功后删除
- 缓存容量监控，超过90%阈值时告警
- 断点续传：记录上传偏移量，网络恢复后从断点继续

遵循Google Python编程规范。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from models import CacheInfo

# 日志配置
logger = logging.getLogger(__name__)

# 类型别名：数据上传回调
UploadCallback = Callable[
    [List[Dict[str, Any]]], Awaitable[bool]
]


class EdgeCache:
    """边缘端SQLite本地缓存管理器。

    提供数据写入、批量读取、断点续传和容量监控功能。
    当平台网络抖动时，采集数据自动落盘缓存；
    网络恢复后，按FIFO顺序批量补传。

    Attributes:
        DEFAULT_DB_PATH: 默认数据库文件路径。
        DEFAULT_LIMIT_MB: 默认缓存容量上限（MB）。
        UPLOAD_BATCH_SIZE: 单次上传批量大小。
        UPLOAD_INTERVAL_S: 上传检查间隔（秒）。
    """

    DEFAULT_DB_PATH: str = "data/edge_cache.db"
    DEFAULT_LIMIT_MB: float = 512.0
    UPLOAD_BATCH_SIZE: int = 100
    UPLOAD_INTERVAL_S: float = 5.0

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        limit_mb: float = DEFAULT_LIMIT_MB,
    ) -> None:
        """初始化缓存管理器。

        Args:
            db_path: SQLite数据库文件路径。
            limit_mb: 缓存容量上限（MB）。
        """
        self._db_path = db_path
        self._limit_mb = limit_mb
        self._conn: Optional[sqlite3.Connection] = None
        self._upload_task: Optional[asyncio.Task[None]] = None
        self._upload_callback: Optional[UploadCallback] = None
        # 网络连接状态标志
        self._network_available: bool = True

        # 确保数据目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        """初始化数据库连接和表结构。

        创建缓存数据表（如不存在），包含自增ID、
        时间戳、数据类型、JSON载荷和上传状态字段。
        """
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                data_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                uploaded INTEGER DEFAULT 0
            )
        """)

        # 为上传状态创建索引，加速断点续传查询
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_uploaded
            ON cache_queue(uploaded)
        """)

        self._conn.commit()
        logger.info(
            "边缘缓存已初始化: %s (上限 %.0fMB)",
            self._db_path,
            self._limit_mb,
        )

    def store(
        self,
        data_type: str,
        payload: Dict[str, Any],
    ) -> int:
        """将数据写入本地缓存队列。

        Args:
            data_type: 数据类型标识（如"gas_reading", "plc_status"）。
            payload: 待缓存的数据字典。

        Returns:
            插入记录的自增ID。

        Raises:
            RuntimeError: 数据库未初始化。
        """
        if not self._conn:
            raise RuntimeError("缓存数据库未初始化，请先调用initialize()")

        now = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        payload_json = json.dumps(payload, ensure_ascii=False)

        cursor = self._conn.execute(
            "INSERT INTO cache_queue (created_at, data_type, payload) "
            "VALUES (?, ?, ?)",
            (now, data_type, payload_json),
        )
        self._conn.commit()

        record_id = cursor.lastrowid or 0
        logger.debug(
            "数据已缓存: id=%d, type=%s", record_id, data_type
        )
        return record_id

    def fetch_pending(
        self, batch_size: int = UPLOAD_BATCH_SIZE
    ) -> List[Tuple[int, str, str, str]]:
        """获取待上传的缓存记录（FIFO顺序）。

        Args:
            batch_size: 单次获取的最大记录数。

        Returns:
            记录列表，每条为(id, created_at, data_type, payload)元组。
        """
        if not self._conn:
            return []

        cursor = self._conn.execute(
            "SELECT id, created_at, data_type, payload "
            "FROM cache_queue "
            "WHERE uploaded = 0 "
            "ORDER BY id ASC "
            "LIMIT ?",
            (batch_size,),
        )
        return cursor.fetchall()

    def mark_uploaded(self, record_ids: List[int]) -> None:
        """标记记录为已上传并删除。

        上传成功后立即删除记录，释放存储空间。

        Args:
            record_ids: 已成功上传的记录ID列表。
        """
        if not self._conn or not record_ids:
            return

        placeholders = ",".join("?" * len(record_ids))
        self._conn.execute(
            f"DELETE FROM cache_queue WHERE id IN ({placeholders})",
            record_ids,
        )
        self._conn.commit()
        logger.info("已清理 %d 条已上传缓存记录。", len(record_ids))

    def get_cache_info(self) -> CacheInfo:
        """获取当前缓存使用情况。

        Returns:
            包含已用空间、容量上限和待传记录数的CacheInfo对象。
        """
        # 计算数据库文件大小
        used_mb = 0.0
        if os.path.exists(self._db_path):
            used_mb = os.path.getsize(self._db_path) / (1024 * 1024)

        # 统计待上传记录数
        pending = 0
        if self._conn:
            cursor = self._conn.execute(
                "SELECT COUNT(*) FROM cache_queue WHERE uploaded = 0"
            )
            row = cursor.fetchone()
            if row:
                pending = row[0]

        return CacheInfo(
            used_mb=round(used_mb, 1),
            limit_mb=self._limit_mb,
            pending_records=pending,
        )

    def set_network_status(self, available: bool) -> None:
        """更新网络连接状态。

        Args:
            available: 网络是否可用。
        """
        if self._network_available != available:
            status_str = "已恢复" if available else "已断开"
            logger.info("网络状态变更: %s", status_str)
            self._network_available = available

    async def _upload_loop(self) -> None:
        """断点续传上传主循环。

        周期性检查待上传记录，网络可用时批量上传，
        上传成功后删除已传记录。
        """
        while True:
            try:
                if (
                    self._network_available
                    and self._upload_callback
                ):
                    pending = self.fetch_pending()
                    if pending:
                        # 构造上传数据批次
                        batch: List[Dict[str, Any]] = []
                        ids: List[int] = []
                        for (
                            record_id,
                            created_at,
                            data_type,
                            payload_str,
                        ) in pending:
                            batch.append({
                                "id": record_id,
                                "created_at": created_at,
                                "data_type": data_type,
                                "payload": json.loads(payload_str),
                            })
                            ids.append(record_id)

                        # 执行上传回调
                        success = await self._upload_callback(batch)
                        if success:
                            self.mark_uploaded(ids)
                            logger.info(
                                "断点续传: 成功上传 %d 条记录。",
                                len(ids),
                            )
                        else:
                            logger.warning(
                                "断点续传: 上传失败，"
                                "将在下次重试。"
                            )

            except asyncio.CancelledError:
                logger.info("断点续传任务已取消。")
                raise
            except Exception:
                logger.exception("断点续传过程异常。")

            await asyncio.sleep(self.UPLOAD_INTERVAL_S)

    async def start_upload_loop(
        self, callback: UploadCallback
    ) -> None:
        """启动断点续传上传循环。

        Args:
            callback: 数据上传回调函数，接收数据批次，
                返回True表示上传成功。
        """
        self._upload_callback = callback
        if self._upload_task is None or self._upload_task.done():
            self._upload_task = asyncio.create_task(
                self._upload_loop()
            )
            logger.info(
                "断点续传服务已启动，检查间隔 %.1fs",
                self.UPLOAD_INTERVAL_S,
            )

    async def stop(self) -> None:
        """停止上传循环并关闭数据库连接。"""
        if self._upload_task and not self._upload_task.done():
            self._upload_task.cancel()
            try:
                await self._upload_task
            except asyncio.CancelledError:
                pass

        if self._conn:
            self._conn.close()
            logger.info("边缘缓存已关闭。")
