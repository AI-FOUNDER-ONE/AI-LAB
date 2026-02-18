"""Modbus TCP数据采集服务模块。

本模块负责通过Modbus TCP协议与PLC控制器和气相色谱仪通信，
周期性采集硬件模块状态和气体浓度数据，并将结果上报给
ModuleHealthMonitor进行状态推导。

设计要点：
- 单次Modbus读响应≤50ms（硬约束），留50ms给状态机处理，总延迟≤100ms
- 采集服务按模块独立运行，单模块通信故障不影响其他模块
- 支持Modbus TCP功能码0x03（读保持寄存器）和0x04（读输入寄存器）
- 数据解析采用IEEE 754大端序浮点数

遵循Google Python编程规范。
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from typing import Dict, List, Optional, Tuple

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from health_monitor import ModuleHealthMonitor
from models import (
    CHARACTERISTIC_GASES,
    GasReading,
    ModuleID,
    ModuleState,
)

# 日志配置
logger = logging.getLogger(__name__)


class ModbusCollectorConfig:
    """Modbus采集器配置。

    Attributes:
        host: 目标设备IP地址。
        port: Modbus TCP端口，默认502。
        slave_id: 从站地址，默认1。
        poll_interval_s: 轮询间隔（秒），默认1.0。
        timeout_s: 单次通信超时（秒），默认1.0。
        max_response_ms: 单次读响应上限（毫秒），默认50。
    """

    def __init__(
        self,
        host: str,
        port: int = 502,
        slave_id: int = 1,
        poll_interval_s: float = 1.0,
        timeout_s: float = 1.0,
        max_response_ms: float = 50.0,
    ) -> None:
        self.host = host
        self.port = port
        self.slave_id = slave_id
        self.poll_interval_s = poll_interval_s
        self.timeout_s = timeout_s
        self.max_response_ms = max_response_ms


class PLCCollector:
    """PLC控制模块Modbus TCP采集器。

    负责采集PLC（西门子S7-1500）的运行状态，包括：
    - 伺服控制状态（取样阀对接位置）
    - 油路压力/温度传感器数据
    - 消泡与真空脱气流程状态

    通过Modbus TCP功能码0x03/0x04读取寄存器数据。
    """

    # PLC寄存器地址映射
    REG_SERVO_STATUS = 0       # 伺服状态寄存器起始地址
    REG_PRESSURE = 10          # 压力传感器寄存器起始地址
    REG_TEMPERATURE = 12       # 温度传感器寄存器起始地址
    REG_DEGAS_STATUS = 14      # 脱气流程状态寄存器
    REG_SYSTEM_STATUS = 16     # PLC系统状态寄存器

    def __init__(
        self,
        config: ModbusCollectorConfig,
        monitor: ModuleHealthMonitor,
    ) -> None:
        """初始化PLC采集器。

        Args:
            config: Modbus连接配置。
            monitor: 健康监控器，用于上报心跳和状态。
        """
        self._config = config
        self._monitor = monitor
        self._client: Optional[AsyncModbusTcpClient] = None
        self._task: Optional[asyncio.Task[None]] = None
        # 最近一次采集的防护参数数据
        self._last_readings: Dict[str, float] = {}

    @property
    def last_readings(self) -> Dict[str, float]:
        """获取最近一次采集的传感器数据。"""
        return self._last_readings.copy()

    async def _connect(self) -> bool:
        """建立Modbus TCP连接。

        Returns:
            连接是否成功。
        """
        try:
            self._client = AsyncModbusTcpClient(
                self._config.host,
                port=self._config.port,
                timeout=self._config.timeout_s,
            )
            connected = await self._client.connect()
            if connected:
                logger.info(
                    "PLC Modbus连接已建立: %s:%d",
                    self._config.host,
                    self._config.port,
                )
            return connected
        except Exception:
            logger.exception("PLC Modbus连接失败。")
            return False

    async def _read_registers(
        self,
        address: int,
        count: int,
    ) -> Optional[List[int]]:
        """读取输入寄存器并校验响应延迟。

        Args:
            address: 寄存器起始地址。
            count: 读取寄存器数量。

        Returns:
            寄存器值列表，失败返回None。
        """
        if not self._client:
            return None

        t0 = time.monotonic()
        try:
            resp = await self._client.read_input_registers(
                address,
                count=count,
                slave=self._config.slave_id,
            )
            latency_ms = (time.monotonic() - t0) * 1000

            if resp.isError():
                logger.warning(
                    "PLC寄存器读取错误 addr=%d: %s",
                    address,
                    resp,
                )
                return None

            # 校验响应延迟是否在硬约束内
            if latency_ms > self._config.max_response_ms:
                logger.warning(
                    "PLC响应延迟 %.1fms 超过阈值 %.1fms",
                    latency_ms,
                    self._config.max_response_ms,
                )

            return list(resp.registers)

        except ModbusException as e:
            logger.error("PLC Modbus通信异常: %s", e)
            return None

    @staticmethod
    def _registers_to_float(
        reg_high: int, reg_low: int
    ) -> float:
        """将两个16位寄存器转换为IEEE 754大端序浮点数。

        Args:
            reg_high: 高位寄存器值。
            reg_low: 低位寄存器值。

        Returns:
            解析后的浮点数值。
        """
        raw_bytes = struct.pack(">HH", reg_high, reg_low)
        return struct.unpack(">f", raw_bytes)[0]

    async def _poll_once(self) -> None:
        """执行一次完整的PLC数据采集。"""
        # 读取压力传感器（2个寄存器 = 1个float）
        pressure_regs = await self._read_registers(
            self.REG_PRESSURE, 2
        )
        if pressure_regs and len(pressure_regs) >= 2:
            pressure = self._registers_to_float(
                pressure_regs[0], pressure_regs[1]
            )
            self._last_readings["pressure_mpa"] = round(
                pressure, 3
            )

        # 读取温度传感器（2个寄存器 = 1个float）
        temp_regs = await self._read_registers(
            self.REG_TEMPERATURE, 2
        )
        if temp_regs and len(temp_regs) >= 2:
            temperature = self._registers_to_float(
                temp_regs[0], temp_regs[1]
            )
            self._last_readings["temperature_c"] = round(
                temperature, 1
            )

        # 读取系统状态寄存器
        status_regs = await self._read_registers(
            self.REG_SYSTEM_STATUS, 1
        )

        # 根据采集结果上报心跳
        if pressure_regs and temp_regs and status_regs:
            self._monitor.update_heartbeat(
                ModuleID.PLC,
                ModuleState.OK,
                detail=f"压力={self._last_readings.get('pressure_mpa', 0)}MPa "
                       f"温度={self._last_readings.get('temperature_c', 0)}°C",
            )
        else:
            self._monitor.update_heartbeat(
                ModuleID.PLC,
                ModuleState.FAULT,
                detail="部分寄存器读取失败",
            )

    async def _poll_loop(self) -> None:
        """PLC数据采集主循环。"""
        while True:
            try:
                # 确保连接可用
                if not self._client or not self._client.connected:
                    if not await self._connect():
                        self._monitor.update_heartbeat(
                            ModuleID.PLC,
                            ModuleState.FAULT,
                            detail="Modbus TCP连接失败",
                        )
                        await asyncio.sleep(
                            self._config.poll_interval_s
                        )
                        continue

                await self._poll_once()

            except asyncio.CancelledError:
                logger.info("PLC采集任务已取消。")
                raise
            except Exception:
                logger.exception("PLC采集过程异常。")
                self._monitor.update_heartbeat(
                    ModuleID.PLC,
                    ModuleState.FAULT,
                    detail="采集过程异常",
                )

            await asyncio.sleep(self._config.poll_interval_s)

    async def start(self) -> None:
        """启动PLC数据采集任务。"""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._poll_loop())
            logger.info(
                "PLC采集服务已启动，轮询间隔 %.1fs",
                self._config.poll_interval_s,
            )

    async def stop(self) -> None:
        """停止PLC数据采集任务并关闭连接。"""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client:
            self._client.close()
            logger.info("PLC采集服务已停止。")


class GCCollector:
    """气相色谱分析模块Modbus TCP采集器。

    负责采集全自动气相色谱仪的分析数据，覆盖变压器油中
    9种特征气体（H2, CH4, C2H6, C2H4, C2H2, CO, CO2, O2, N2）。

    每种气体占用2个寄存器（浓度值，IEEE 754浮点数），
    共需18个寄存器。
    """

    # 气体浓度寄存器起始地址
    REG_GAS_START = 0
    # 每种气体占用的寄存器数（2个16位 = 1个float32）
    REGS_PER_GAS = 2
    # 设备状态寄存器地址
    REG_DEVICE_STATUS = 36

    def __init__(
        self,
        config: ModbusCollectorConfig,
        monitor: ModuleHealthMonitor,
    ) -> None:
        """初始化色谱仪采集器。

        Args:
            config: Modbus连接配置。
            monitor: 健康监控器，用于上报心跳和状态。
        """
        self._config = config
        self._monitor = monitor
        self._client: Optional[AsyncModbusTcpClient] = None
        self._task: Optional[asyncio.Task[None]] = None
        # 最近一次采集的气体浓度数据
        self._last_readings: List[GasReading] = []

    @property
    def last_readings(self) -> List[GasReading]:
        """获取最近一次采集的气体浓度数据。"""
        return list(self._last_readings)

    async def _connect(self) -> bool:
        """建立Modbus TCP连接。"""
        try:
            self._client = AsyncModbusTcpClient(
                self._config.host,
                port=self._config.port,
                timeout=self._config.timeout_s,
            )
            connected = await self._client.connect()
            if connected:
                logger.info(
                    "色谱仪Modbus连接已建立: %s:%d",
                    self._config.host,
                    self._config.port,
                )
            return connected
        except Exception:
            logger.exception("色谱仪Modbus连接失败。")
            return False

    async def _poll_once(self) -> None:
        """执行一次完整的色谱数据采集。

        批量读取9种气体×2寄存器=18个寄存器，
        解析为IEEE 754大端序浮点数。
        """
        if not self._client:
            return

        total_regs = len(CHARACTERISTIC_GASES) * self.REGS_PER_GAS

        t0 = time.monotonic()
        try:
            resp = await self._client.read_input_registers(
                self.REG_GAS_START,
                count=total_regs,
                slave=self._config.slave_id,
            )
            latency_ms = (time.monotonic() - t0) * 1000

            if resp.isError():
                self._monitor.update_heartbeat(
                    ModuleID.GC,
                    ModuleState.FAULT,
                    detail=f"寄存器读取错误: {resp}",
                )
                return

            if latency_ms > self._config.max_response_ms:
                logger.warning(
                    "色谱仪响应延迟 %.1fms 超过阈值 %.1fms",
                    latency_ms,
                    self._config.max_response_ms,
                )

            # 解析9种气体浓度
            readings: List[GasReading] = []
            registers = resp.registers

            for i, gas_name in enumerate(CHARACTERISTIC_GASES):
                offset = i * self.REGS_PER_GAS
                if offset + 1 < len(registers):
                    raw = struct.pack(
                        ">HH",
                        registers[offset],
                        registers[offset + 1],
                    )
                    concentration = struct.unpack(">f", raw)[0]
                    readings.append(
                        GasReading(
                            gas_name=gas_name,
                            concentration_ppm=round(
                                concentration, 2
                            ),
                        )
                    )

            self._last_readings = readings

            # 上报心跳：采集成功
            self._monitor.update_heartbeat(
                ModuleID.GC,
                ModuleState.OK,
                detail=f"已采集{len(readings)}种气体，"
                       f"延迟{latency_ms:.1f}ms",
            )

        except ModbusException as e:
            logger.error("色谱仪Modbus通信异常: %s", e)
            self._monitor.update_heartbeat(
                ModuleID.GC,
                ModuleState.FAULT,
                detail=f"通信异常: {e}",
            )

    async def _poll_loop(self) -> None:
        """色谱数据采集主循环。"""
        while True:
            try:
                if not self._client or not self._client.connected:
                    if not await self._connect():
                        self._monitor.update_heartbeat(
                            ModuleID.GC,
                            ModuleState.FAULT,
                            detail="Modbus TCP连接失败",
                        )
                        await asyncio.sleep(
                            self._config.poll_interval_s
                        )
                        continue

                await self._poll_once()

            except asyncio.CancelledError:
                logger.info("色谱仪采集任务已取消。")
                raise
            except Exception:
                logger.exception("色谱仪采集过程异常。")
                self._monitor.update_heartbeat(
                    ModuleID.GC,
                    ModuleState.FAULT,
                    detail="采集过程异常",
                )

            await asyncio.sleep(self._config.poll_interval_s)

    async def start(self) -> None:
        """启动色谱数据采集任务。"""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._poll_loop())
            logger.info(
                "色谱仪采集服务已启动，轮询间隔 %.1fs",
                self._config.poll_interval_s,
            )

    async def stop(self) -> None:
        """停止色谱数据采集任务并关闭连接。"""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client:
            self._client.close()
            logger.info("色谱仪采集服务已停止。")
