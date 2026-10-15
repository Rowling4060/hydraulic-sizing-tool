"""
管网水力特性与水泵选型曲线绘制模块 - Hydraulic & Pump Curve Visualizer Module
使用 Matplotlib 绘制高精度工程级 "管网阻力曲线 vs 水泵扬程特性曲线" (assets/system_curve.png)。
Plots System Resistance Curve, Pump Performance Curve (100% & 80% VFD), and Component Breakdowns.
"""

from pathlib import Path
from typing import Union
import matplotlib
matplotlib.use('Agg')  # 无头模式生成图像 / Headless mode
import matplotlib.pyplot as plt
import numpy as np

from core.sizing_engine import HydraulicSizingEngine, SizingSummary


def setup_chinese_fonts():
    """配置 Matplotlib 支持清晰中文字符与负号正常显示"""
    font_candidates = [
        'Microsoft YaHei',
        'SimHei',
        'DengXian',
        'SimSun',
        'DejaVu Sans',
        'sans-serif',
    ]
    plt.rcParams['font.sans-serif'] = font_candidates
    plt.rcParams['axes.unicode_minus'] = False  # 避免负号乱码
    plt.rcParams['font.size'] = 10.0


def plot_system_curve(
    engine: HydraulicSizingEngine,
    summary: SizingSummary,
    output_image_path: Union[str, Path] = "assets/system_curve.png",
) -> Path:
    """
    绘制管网水力特性与水泵选型工作曲线并保存至指定路径

    :param engine: 水力计算引擎实例
    :param summary: 计算汇总结果
    :param output_image_path: 图片保存路径 (PNG)
    :return: Path 对象
    """
    setup_chinese_fonts()
    out_path = Path(output_image_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. 采集阻力曲线数据点 (覆盖 0 ~ 140% 额定流量)
    curve_data = engine.generate_system_curve(summary, num_points=70, flow_range_factor=(0.05, 1.40))
    q_m3h = np.array(curve_data['q_m3h'])
    dp_total = np.array(curve_data['dp_total_kpa'])
    dp_phex = np.array(curve_data['dp_phex_kpa'])
    dp_manifold = np.array(curve_data['dp_manifold_kpa'])
    dp_rack = np.array(curve_data['dp_rack_branch_kpa'])

    # 额定设计工况点
    q_duty_m3h = summary.volume_flow_m3_h
    dp_duty_kpa = summary.total_dp_kpa
    head_duty_m = summary.total_head_m

    # 2. 模拟选型离心水泵特性曲线 (H-Q / ΔP-Q 曲线)
    # 离心泵关死点压强约为额定压头的 1.28 ~ 1.32 倍
    dp_shutoff = 1.30 * dp_duty_kpa
    # 额定转速 (100% RPM) 泵特性曲线: ΔP_pump = ΔP_shutoff - A * Q^2
    a_pump = (dp_shutoff - dp_duty_kpa) / (q_duty_m3h ** 2)
    dp_pump_100 = np.clip(dp_shutoff - a_pump * (q_m3h ** 2), 0, None)

    # 变频 80% 转速泵曲线 (依照水泵比例相似定律 Affinity Laws: Q ∝ n, ΔP ∝ n^2)
    speed_ratio = 0.82
    dp_shutoff_vfd = dp_shutoff * (speed_ratio ** 2)
    dp_pump_vfd = np.clip(dp_shutoff_vfd - a_pump * (q_m3h ** 2), 0, None)

    # 3. 创建画布并严密分配间距 (杜绝顶部坐标轴与大标题重合)
    fig, ax1 = plt.subplots(figsize=(12.2, 7.8), dpi=300)
    fig.subplots_adjust(top=0.79, bottom=0.10, left=0.09, right=0.91)

    # ---------------- 曲线绘制 ----------------
    # 系统总阻力曲线
    line_total, = ax1.plot(
        q_m3h, dp_total,
        color='#0D47A1', linewidth=3.2,
        label='管网总阻力特性曲线 (System Resistance: ΔP = R·Q²)',
        zorder=6
    )

    # 水泵特性曲线 (100% 额定转速)
    line_pump, = ax1.plot(
        q_m3h, dp_pump_100,
        color='#B71C1C', linewidth=2.4, linestyle='-',
        label='水泵扬程特性曲线 (Rated Pump Curve @100% RPM)',
        zorder=5
    )

    # 水泵变频特性曲线 (82% 调速)
    line_pump_vfd, = ax1.plot(
        q_m3h, dp_pump_vfd,
        color='#E53935', linewidth=1.6, linestyle='-.',
        label='水泵变频调速曲线 (VFD Pump Curve @82% RPM)',
        alpha=0.85, zorder=4
    )

    # 各分项阻力曲线 (虚线)
    line_rack, = ax1.plot(
        q_m3h, dp_rack,
        color='#E65100', linewidth=1.7, linestyle='--',
        label='机柜冷板+快接头支路 (Rack Branch: Cold Plates + QDs)',
        alpha=0.9, zorder=3
    )
    line_phex, = ax1.plot(
        q_m3h, dp_phex,
        color='#2E7D32', linewidth=1.7, linestyle=':',
        label='板换+CDU内部附件 (PHE & CDU Internals)',
        alpha=0.85, zorder=3
    )
    line_pipe, = ax1.plot(
        q_m3h, dp_manifold,
        color='#6A1B9A', linewidth=1.7, linestyle='-.',
        label=f'供回水主管管阻 ({summary.selected_pipe.dn} Manifold)',
        alpha=0.8, zorder=3
    )

    # 填充半透明层次色彩
    ax1.fill_between(q_m3h, 0, dp_rack, color='#FFE0B2', alpha=0.22)
    ax1.fill_between(q_m3h, dp_rack, dp_rack + dp_phex, color='#C8E6C9', alpha=0.20)
    ax1.fill_between(q_m3h, dp_rack + dp_phex, dp_total, color='#E1BEE7', alpha=0.18)

    # 标出额定设计工况点 (Operating Duty Point)
    duty_point = ax1.scatter(
        [q_duty_m3h], [dp_duty_kpa],
        color='#D50000', s=160, marker='D', edgecolors='#212121', linewidth=1.8,
        zorder=10, label='额定设计工况工作点 (Design Duty Point)'
    )

    # 绘制十字参考线
    ax1.axvline(x=q_duty_m3h, color='#C62828', linestyle=':', linewidth=1.3, alpha=0.7)
    ax1.axhline(y=dp_duty_kpa, color='#C62828', linestyle=':', linewidth=1.3, alpha=0.7)

    # 设计工况信息浮动文字标注框 (Callout Box)
    annotation_text = (
        f"★ 额定设计工况点 (Design Duty Point)\n"
        f"  • 总散热负荷: {summary.total_power_kw:.0f} kW ({summary.rack_count}机柜 × {summary.rack_power_kw:.0f}kW)\n"
        f"  • 循环工质: {summary.fluid.code} (供回水ΔT = {summary.delta_t_c:.1f}℃)\n"
        f"  • 额定流量 Q: {q_duty_m3h:.2f} m³/h ({summary.volume_flow_lpm:.1f} LPM)\n"
        f"  • 选定管径: {summary.selected_pipe.dn} (流速 v = {summary.selected_pipe.velocity_m_s:.2f} m/s)\n"
        f"  • 系统总阻力 ΔP: {dp_duty_kpa:.1f} kPa ({summary.total_dp_bar:.2f} bar)\n"
        f"  • 水泵需求扬程 H: {head_duty_m:.2f} mH2O\n"
        f"  • 水力有效功率: {summary.hydraulic_power_kw:.2f} kW\n"
        f"  • 电机推荐输入电功率: {summary.motor_electric_power_kw:.2f} kW"
    )

    # 放置在左上方空白区 (位于水泵关闭点压头上方，完全避开所有曲线)
    box_x = q_m3h[-1] * 0.05
    box_y = max(dp_duty_kpa * 1.50, dp_shutoff * 1.12)
    ax1.annotate(
        annotation_text,
        xy=(q_duty_m3h, dp_duty_kpa),
        xytext=(box_x, box_y),
        bbox=dict(boxstyle="round,pad=0.7", facecolor="#FFFDE7", edgecolor="#FBC02D", alpha=0.96, lw=1.5),
        arrowprops=dict(
            arrowstyle="->", connectionstyle="arc3,rad=-0.16",
            color="#D50000", lw=2.0
        ),
        fontsize=9.2,
        color="#212121",
        linespacing=1.42,
    )

    # 坐标轴限制与刻度设置
    y_max = max(dp_total[-1], dp_shutoff) * 1.15
    ax1.set_xlim(left=0, right=q_m3h[-1] * 1.02)
    ax1.set_ylim(bottom=0, top=y_max)
    ax1.set_xlabel('二次侧循环流量 / Flow Rate  Q (m³/h)', fontsize=11.5, fontweight='bold', labelpad=8)
    ax1.set_ylabel('系统总水力阻力压降 / Pressure Drop  ΔP (kPa)', fontsize=11.5, fontweight='bold', color='#0D47A1', labelpad=8)
    ax1.tick_params(axis='y', labelcolor='#0D47A1')
    ax1.grid(True, which='major', linestyle='--', linewidth=0.6, alpha=0.55)
    ax1.grid(True, which='minor', linestyle=':', linewidth=0.35, alpha=0.3)
    ax1.minorticks_on()

    # 右 Y 轴：转换为水头扬程 (Head in mH2O)
    ax2 = ax1.twinx()
    head_max = y_max * 1000.0 / (summary.fluid.density * 9.80665)
    ax2.set_ylim(bottom=0, top=head_max)
    ax2.set_ylabel('水泵水力扬程 / Pump Dynamic Head  H (mH2O)', fontsize=11.5, fontweight='bold', color='#B71C1C', labelpad=8)
    ax2.tick_params(axis='y', labelcolor='#B71C1C')

    # 顶部副 X 轴 (流量单位 LPM 换算)
    ax_top = ax1.secondary_xaxis('top', functions=(lambda x: x * 1000.0 / 60.0, lambda x: x * 60.0 / 1000.0))
    ax_top.set_xlabel('循环流量 / Flow Rate  Q (LPM / L/min)', fontsize=10.0, color='#37474F', labelpad=6)
    ax_top.tick_params(axis='x', labelcolor='#37474F', pad=3)

    # 顶部大标题与工程副标题 (suptitle 位于最上方，间距宽裕)
    fig.suptitle(
        "数据中心液冷二次侧流体管网水力特性与水泵选型匹配曲线\n"
        "Data Center Liquid Cooling Secondary Hydraulic Sizing & Pump Operating Curve",
        fontsize=13.0, fontweight='bold', y=0.965
    )

    # 图例
    lines = [line_total, line_pump, line_pump_vfd, line_rack, line_phex, line_pipe, duty_point]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='lower right', frameon=True, framealpha=0.94, facecolor='#FAFAFA', edgecolor='#BDBDBD', fontsize=8.8)

    # 保存高精度图像
    fig.savefig(out_path, dpi=300)
    plt.close(fig)

    return out_path
