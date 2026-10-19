"""
选型计算书 CSV 导出模块 - Sizing Report CSV Exporter Module
自动生成规整、标准、包含详细中英双语物理量与工程注释的数据中心液冷水力计算书。
Generates structured sizing_report.csv with bilingual headers and standard engineering sections.
"""

import csv
from pathlib import Path
from typing import Union
from core.sizing_engine import SizingSummary


def export_sizing_report_csv(summary: SizingSummary, file_path: Union[str, Path]) -> Path:
    """
    导出水力计算选型报告至 CSV 文件 (UTF-8 with BOM 编码，兼容 Excel 打开乱码问题)

    :param summary: SizingSummary 计算结果汇总
    :param file_path: 输出 CSV 文件路径
    :return: 写入成功的文件 Path 对象
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)

        # ----------------------------------------------------------------------
        # 标题与工程基本信息 / Title & Project Metadata
        # ----------------------------------------------------------------------
        writer.writerow(["=========================================================================================="])
        writer.writerow(["数据中心液冷二次侧流体管网水力计算与水泵选型计算书"])
        writer.writerow(["Data Center Liquid Cooling Secondary Loop Hydraulic Sizing & Pump Calculation Report"])
        writer.writerow(["=========================================================================================="])
        writer.writerow([])

        # ----------------------------------------------------------------------
        # 第一部分: 设计边界条件与输入参数 / Section 1: Design Boundary Conditions
        # ----------------------------------------------------------------------
        writer.writerow(["【1. 设计边界条件与输入参数 / Design Boundary Conditions】"])
        writer.writerow(["参数物理量名称 / Parameter Name", "数值 / Value", "工程单位 / Unit", "中文说明 / Description"])
        writer.writerow(["机柜数量 (Rack Count)", summary.rack_count, "个 / Units", "二次侧服务的总IT机柜列柜数量"])
        writer.writerow(["单机柜散热功耗 (Rack Power)", f"{summary.rack_power_kw:.2f}", "kW", "单台机柜满负荷液冷散热功率"])
        writer.writerow(["系统总散热热负荷 (Total Heat Load)", f"{summary.total_power_kw:.2f}", "kW", "二次侧总散热能力需求 (P_total = N * P_rack)"])
        writer.writerow(["二次侧设计供水温度 (Supply Temp)", f"{summary.supply_temp_c:.2f}", "℃", "CDU二次侧供水温度 (W35 工况)"])
        writer.writerow(["二次侧设计回水温度 (Return Temp)", f"{summary.return_temp_c:.2f}", "℃", "服务器冷板出口总回水温度"])
        writer.writerow(["供回水设计温差 (Delta T)", f"{summary.delta_t_c:.2f}", "℃ / K", "二次侧主循环温差 ΔT = T_return - T_supply"])
        writer.writerow(["选用冷却工质 (Coolant Fluid)", summary.fluid.name, "-", f"工质代号: {summary.fluid.code}"])
        writer.writerow([])

        # ----------------------------------------------------------------------
        # 第二部分: 工质热物理性质 / Section 2: Coolant Thermophysical Properties
        # ----------------------------------------------------------------------
        writer.writerow(["【2. 工质在平均工况温度下的热物理性质 / Coolant Properties at Mean Temp】"])
        writer.writerow(["物性名称 / Property Name", "数值 / Value", "工程单位 / Unit", "物理量符号与说明 / Symbol & Notes"])
        writer.writerow(["参考计算温度 (Reference Temp)", f"{summary.fluid.temp_c:.2f}", "℃", "T_avg = (T_supply + T_return) / 2"])
        writer.writerow(["流体密度 (Density)", f"{summary.fluid.density:.2f}", "kg/m³", "ρ (用于体积流量换算与水头重力位能推导)"])
        writer.writerow(["定压比热容 (Specific Heat)", f"{summary.fluid.specific_heat:.2f}", "J/(kg·K)", "Cp (热平衡循环流量求解关键参数)"])
        writer.writerow(["动力粘度 (Dynamic Viscosity)", f"{summary.fluid.dynamic_viscosity*1000.0:.4f}", "mPa·s (cP)", "μ (雷诺数及粘性切应力阻力核心参数)"])
        writer.writerow(["运动粘度 (Kinematic Viscosity)", f"{summary.fluid.kinematic_viscosity*1e6:.4f}", "mm²/s (cSt)", "ν = μ / ρ"])
        writer.writerow(["流体导热系数 (Thermal Conductivity)", f"{summary.fluid.thermal_conductivity:.4f}", "W/(m·K)", "k (流体对流换热导热能力)"])
        writer.writerow(["普朗特数 (Prandtl Number)", f"{summary.fluid.prandtl_number:.2f}", "-", "Pr = Cp * μ / k"])
        writer.writerow([])

        # ----------------------------------------------------------------------
        # 第三部分: 二次侧循环流量计算成果 / Section 3: Loop Flow Rate Sizing
        # ----------------------------------------------------------------------
        writer.writerow(["【3. 二次侧总循环流量计算成果 / Secondary Loop Flow Rate Sizing】"])
        writer.writerow(["流量表述维度 / Flow Rate Metric", "计算数值 / Value", "工程单位 / Unit", "计算公式 / Governing Formula"])
        writer.writerow(["总质量流量 (Mass Flow Rate)", f"{summary.mass_flow_kg_s:.4f}", "kg/s", "m_dot = P_total / (Cp * ΔT)"])
        writer.writerow(["总体积流量 (Volumetric Flow m³/h)", f"{summary.volume_flow_m3_h:.2f}", "m³/h", "Q_m3h = (m_dot / ρ) * 3600"])
        writer.writerow(["总体积流量 (Volumetric Flow LPM)", f"{summary.volume_flow_lpm:.2f}", "LPM (L/min)", "Q_LPM = Q_m3s * 60,000"])
        writer.writerow(["单机柜平均流量 (Per-Rack Flow)", f"{summary.rack_flow_lpm:.2f}", "LPM / rack", "q_rack = Q_total / N_racks"])
        writer.writerow([])

        # ----------------------------------------------------------------------
        # 第四部分: 主供回水集管管径水力比选对比表 / Section 4: Manifold Sizing Comparison
        # ----------------------------------------------------------------------
        writer.writerow(["【4. 主供回水集管(Manifold)不同管径水力比选对比表 / Pipe Sizing Comparison】"])
        writer.writerow([
            "公称通径 DN",
            "英制尺寸",
            "外径 (mm)",
            "壁厚 (mm)",
            "内径 (mm)",
            "流速 (m/s)",
            "雷诺数 Re",
            "流态判定",
            "达西阻力系数 f",
            "比摩阻 (Pa/m)",
            "沿程压降 (kPa)",
            "管件局部压降 (kPa)",
            "集管总压降 (kPa)",
            "总水头损失 (mH2O)",
            "工程评估状态",
            "选型建议",
        ])
        for p in summary.pipe_evaluations:
            rec_str = "【推荐管径 / RECOMMENDED】" if p.is_recommended else "备选 / Alternative"
            writer.writerow([
                p.dn,
                p.nominal_inch,
                f"{p.outer_dia_mm:.1f}",
                f"{p.wall_thick_mm:.1f}",
                f"{p.inner_dia_mm:.1f}",
                f"{p.velocity_m_s:.2f}",
                f"{p.reynolds_number:.0f}",
                p.flow_regime,
                f"{p.friction_factor:.4f}",
                f"{p.dp_per_meter_pa_m:.1f}",
                f"{p.dp_major_kpa:.2f}",
                f"{p.dp_minor_kpa:.2f}",
                f"{p.dp_manifold_total_kpa:.2f}",
                f"{p.head_loss_m:.2f}",
                p.status_cn,
                rec_str,
            ])
        writer.writerow([])

        # ----------------------------------------------------------------------
        # 第五部分: 推荐选型系统总阻力分解明细 / Section 5: Component Pressure Losses
        # ----------------------------------------------------------------------
        writer.writerow([f"【5. 选定主集管 [{summary.selected_pipe.dn}] 时系统各部件水力阻力明细 / Component Pressure Breakdown】"])
        writer.writerow(["部件中文名称 / Component CN", "部件英文名称 / Component EN", "所属子系统 / Category", "额定压降 (kPa)", "水头损失 (mH2O)", "阻力占比 (%)"])
        for c in summary.component_losses:
            writer.writerow([
                c.name_cn,
                c.name_en,
                c.category,
                f"{c.dp_kpa:.2f}",
                f"{c.head_m:.2f}",
                f"{c.percentage:.1f}%",
            ])
        writer.writerow([])

        # ----------------------------------------------------------------------
        # 第六部分: 水泵设计扬程与功率输出 / Section 6: Pump Selection & Sizing Output
        # ----------------------------------------------------------------------
        writer.writerow(["【6. 管网总阻力与二次侧循环水泵选型指标 / Total System Head & Pump Duty Point】"])
        writer.writerow(["水泵选型参数项 / Pump Duty Parameter", "计算输出值 / Output Value", "工程单位 / Unit", "工程设计指引与安全裕量建议 / Engineering Notes"])
        writer.writerow(["二次侧系统总设计阻力 (Total System ΔP)", f"{summary.total_dp_kpa:.2f}", "kPa", "包含板换、主管、快接头、冷板的管网总损失"])
        writer.writerow(["二次侧系统总设计阻力 (Total ΔP in bar)", f"{summary.total_dp_bar:.3f}", "bar", "工程压力表直接读数参考"])
        writer.writerow(["水泵额定设计扬程 (Pump Rated Head)", f"{summary.total_head_m:.2f}", "mH2O", "H = ΔP / (ρ * g)，建议水泵选型留 10%~15% 扬程裕量"])
        writer.writerow(["流体水力有效功率 (Hydraulic Power)", f"{summary.hydraulic_power_kw:.2f}", "kW", "P_hyd = Q * ΔP"])
        writer.writerow(["水泵轴功率需求 (Pump Shaft Power)", f"{summary.pump_shaft_power_kw:.2f}", "kW", "按水泵水力效率 75% 计算 (P_shaft = P_hyd / 0.75)"])
        writer.writerow(["水泵电机输入电功率 (Motor Electric Power)", f"{summary.motor_electric_power_kw:.2f}", "kW", "按 IE4 高效电机效率 92% 计算"])
        writer.writerow(["系统流阻综合系数 (System Resistance R)", f"{summary.system_flow_resistance_r:.6f}", "kPa / (m³/h)²", "管网特性方程: ΔP(Q) = R * Q²"])
        writer.writerow([])
        writer.writerow(["--- 报告生成完毕 / End of Sizing Report ---"])

    return path
