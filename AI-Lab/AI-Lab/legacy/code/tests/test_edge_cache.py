"""边缘缓存与断点续传单元测试。

覆盖@Tester提出的关键测试场景：
- 数据写入与读取
- 断点续传FIFO顺序
- 缓存容量监控
- 网络中断/恢复场景
- 数据库初始化与清理

遵循Google Python编程规范。
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "code"))

from edge_cache import EdgeCache
from models import CacheInfo


# ============================================================
# 测试夹具
# ============================================================
@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """创建临时数据库路径。"""
    return str(tmp_path / "test_cache.db")


@pytest.fixture
def cache(temp_db_path: str) -> EdgeCache:
    """创建并初始化测试用缓存实例。"""
    c = EdgeCache(db_path=temp_db_path, limit_mb=10.0)
    c.initialize()
    return c


# ============================================================
# 初始化测试
# ============================================================
class TestInitialization:
    """缓存初始化测试。"""

    def test_initialize_creates_db_file(
        self, temp_db_path: str
    ) -> None:
        """初始化应创建SQLite数据库文件。"""
        cache = EdgeCache(db_path=temp_db_path)
        cache.initialize()
        assert os.path.exists(temp_db_path)

    def test_initialize_creates_parent_dir(
        self, tmp_path: Path
    ) -> None:
        """初始化应自动创建父目录。"""
        db_path = str(tmp_path / "subdir" / "deep" / "cache.db")
        cache = EdgeCache(db_path=db_path)
        cache.initialize()
        assert os.path.exists(db_path)

    def test_double_initialize_is_safe(
        self, temp_db_path: str
    ) -> None:
        """重复初始化不应报错（幂等性）。"""
        cache = EdgeCache(db_path=temp_db_path)
        cache.initialize()
        cache.initialize()  # 第二次不应抛异常

    def test_store_without_init_raises(
        self, temp_db_path: str
    ) -> None:
        """未初始化时写入应抛出RuntimeError。"""
        cache = EdgeCache(db_path=temp_db_path)
        with pytest.raises(RuntimeError, match="未初始化"):
            cache.store("test", {"key": "value"})


# ============================================================
# 数据写入与读取测试
# ============================================================
class TestStoreAndFetch:
    """数据写入与读取测试。"""

    def test_store_returns_positive_id(
        self, cache: EdgeCache
    ) -> None:
        """写入应返回正整数ID。"""
        record_id = cache.store(
            "gas_reading", {"H2": 15.5}
        )
        assert record_id > 0

    def test_store_increments_id(
        self, cache: EdgeCache
    ) -> None:
        """连续写入的ID应递增。"""
        id1 = cache.store("type_a", {"a": 1})
        id2 = cache.store("type_b", {"b": 2})
        assert id2 > id1

    def test_fetch_pending_returns_stored_data(
        self, cache: EdgeCache
    ) -> None:
        """读取待上传记录应返回已写入的数据。"""
        cache.store("gas_reading", {"H2": 15.5, "CH4": 3.2})
        pending = cache.fetch_pending()
        assert len(pending) == 1
        record_id, created_at, data_type, payload_str = pending[0]
        assert data_type == "gas_reading"
        payload = json.loads(payload_str)
        assert payload["H2"] == 15.5

    def test_fetch_pending_fifo_order(
        self, cache: EdgeCache
    ) -> None:
        """待上传记录应按FIFO顺序返回。"""
        cache.store("type_1", {"order": 1})
        cache.store("type_2", {"order": 2})
        cache.store("type_3", {"order": 3})
        pending = cache.fetch_pending()
        assert len(pending) == 3
        # 验证FIFO顺序
        orders = [
            json.loads(p[3])["order"] for p in pending
        ]
        assert orders == [1, 2, 3]

    def test_fetch_pending_respects_batch_size(
        self, cache: EdgeCache
    ) -> None:
        """批量读取应遵守batch_size限制。"""
        for i in range(10):
            cache.store("batch_test", {"i": i})
        pending = cache.fetch_pending(batch_size=3)
        assert len(pending) == 3

    def test_fetch_pending_empty_when_no_data(
        self, cache: EdgeCache
    ) -> None:
        """无数据时应返回空列表。"""
        pending = cache.fetch_pending()
        assert pending == []

    def test_store_chinese_content(
        self, cache: EdgeCache
    ) -> None:
        """中文内容应正确存储和读取。"""
        cache.store(
            "plc_status",
            {"detail": "伺服控制正常，压力0.5MPa"},
        )
        pending = cache.fetch_pending()
        payload = json.loads(pending[0][3])
        assert "伺服控制正常" in payload["detail"]


# ============================================================
# 标记上传与删除测试
# ============================================================
class TestMarkUploaded:
    """标记上传完成与记录删除测试。"""

    def test_mark_uploaded_removes_records(
        self, cache: EdgeCache
    ) -> None:
        """标记上传后记录应被删除。"""
        id1 = cache.store("type_a", {"a": 1})
        id2 = cache.store("type_b", {"b": 2})
        cache.mark_uploaded([id1])
        pending = cache.fetch_pending()
        assert len(pending) == 1
        assert pending[0][0] == id2

    def test_mark_uploaded_all(
        self, cache: EdgeCache
    ) -> None:
        """标记全部上传后应无待传记录。"""
        ids = [
            cache.store("test", {"i": i}) for i in range(5)
        ]
        cache.mark_uploaded(ids)
        pending = cache.fetch_pending()
        assert len(pending) == 0

    def test_mark_uploaded_empty_list(
        self, cache: EdgeCache
    ) -> None:
        """空ID列表不应报错。"""
        cache.mark_uploaded([])  # 不应抛异常

    def test_mark_uploaded_nonexistent_id(
        self, cache: EdgeCache
    ) -> None:
        """标记不存在的ID不应报错。"""
        cache.store("test", {"a": 1})
        cache.mark_uploaded([99999])  # 不存在的ID
        # 原记录应仍在
        pending = cache.fetch_pending()
        assert len(pending) == 1


# ============================================================
# 缓存信息与容量监控测试
# ============================================================
class TestCacheInfo:
    """缓存容量监控测试。"""

    def test_get_cache_info_initial(
        self, cache: EdgeCache
    ) -> None:
        """初始缓存信息应显示0待传记录。"""
        info = cache.get_cache_info()
        assert info.pending_records == 0
        assert info.limit_mb == 10.0

    def test_get_cache_info_after_store(
        self, cache: EdgeCache
    ) -> None:
        """写入数据后待传记录数应增加。"""
        for i in range(5):
            cache.store("test", {"i": i})
        info = cache.get_cache_info()
        assert info.pending_records == 5

    def test_get_cache_info_after_upload(
        self, cache: EdgeCache
    ) -> None:
        """上传完成后待传记录数应减少。"""
        ids = [
            cache.store("test", {"i": i}) for i in range(5)
        ]
        cache.mark_uploaded(ids[:3])
        info = cache.get_cache_info()
        assert info.pending_records == 2

    def test_cache_used_mb_is_float(
        self, cache: EdgeCache
    ) -> None:
        """已用空间应为浮点数。"""
        info = cache.get_cache_info()
        assert isinstance(info.used_mb, float)


# ============================================================
# 网络状态管理测试
# ============================================================
class TestNetworkStatus:
    """网络状态管理测试。"""

    def test_default_network_available(
        self, cache: EdgeCache
    ) -> None:
        """默认网络状态应为可用。"""
        assert cache._network_available is True

    def test_set_network_unavailable(
        self, cache: EdgeCache
    ) -> None:
        """设置网络不可用。"""
        cache.set_network_status(False)
        assert cache._network_available is False

    def test_set_network_available(
        self, cache: EdgeCache
    ) -> None:
        """网络恢复。"""
        cache.set_network_status(False)
        cache.set_network_status(True)
        assert cache._network_available is True

    def test_set_same_status_no_change(
        self, cache: EdgeCache
    ) -> None:
        """设置相同网络状态不应触发变更。"""
        cache.set_network_status(True)  # 与默认相同
        assert cache._network_available is True


# ============================================================
# 断点续传异步测试
# ============================================================
class TestUploadLoop:
    """断点续传上传循环测试。"""

    @pytest.mark.asyncio
    async def test_upload_loop_calls_callback(
        self, cache: EdgeCache
    ) -> None:
        """上传循环应调用回调函数。"""
        callback = AsyncMock(return_value=True)
        cache.UPLOAD_INTERVAL_S = 0.2

        # 写入测试数据
        cache.store("test", {"data": "value"})

        await cache.start_upload_loop(callback)
        await asyncio.sleep(0.5)
        await cache.stop()

        # 回调应被调用
        assert callback.call_count >= 1

    @pytest.mark.asyncio
    async def test_upload_success_removes_records(
        self, cache: EdgeCache
    ) -> None:
        """上传成功后缓存记录应被清理。"""
        callback = AsyncMock(return_value=True)
        cache.UPLOAD_INTERVAL_S = 0.2

        cache.store("test", {"data": "value"})

        await cache.start_upload_loop(callback)
        await asyncio.sleep(0.5)
        await cache.stop()

        # 记录应已被清理
        pending = cache.fetch_pending()
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_upload_failure_retains_records(
        self, cache: EdgeCache
    ) -> None:
        """上传失败时缓存记录应保留。"""
        callback = AsyncMock(return_value=False)
        cache.UPLOAD_INTERVAL_S = 0.2

        cache.store("test", {"data": "value"})

        await cache.start_upload_loop(callback)
        await asyncio.sleep(0.5)
        await cache.stop()

        # 记录应仍在
        pending = cache.fetch_pending()
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_network_down_skips_upload(
        self, cache: EdgeCache
    ) -> None:
        """网络不可用时应跳过上传。"""
        callback = AsyncMock(return_value=True)
        cache.UPLOAD_INTERVAL_S = 0.2

        cache.store("test", {"data": "value"})
        cache.set_network_status(False)

        await cache.start_upload_loop(callback)
        await asyncio.sleep(0.5)
        await cache.stop()

        # 网络不可用，回调不应被调用
        assert callback.call_count == 0
        # 记录应仍在
        pending = cache.fetch_pending()
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_start_and_stop(
        self, cache: EdgeCache
    ) -> None:
        """上传循环应能正常启动和停止。"""
        callback = AsyncMock(return_value=True)
        await cache.start_upload_loop(callback)
        await asyncio.sleep(0.3)
        await cache.stop()
