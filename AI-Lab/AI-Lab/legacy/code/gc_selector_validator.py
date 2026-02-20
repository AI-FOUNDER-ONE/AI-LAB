"""气相色谱仪选型验证CLI工具。

使用方式：
    python gc_selector_validator.py --host 192.168.1.100 --port 502
    python gc_selector_validator.py --host 192.168.1.100 --output-dir reports/

输出：终端彩色报告 + Markdown文件 + JSON数据文件 + HTML可视化报告

本工具用于色谱仪选型阶段，对候选设备执行Modbus TCP接口
一致性校验，包括功能码支持、响应延迟、批量读取能力和
连续读取稳定性测试。

遵循Google Python编程规范。
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pymodbus.client import ModbusTcpClient


# ============================================================
# 选型校验规则定义
# ============================================================
@dataclass(frozen=True)
class GCModbusValidation:
    """气相色谱仪Modbus TCP接口选型校验规则。

    必须项不满足则一票否决，加分项影响综合评分。

    Attributes:
        REQUIRED_FUNC_CODES: 必须支持的Modbus功能码集合。
        MIN_REGISTER_COUNT: 最少寄存器数量（9种气体×2寄存器）。
        MAX_RESPONSE_MS: 单次读响应上限（毫秒），硬约束。
        BULK_REGISTER_TARGET: 批量读取目标寄存器数。
        STABILITY_TEST_ROUNDS: 稳定性测试轮次。
    """

    REQUIRED_FUNC_CODES: frozenset = frozenset({0x03, 0x04})
    MIN_REGISTER_COUNT: int = 18
    MAX_RESPONSE_MS: float = 50.0
    BULK_REGISTER_TARGET: int = 40
    STABILITY_TEST_ROUNDS: int = 10


# ============================================================
# 验证结果数据结构
# ============================================================
@dataclass
class CheckItem:
    """单项校验结果。

    Attributes:
        name: 校验项名称。
        passed: 是否通过。
        required: 是否为必须项（不通过则整体不通过）。
        value: 实测值描述。
        threshold: 阈值要求描述。
        detail: 补充说明。
    """

    name: str
    passed: bool
    required: bool
    value: str
    threshold: str
    detail: str = ""


@dataclass
class ValidationReport:
    """完整验证报告。

    Attributes:
        host: 目标设备IP地址。
        port: Modbus TCP端口。
        timestamp: 验证执行时间（UTC ISO 8601）。
        overall_pass: 综合是否通过（所有必须项均通过）。
        checks: 各校验项结果列表。
        error: 全局错误信息（如连接失败）。
    """

    host: str
    port: int
    timestamp: str = ""
    overall_pass: bool = False
    checks: List[CheckItem] = field(default_factory=list)
    error: Optional[str] = None

    def __post_init__(self) -> None:
        """初始化时自动填充时间戳。"""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )


# ============================================================
# 核心验证逻辑
# ============================================================
def validate_gc_candidate(
    host: str,
    port: int = 502,
    slave_id: int = 1,
) -> ValidationReport:
    """对候选色谱仪执行全量Modbus TCP接口校验。

    校验项包括：
    1. 输入寄存器读取（FC=0x04）+ 响应延迟
    2. 保持寄存器读取（FC=0x03）
    3. 批量读取能力（加分项）
    4. 连续读取稳定性（10次取平均/最大值）

    Args:
        host: 色谱仪IP地址。
        port: Modbus TCP端口，默认502。
        slave_id: 从站地址，默认1。

    Returns:
        包含所有校验项结果的结构化验证报告。
    """
    rules = GCModbusValidation()
    report = ValidationReport(host=host, port=port)

    # 建立Modbus TCP连接
    client = ModbusTcpClient(host, port=port, timeout=2)
    if not client.connect():
        report.error = f"无法连接 {host}:{port}"
        return report

    try:
        # ---- 校验1：输入寄存器读取 + 响应延迟 ----
        t0 = time.monotonic()
        resp_input = client.read_input_registers(
            0, count=rules.MIN_REGISTER_COUNT, slave=slave_id
        )
        latency_input = (time.monotonic() - t0) * 1000

        input_ok = not resp_input.isError()
        latency_ok = latency_input <= rules.MAX_RESPONSE_MS

        report.checks.append(CheckItem(
            name="输入寄存器读取(FC=0x04)",
            passed=input_ok,
            required=True,
            value="成功" if input_ok else f"错误: {resp_input}",
            threshold=(
                f"FC 0x04 读取{rules.MIN_REGISTER_COUNT}寄存器"
            ),
        ))

        report.checks.append(CheckItem(
            name="单次读响应延迟",
            passed=latency_ok,
            required=True,
            value=f"{latency_input:.1f}ms",
            threshold=f"≤{rules.MAX_RESPONSE_MS}ms",
            detail="留50ms给状态机处理，总延迟≤100ms",
        ))

        # ---- 校验2：保持寄存器读取 ----
        resp_holding = client.read_holding_registers(
            0, count=rules.MIN_REGISTER_COUNT, slave=slave_id
        )
        holding_ok = not resp_holding.isError()

        report.checks.append(CheckItem(
            name="保持寄存器读取(FC=0x03)",
            passed=holding_ok,
            required=True,
            value="成功" if holding_ok else f"错误: {resp_holding}",
            threshold=(
                f"FC 0x03 读取{rules.MIN_REGISTER_COUNT}寄存器"
            ),
        ))

        # ---- 校验3：批量读取能力（加分项） ----
        resp_bulk = client.read_input_registers(
            0, count=rules.BULK_REGISTER_TARGET, slave=slave_id
        )
        bulk_ok = not resp_bulk.isError()

        report.checks.append(CheckItem(
            name="批量读取能力",
            passed=bulk_ok,
            required=False,
            value="支持" if bulk_ok else "不支持",
            threshold=(
                f"单次读取≥{rules.BULK_REGISTER_TARGET}寄存器"
            ),
            detail="加分项：一次轮询取完所有数据",
        ))

        # ---- 校验4：连续读取稳定性 ----
        latencies: List[float] = []
        for _ in range(rules.STABILITY_TEST_ROUNDS):
            t0 = time.monotonic()
            r = client.read_input_registers(
                0, count=rules.MIN_REGISTER_COUNT, slave=slave_id
            )
            if not r.isError():
                latencies.append(
                    (time.monotonic() - t0) * 1000
                )

        if latencies:
            avg_lat = sum(latencies) / len(latencies)
            max_lat = max(latencies)
            stability_ok = max_lat <= rules.MAX_RESPONSE_MS

            report.checks.append(CheckItem(
                name=(
                    f"连续读取稳定性"
                    f"({rules.STABILITY_TEST_ROUNDS}次)"
                ),
                passed=stability_ok,
                required=True,
                value=(
                    f"平均{avg_lat:.1f}ms / 最大{max_lat:.1f}ms"
                ),
                threshold=f"最大值≤{rules.MAX_RESPONSE_MS}ms",
                detail=f"成功{len(latencies)}/{rules.STABILITY_TEST_ROUNDS}次",
            ))

        # 汇总：所有必须项通过才算整体通过
        report.overall_pass = all(
            c.passed for c in report.checks if c.required
        )

    except Exception as e:
        report.error = f"验证过程异常: {e}"
    finally:
        client.close()

    return report


# ============================================================
# 输出：终端彩色报告
# ============================================================
def print_terminal_report(report: ValidationReport) -> None:
    """终端输出带ANSI颜色标识的验证报告。

    Args:
        report: 验证报告对象。
    """
    green = "\033[92m"
    red = "\033[91m"
    yellow = "\033[93m"
    reset = "\033[0m"

    status = (
        f"{green}✅ 通过{reset}"
        if report.overall_pass
        else f"{red}❌ 不通过{reset}"
    )

    print(f"\n{'='*55}")
    print(f"  气相色谱仪选型验证报告")
    print(f"  目标: {report.host}:{report.port}")
    print(f"  时间: {report.timestamp}")
    print(f"  结果: {status}")
    print(f"{'='*55}")

    if report.error:
        print(f"  {red}错误: {report.error}{reset}")
        print(f"{'='*55}\n")
        return

    for c in report.checks:
        tag = "[必须]" if c.required else "[加分]"
        if c.passed:
            icon = f"{green}✅{reset}"
        elif c.required:
            icon = f"{red}❌{reset}"
        else:
            icon = f"{yellow}⚠{reset}"

        print(f"  {icon} {tag} {c.name}")
        print(f"       实测: {c.value}  |  要求: {c.threshold}")
        if c.detail:
            print(f"       备注: {c.detail}")

    print(f"{'='*55}\n")


# ============================================================
# 输出：Markdown报告文件
# ============================================================
def generate_markdown_report(
    report: ValidationReport,
    output_dir: str = ".",
) -> str:
    """生成Markdown格式的选型验证报告文件。

    Args:
        report: 验证报告对象。
        output_dir: 输出目录路径。

    Returns:
        生成的Markdown文件路径。
    """
    status_emoji = "✅ 通过" if report.overall_pass else "❌ 不通过"
    lines = [
        "# 气相色谱仪选型验证报告",
        "",
        "| 项目 | 值 |",
        "|------|-----|",
        f"| 目标设备 | `{report.host}:{report.port}` |",
        f"| 验证时间 | {report.timestamp} |",
        f"| 综合结果 | {status_emoji} |",
        "",
    ]

    if report.error:
        lines.append(f"> ⚠ 错误: {report.error}")
    else:
        lines.append("## 校验明细")
        lines.append("")
        lines.append(
            "| 状态 | 类型 | 校验项 | 实测值 | 要求 | 备注 |"
        )
        lines.append(
            "|------|------|--------|--------|------|------|"
        )
        for c in report.checks:
            icon = "✅" if c.passed else (
                "❌" if c.required else "⚠"
            )
            tag = "必须" if c.required else "加分"
            detail = c.detail if c.detail else "-"
            lines.append(
                f"| {icon} | {tag} | {c.name} "
                f"| {c.value} | {c.threshold} | {detail} |"
            )

    lines.extend(["", "---", "*本报告由gc_selector_validator.py自动生成*"])

    filename = (
        f"gc_validation_{report.host.replace('.', '_')}"
        f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    )
    filepath = Path(output_dir) / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text("\n".join(lines), encoding="utf-8")
    return str(filepath)


# ============================================================
# 输出：JSON数据文件（供远程协作共享和测试消费）
# ============================================================
def export_json(
    report: ValidationReport,
    output_dir: str = ".",
) -> str:
    """导出JSON格式验证数据文件。

    JSON输出可供@Tester直接反序列化做断言，
    也可上传共享盘供远程协作评审。

    Args:
        report: 验证报告对象。
        output_dir: 输出目录路径。

    Returns:
        生成的JSON文件路径。
    """
    data: Dict[str, Any] = {
        "host": report.host,
        "port": report.port,
        "timestamp": report.timestamp,
        "overall_pass": report.overall_pass,
        "error": report.error,
        "checks": [asdict(c) for c in report.checks],
    }
    filename = (
        f"gc_validation_{report.host.replace('.', '_')}"
        f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    filepath = Path(output_dir) / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(filepath)


# ============================================================
# 输出：单文件HTML可视化报告
# ============================================================
def generate_html_report(
    report: ValidationReport,
    output_dir: str = ".",
) -> str:
    """生成单文件HTML可视化验证报告。

    零JS依赖，浏览器直接打开。采用高对比色方案
    （#D32F2F红/#388E3C绿）确保电站强光环境下可读。
    支持tooltip悬停显示详情。

    Args:
        report: 验证报告对象。
        output_dir: 输出目录路径。

    Returns:
        生成的HTML文件路径。
    """
    # 构建表格行
    rows = ""
    for c in report.checks:
        # 高对比色：通过绿#388E3C / 必须项失败红#D32F2F / 加分项警告橙#F57C00
        if c.passed:
            color = "#388E3C"
            icon = "✅"
        elif c.required:
            color = "#D32F2F"
            icon = "❌"
        else:
            color = "#F57C00"
            icon = "⚠"

        tag = "必须" if c.required else "加分"
        tooltip = c.detail if c.detail else c.threshold
        rows += (
            f"<tr>"
            f"<td style='color:{color};font-weight:bold' "
            f"title='{tooltip}'>{icon}</td>"
            f"<td title='{"不通过则整体不通过" if c.required else "影响综合评分"}'>"
            f"{tag}</td>"
            f"<td>{c.name}</td>"
            f"<td title='{tooltip}'>{c.value}</td>"
            f"<td>{c.threshold}</td>"
            f"</tr>\n"
        )

    status = "✅ 通过" if report.overall_pass else "❌ 不通过"
    status_color = "#388E3C" if report.overall_pass else "#D32F2F"

    error_section = ""
    if report.error:
        error_section = (
            f"<div style='background:#FFEBEE;border-left:4px solid #D32F2F;"
            f"padding:12px;margin:16px 0;font-size:15px'>"
            f"⚠ 错误: {report.error}</div>"
        )

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>色谱仪选型验证 - {report.host}</title>
<style>
body {{
    font-family: system-ui, -apple-system, sans-serif;
    max-width: 860px;
    margin: 2em auto;
    padding: 0 16px;
    background: #FAFAFA;
    color: #212121;
    font-size: 15px;
    line-height: 1.6;
}}
h1 {{
    font-size: 22px;
    border-bottom: 2px solid #1565C0;
    padding-bottom: 8px;
}}
.meta {{
    background: #E3F2FD;
    border-radius: 6px;
    padding: 12px 16px;
    margin: 16px 0;
}}
.meta span {{
    margin-right: 24px;
    white-space: nowrap;
}}
.result {{
    font-size: 18px;
    font-weight: bold;
    color: {status_color};
}}
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    background: #FFF;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}}
th {{
    background: #1565C0;
    color: #FFF;
    padding: 10px 12px;
    text-align: left;
    font-size: 14px;
}}
td {{
    border-bottom: 1px solid #E0E0E0;
    padding: 8px 12px;
    font-size: 14px;
}}
td[title]:hover {{
    cursor: help;
    background: #E3F2FD;
}}
tr:hover {{
    background: #F5F5F5;
}}
.footer {{
    margin-top: 24px;
    font-size: 12px;
    color: #9E9E9E;
    text-align: center;
}}
</style>
</head>
<body>
<h1>气相色谱仪选型验证报告</h1>
<div class="meta">
    <span>目标: <code>{report.host}:{report.port}</code></span>
    <span>时间: {report.timestamp}</span>
    <span class="result">结果: {status}</span>
</div>
{error_section}
<table>
<thead>
<tr><th>状态</th><th>类型</th><th>校验项</th><th>实测值</th><th>要求</th></tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
<div class="footer">
    本报告由 gc_selector_validator.py 自动生成 | 鼠标悬停单元格查看详情
</div>
</body>
</html>"""

    filename = (
        f"gc_validation_{report.host.replace('.', '_')}"
        f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    )
    filepath = Path(output_dir) / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(html, encoding="utf-8")
    return str(filepath)


# ============================================================
# CLI入口
# ============================================================
def main() -> None:
    """命令行入口函数。

    解析命令行参数，执行验证，输出四路报告
    （终端 + Markdown + JSON + HTML）。
    """
    parser = argparse.ArgumentParser(
        description="气相色谱仪Modbus TCP接口选型验证工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python gc_selector_validator.py "
            "--host 192.168.1.100\n"
            "  python gc_selector_validator.py "
            "--host 10.0.0.50 --port 5020 "
            "--output-dir reports/"
        ),
    )
    parser.add_argument(
        "--host",
        required=True,
        help="色谱仪IP地址",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=502,
        help="Modbus TCP端口（默认502）",
    )
    parser.add_argument(
        "--slave",
        type=int,
        default=1,
        help="从站地址（默认1）",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="报告输出目录（默认当前目录）",
    )
    args = parser.parse_args()

    # 执行验证
    print(f"\n正在验证色谱仪 {args.host}:{args.port} ...")
    report = validate_gc_candidate(
        args.host, args.port, args.slave
    )

    # 四路输出：终端 + Markdown + JSON + HTML
    print_terminal_report(report)

    md_path = generate_markdown_report(
        report, args.output_dir
    )
    json_path = export_json(report, args.output_dir)
    html_path = generate_html_report(
        report, args.output_dir
    )

    print(f"📄 Markdown报告: {md_path}")
    print(f"📊 JSON数据文件: {json_path}")
    print(f"🌐 HTML可视化:   {html_path}")


if __name__ == "__main__":
    main()
