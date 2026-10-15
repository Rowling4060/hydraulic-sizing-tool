"""
数据中心液冷二次侧流体管网水力计算与水泵选型工具 - 主程序入口
Data Center Liquid Cooling Secondary Loop Hydraulic Sizing & Pump Sizing Tool

运行方式:
    python main.py
    python main.py --racks 20 --power 50 --delta_t 10 --fluid WATER
    python main.py --racks 24 --power 60 --delta_t 8 --fluid PG25 --pipe_dn DN150
"""

import argparse
import os
import sys
from pathlib import Path

# 保证当前项目根路径在 sys.path 中
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from config.parameters import (
    DEFAULT_RACK_COUNT,
    DEFAULT_RACK_POWER_KW,
    DEFAULT_DELTA_T_C,
    DEFAULT_SUPPLY_TEMP_C,
    DEFAULT_RETURN_TEMP_C,
    DEFAULT_FLUID,
    CircuitLayoutConfig,
)
from core.sizing_engine import HydraulicSizingEngine, SizingSummary
from reporting.csv_exporter import export_sizing_report_csv
from reporting.visualizer import plot_system_curve


# 保证 Windows 控制台 UTF-8 编码兼容性
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def print_banner():
    """打印计算工具控制台横幅"""
    banner = r"""
========================================================================================
     数据中心液冷二次侧流体管网水力计算与水泵选型工具 v1.0
     Data Center Liquid Cooling Secondary Hydraulic Sizing Tool
========================================================================================
    """
    print(banner)


def display_console_results(summary: SizingSummary):
    """在控制台打印美观的工程选型摘要报告"""
    print("----------------------------------------------------------------------------------------")
    print("【1. 边界条件与热平衡流量 / Thermal & Flow Sizing】")
    print(f"  * 机柜配置 (IT Racks):       {summary.rack_count} 个 (单机柜: {summary.rack_power_kw:.1f} kW)")
    print(f"  * 二次侧总热负荷 (Heat Load): {summary.total_power_kw:.1f} kW ({(summary.total_power_kw/1000.0):.2f} MW)")
    print(f"  * 设计供回水温差 (Delta T):   {summary.delta_t_c:.1f} degC (供水 {summary.supply_temp_c:.1f}C / 回水 {summary.return_temp_c:.1f}C)")
    print(f"  * 循环冷却工质 (Coolant):     {summary.fluid.name}")
    print(f"    - 物性指标: 密度 rho = {summary.fluid.density:.1f} kg/m3, 比热 Cp = {summary.fluid.specific_heat:.1f} J/(kg·K), 粘度 mu = {summary.fluid.dynamic_viscosity*1000:.3f} mPa·s")
    print(f"  * 循环质量流量 (Mass Flow):   {summary.mass_flow_kg_s:.3f} kg/s")
    print(f"  * 循环总体积流量 (Total Q):   {summary.volume_flow_m3_h:.2f} m3/h  |  {summary.volume_flow_lpm:.1f} LPM (升/分钟)")
    print(f"  * 单机柜平均流量 (Rack Flow): {summary.rack_flow_lpm:.2f} LPM / 机柜")
    print("----------------------------------------------------------------------------------------")

    print("\n【2. 主供回水集管(Manifold)候选管径水力比选对比表 / Manifold Pipe Sizing Comparison】")
    header = (
        f"{'DN':<7} | {'外径x壁厚':<11} | {'内径':<8} | {'流速(m/s)':<10} | "
        f"{'雷诺数 Re':<10} | {'流态':<12} | {'沿程(kPa)':<10} | {'局部(kPa)':<10} | "
        f"{'总压降(kPa)':<11} | {'水头(m)':<8} | {'评估与选型状态'}"
    )
    print("-" * 115)
    print(header)
    print("-" * 115)

    for p in summary.pipe_evaluations:
        dim_str = f"{p.outer_dia_mm:.1f}x{p.wall_thick_mm:.1f}"
        rec_mark = " [推荐选型]" if p.is_recommended else ""
        chosen_mark = " (已选用)" if p.dn == summary.selected_pipe.dn else ""
        status_display = f"{p.status_cn}{rec_mark}{chosen_mark}"
        print(
            f"{p.dn:<7} | {dim_str:<11} | {p.inner_dia_mm:<8.1f} | {p.velocity_m_s:<10.2f} | "
            f"{p.reynolds_number:<10.0f} | {p.flow_regime:<12} | {p.dp_major_kpa:<10.2f} | {p.dp_minor_kpa:<10.2f} | "
            f"{p.dp_manifold_total_kpa:<11.2f} | {p.head_loss_m:<8.2f} | {status_display}"
        )
    print("-" * 115)

    print(f"\n【3. 系统水力阻力分解明细 (当前选定主管: {summary.selected_pipe.dn})】")
    print(f"{'管网部件名称':<35} | {'所属类别':<12} | {'阻力压降 (kPa)':<14} | {'水头 (mH2O)':<12} | {'阻力占比 (%)'}")
    print("-" * 90)
    for c in summary.component_losses:
        print(f"{c.name_cn:<35} | {c.category:<12} | {c.dp_kpa:<14.2f} | {c.head_m:<12.2f} | {c.percentage:<.1f}%")
    print("-" * 90)

    print(f"\n【4. 水泵选型核心参数输出 / Pump Duty Point & Power Specification】")
    print(f"  * 系统总水力阻力 (Total System DP):    {summary.total_dp_kpa:.2f} kPa ({summary.total_dp_bar:.3f} bar)")
    print(f"  * 水泵设计需求扬程 (Design Head H):      {summary.total_head_m:.2f} mH2O (米水柱)")
    print(f"  * 水力有效功率 (Hydraulic Power):       {summary.hydraulic_power_kw:.2f} kW (Q x DP)")
    print(f"  * 水泵轴功率需求 (Pump Shaft Power):    {summary.pump_shaft_power_kw:.2f} kW (泵水力效率 75%)")
    print(f"  * 电机输入电功率 (Motor Electric Power): {summary.motor_electric_power_kw:.2f} kW (电机效率 92%)")
    print(f"  * 管网流阻特性系数 (System R factor):   {summary.system_flow_resistance_r:.6f} kPa/(m3/h)2")
    print("----------------------------------------------------------------------------------------\n")


def main():
    parser = argparse.ArgumentParser(
        description="数据中心液冷二次侧流体管网水力计算与水泵选型工具 (Data Center Liquid Cooling Secondary Hydraulic Sizing Tool)"
    )
    parser.add_argument("--racks", type=int, default=DEFAULT_RACK_COUNT, help="机柜数量 (默认 20 个)")
    parser.add_argument("--power", type=float, default=DEFAULT_RACK_POWER_KW, help="单机柜功耗 kW (默认 50 kW)")
    parser.add_argument("--delta_t", type=float, default=DEFAULT_DELTA_T_C, help="供回水温差 ℃ (默认 10 ℃)")
    parser.add_argument(
        "--fluid",
        type=str,
        default=DEFAULT_FLUID,
        choices=["WATER", "PG25", "EG25", "water", "pg25", "eg25", "去离子水", "25%乙二醇", "25%丙二醇"],
        help="工质选择 (WATER: 去离子水, PG25: 25%丙二醇水溶液, EG25: 25%乙二醇水溶液)",
    )
    parser.add_argument("--supply_temp", type=float, default=DEFAULT_SUPPLY_TEMP_C, help="供水温度 ℃ (默认 35 ℃)")
    parser.add_argument("--pipe_dn", type=str, default=None, help="指定集管管径 (例如 DN100, DN125, DN150，留空则自动推荐最佳经济管径)")
    parser.add_argument("--csv", type=str, default="sizing_report.csv", help="输出计算书 CSV 文件名/路径 (默认: sizing_report.csv)")
    parser.add_argument("--plot", type=str, default="assets/system_curve.png", help="输出特性曲线图路径 (默认: assets/system_curve.png)")

    args = parser.parse_args()

    print_banner()

    # 初始化水力计算引擎
    engine = HydraulicSizingEngine(
        rack_count=args.racks,
        rack_power_kw=args.power,
        delta_t_c=args.delta_t,
        fluid_type=args.fluid,
        supply_temp_c=args.supply_temp,
        return_temp_c=args.supply_temp + args.delta_t,
    )

    # 执行水力求解
    summary = engine.solve(preferred_dn=args.pipe_dn)

    # 打印控制台详细报表
    display_console_results(summary)

    # 导出计算书 CSV
    csv_file = Path(args.csv)
    if not csv_file.is_absolute():
        csv_file = CURRENT_DIR / csv_file
    export_sizing_report_csv(summary, csv_file)
    print(f"✔ 选型计算书已成功生成: {csv_file}")

    # 绘制管网特性曲线图
    plot_file = Path(args.plot)
    if not plot_file.is_absolute():
        plot_file = CURRENT_DIR / plot_file
    plot_system_curve(engine, summary, plot_file)
    print(f"✔ 管网特性曲线图已成功绘制: {plot_file}\n")


if __name__ == "__main__":
    main()
