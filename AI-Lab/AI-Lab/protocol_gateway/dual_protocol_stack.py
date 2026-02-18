

class DualProtocolGateway:
    """IEC 61850 + Modbus TCP 双协议栈网关

    延迟预算（端到端 ≤ 100ms）：
    Modbus采集 5-20ms + 网关处理 2-5ms + GOOSE发布 1-4ms + 网络冗余 5-10ms = 13-39ms典型值
    最坏情况含重传 60-80ms，满足100ms约束。
    强电磁干扰应对：TCP自动重传 + GOOSE重发 + 心跳快速切换冗余链路，目标握手成功率≥99%
    """
    MAX_E2E_LATENCY_MS = 100.0
    MIN_SUCCESS_RATE = 0.99
    HEARTBEAT_INTERVAL_S = 2.0
    STALE_DATA_THRESHOLD_MS = 500.0

    def __init__(self, iec61850_config: Dict[str, Any], modbus_config: Dict[str, Any]):
        self._iec61850 = IEC61850Adapter(iec61850_config)
        self._modbus = ModbusTCPAdapter(modbus_config)
        self._running = False
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._mapping_table: Dict[int, str] = {}
        self._logger = logging.getLogger("Gateway")

    def configure_mapping(self, mapping: Dict[int, str]) -> None:
        self._mapping_table = mapping
        self._logger.info("已配置 %d 条协议映射规则", len(mapping))

    async def start(self) -> None:
        self._logger.info("启动双协议栈网关...")
        results = await asyncio.gather(self._iec61850.connect(), self._modbus.connect(), return_exceptions=True)
        if results[0] is not True:
            if not await self._iec61850.reconnect():
                raise ConnectionError("IEC 61850 初始化失败")
        if results[1] is not True:
            if not await self._modbus.reconnect():
                raise ConnectionError("Modbus TCP 初始化失败")
        self._running = True
        self._logger.info("双协议栈网关启动成功")
        await asyncio.gather(self._polling_loop(), self._forwarding_loop(), self._health_monitor())

    async def stop(self) -> None:
        self._running = False
        await asyncio.gather(self._iec61850.disconnect(), self._modbus.disconnect())

    async def _polling_loop(self) -> None:
        interval = self._modbus.config.get("poll_interval_s", 0.05)
        while self._running:
            try:
                msg = await self._modbus.receive()
                if msg and msg.quality == DataQuality.GOOD:
                    await self._message_queue.put(msg)
            except Exception as e:
                self._logger.error("轮询异常: %s", e)
            await asyncio.sleep(interval)

    async def _forwarding_loop(self) -> None:
        while self._running:
            try:
                msg = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                if msg.age_ms > self.STALE_DATA_THRESHOLD_MS:
                    continue
                converted = self._convert_modbus_to_iec61850(msg)
                if converted:
                    await self._iec61850.send(converted)
            except asyncio.TimeoutError:
                continue

    def _convert_modbus_to_iec61850(self, msg: ProtocolMessage) -> Optional[ProtocolMessage]:
        iec_ref = self._mapping_table.get(msg.data.get("address", 0))
        if not iec_ref:
            return None
        return ProtocolMessage(
            protocol=ProtocolType.IEC_61850_MMS, source_addr="gateway",
            timestamp_ms=time.time() * 1000,
            data={"ref": iec_ref, "value": msg.data.get("payload"), "quality": msg.quality.value},
            quality=msg.quality)

    async def _health_monitor(self) -> None:
        while self._running:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL_S)
            for a in [self._iec61850, self._modbus]:
                if a.stats.total_sent > 100 and a.stats.success_rate < self.MIN_SUCCESS_RATE:
                    self._logger.warning("[%s] 成功率 %.2f%%", a.name, a.stats.success_rate * 100)
                if a.stats.p99_latency_ms > self.MAX_E2E_LATENCY_MS:
                    self._logger.warning("[%s] P99延迟 %.1fms", a.name, a.stats.p99_latency_ms)
                if not a.is_connected:
                    await a.reconnect()

    def get_diagnostics(self) -> Dict[str, Any]:
        def _info(a: ProtocolAdapter) -> Dict:
            return {"connected": a.is_connected, "success_rate": f"{a.stats.success_rate:.4f}",
                    "avg_latency_ms": f"{a.stats.avg_latency_ms:.1f}", "p99_latency_ms": f"{a.stats.p99_latency_ms:.1f}",
                    "sent": a.stats.total_sent, "errors": a.stats.total_errors}
        return {"running": self._running, "queue": self._message_queue.qsize(),
                "iec61850": _info(self._iec61850), "modbus": _info(self._modbus), "rules": len(self._mapping_table)}


async def main():
    """向家坝电站取油装置 - 双协议栈网关启动入口"""
    gw = DualProtocolGateway(
        {"host": "192.168.1.10", "mms_port": 102, "connect_timeout_s": 5.0, "read_timeout_s": 1.0},
        {"host": "192.168.1.20", "port": 502, "connect_timeout_s": 5.0, "read_timeout_s": 1.0, "poll_interval_s": 0.05})
    gw.configure_mapping({
        40001: "XCBR1$ST$Pos", 40010: "MMXU1$MX$TotW", 40020: "SIML1$DC$OilTemp",
        40021: "SIML1$DC$OilLevel", 40022: "SIML1$DC$OilPressure",
        40030: "SOPM1$ST$SampleValve", 40031: "SOPM1$ST$DrainValve", 40040: "CALH1$ST$GasAlarm"})
    try:
        await gw.start()
    except ConnectionError as e:
        logger.error("启动失败: %s", e)
    finally:
        await gw.stop()

if __name__ == "__main__":
    asyncio.run(main())
