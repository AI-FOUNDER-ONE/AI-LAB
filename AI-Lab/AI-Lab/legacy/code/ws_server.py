"""WebSocket推送服务模块。

本模块基于aiohttp实现WebSocket服务端，负责将系统状态快照
实时推送给前端（动态状态感知界面）。

设计要点：
- 推送延迟目标≤100ms（通信50ms + 状态机计算50ms）
- 支持多客户端并发连接
- 连接断开自动清理，无资源泄漏
- 提供REST健康检查端点供运维监控

遵循Google Python编程规范。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Set

import aiohttp
from aiohttp import web

from health_monitor import ModuleHealthMonitor
from models import SystemSnapshot

# 日志配置
logger = logging.getLogger(__name__)


class WebSocketServer:
    """WebSocket推送服务。

    管理所有前端WebSocket连接，在系统状态变更时
    向所有已连接客户端广播状态快照。

    Attributes:
        DEFAULT_HOST: 默认监听地址。
        DEFAULT_PORT: 默认监听端口。
    """

    DEFAULT_HOST: str = "0.0.0.0"
    DEFAULT_PORT: int = 8765

    def __init__(
        self,
        monitor: ModuleHealthMonitor,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        """初始化WebSocket服务。

        Args:
            monitor: 模块健康监控器实例，用于获取状态快照。
            host: 监听地址。
            port: 监听端口。
        """
        self._monitor = monitor
        self._host = host
        self._port = port
        # 已连接的WebSocket客户端集合
        self._clients: Set[web.WebSocketResponse] = set()
        # aiohttp应用实例
        self._app = web.Application()
        self._app.router.add_get("/ws", self._ws_handler)
        self._app.router.add_get("/health", self._health_handler)
        # 运行器
        self._runner: web.AppRunner | None = None

    @property
    def client_count(self) -> int:
        """当前已连接的客户端数量。"""
        return len(self._clients)

    async def broadcast(self, snapshot: SystemSnapshot) -> None:
        """向所有已连接客户端广播系统状态快照。

        此方法作为ModuleHealthMonitor的on_state_change回调。
        广播失败的客户端会被自动清理。

        Args:
            snapshot: 系统状态快照。
        """
        if not self._clients:
            return

        message = json.dumps(
            snapshot.to_dict(), ensure_ascii=False
        )
        # 并发发送，收集失败的连接
        stale_clients: list[web.WebSocketResponse] = []

        for ws in self._clients:
            try:
                await ws.send_str(message)
            except (ConnectionResetError, asyncio.CancelledError):
                stale_clients.append(ws)
            except Exception:
                logger.exception("向客户端推送消息失败。")
                stale_clients.append(ws)

        # 清理断开的连接
        for ws in stale_clients:
            self._clients.discard(ws)
            logger.info(
                "已清理断开的客户端连接，当前连接数: %d",
                len(self._clients),
            )

    async def _ws_handler(
        self, request: web.Request
    ) -> web.WebSocketResponse:
        """WebSocket连接处理器。

        客户端连接后立即推送一次当前状态快照，
        后续由状态变更事件驱动推送。

        Args:
            request: HTTP请求对象。

        Returns:
            WebSocket响应对象。
        """
        ws = web.WebSocketResponse(
            heartbeat=30.0,  # 30秒心跳保活
        )
        await ws.prepare(request)

        # 注册客户端
        self._clients.add(ws)
        logger.info(
            "新WebSocket客户端已连接，当前连接数: %d",
            len(self._clients),
        )

        # 立即推送当前状态快照（首次连接同步）
        try:
            snapshot = self._monitor.get_snapshot()
            await ws.send_str(
                json.dumps(snapshot.to_dict(), ensure_ascii=False)
            )
        except Exception:
            logger.exception("首次状态推送失败。")

        # 保持连接，监听客户端消息（主要用于保活）
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # 客户端可发送ping消息，服务端回复pong
                    if msg.data == "ping":
                        await ws.send_str("pong")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(
                        "WebSocket连接异常: %s",
                        ws.exception(),
                    )
        finally:
            # 连接关闭，清理客户端
            self._clients.discard(ws)
            logger.info(
                "WebSocket客户端已断开，当前连接数: %d",
                len(self._clients),
            )

        return ws

    async def _health_handler(
        self, request: web.Request
    ) -> web.Response:
        """REST健康检查端点。

        返回当前系统状态和连接数，供运维监控使用。

        Args:
            request: HTTP请求对象。

        Returns:
            JSON格式的健康状态响应。
        """
        snapshot = self._monitor.get_snapshot()
        health_data: Dict[str, Any] = {
            "status": "running",
            "system_state": snapshot.system_state.value,
            "connected_clients": self.client_count,
            "timestamp": snapshot.timestamp,
        }
        return web.json_response(health_data)

    async def start(self) -> None:
        """启动WebSocket服务。"""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(
            self._runner, self._host, self._port
        )
        await site.start()
        logger.info(
            "WebSocket服务已启动: ws://%s:%d/ws",
            self._host,
            self._port,
        )

    async def stop(self) -> None:
        """停止WebSocket服务，关闭所有连接。"""
        # 关闭所有客户端连接
        for ws in list(self._clients):
            await ws.close()
        self._clients.clear()

        # 停止HTTP服务
        if self._runner:
            await self._runner.cleanup()
            logger.info("WebSocket服务已停止。")
