"""
选型与系统求解引擎 - Sizing and System Solving Engine
封装数据中心二次侧水力计算的全套业务逻辑：
1. 流量求解：基于热负荷与供回水温差的热平衡方程 Q = P / (rho * Cp * ΔT)
2. 集管管径扫描对比：不同 DN 规格下的流速、雷诺数、水头压降与工程推荐评估
3. 全管网阻力汇总：板换、CDU附件、供回水主管、快接头对(QD)、机柜冷板的阻力叠加
4. 水泵选型参数推导：扬程需求 (kPa / mH2O)、水力功率及电机轴功率计算
5. 管网特性曲线 (System Resistance Characteristic Curve) 数组生成
"""

from dataclasses import dataclass, field
import math
from typing import Dict, List, Optional, Tuple

from config.parameters import (
    DEFAULT_RACK_COUNT,
    DEFAULT_RACK_POWER_KW,
    DEFAULT_DELTA_T_C,
    DEFAULT_SUPPLY_TEMP_C,
    DEFAULT_RETURN_TEMP_C,
    DEFAULT_FLUID,
    GRAVITY_ACCEL,
    PIPE_ROUGHNESS_M,
    STANDARD_PIPES,
    PipeSpec,
    CircuitLayoutConfig,
)
from core.fluid_props import FluidProperties, get_fluid_properties
from core.hydraulics import (
    calc_velocity,
    calc_reynolds_number,
    determine_flow_regime,
    calc_darcy_friction_factor,
    calc_major_loss,
    calc_minor_loss,
    pressure_to_head_m,
)


@dataclass
class PipeSizingResult:
    """单个公称通径下的水力计算评估结果 / Single Pipe Sizing Hydraulic Result"""
    dn: str                             # 公称通径 / Nominal Diameter (e.g. 'DN125')
    nominal_inch: str                   # 英制尺寸 / Nominal Inch (e.g. '5"')
    outer_dia_mm: float                 # 外径 (mm)
    wall_thick_mm: float                # 壁厚 (mm)
    inner_dia_mm: float                 # 内径 (mm)
    velocity_m_s: float                 # 流速 (m/s)
    reynolds_number: float              # 雷诺数 Re
    flow_regime: str                    # 流动状态 (层流/过渡/紊流)
    friction_factor: float              # 达西摩擦阻力系数 f
    dp_per_meter_pa_m: float            # 沿程比摩阻 (Pa/m)
    dp_major_kpa: float                 # 集管总直管沿程压降 (kPa)
    dp_minor_kpa: float                 # 集管管件局部阻力压降 (kPa)
    dp_manifold_total_kpa: float        # 集管总压降 (kPa)
    head_loss_m: float                  # 集管总水头损失 (mH2O)
    status_tag: str                     # 评估评级 (RECOMMENDED / ACCEPTABLE / OVERSIZED / HIGH_VELOCITY)
    status_cn: str                      # 中文评估结论
    is_recommended: bool                # 是否推荐选型


@dataclass
class ComponentPressureLoss:
    """各管网部件水力阻力分解结构 / Component Pressure Drop Breakdown"""
    name_cn: str                        # 部件中文名称
    name_en: str                        # 部件英文名称
    category: str                       # 部件类别 (CDU / Distribution / Rack)
    dp_kpa: float                       # 额定工况阻力 (kPa)
    head_m: float                       # 额定工况水头 (mH2O)
    percentage: float                   # 占总系统阻力百分比 (%)


@dataclass
class SizingSummary:
    """液冷二次侧系统总体选型求解成果 / Overall Secondary Loop Sizing Summary"""
    # 1. 基础工况输入 / Boundary Conditions
    rack_count: int                     # 机柜数量 (台)
    rack_power_kw: float                # 单机柜功率 (kW)
    total_power_kw: float               # 总散热负荷 (kW)
    delta_t_c: float                    # 供回水温差 (℃)
    supply_temp_c: float                # 供水温度 (℃)
    return_temp_c: float                # 回水温度 (℃)
    fluid: FluidProperties              # 流体工质热物性

    # 2. 流量求解 / Flow Rate Sizing
    mass_flow_kg_s: float               # 质量流量 (kg/s)
    volume_flow_m3_s: float             # 体积流量 (m³/s)
    volume_flow_m3_h: float             # 体积流量 (m³/h)
    volume_flow_lpm: float              # 体积流量 (LPM, 升/分钟)
    rack_flow_lpm: float                # 单机柜平均流量 (LPM)

    # 3. 集管比选结果列表 / Pipe Sizing Evaluation List
    pipe_evaluations: List[PipeSizingResult] = field(default_factory=list)
    selected_pipe: Optional[PipeSizingResult] = None

    # 4. 系统各部件阻力拆解 / Component Breakdown
    component_losses: List[ComponentPressureLoss] = field(default_factory=list)

    # 5. 系统总阻力与水泵参数 / System Total Resistance & Pump Requirements
    total_dp_kpa: float = 0.0           # 管网总阻力 (kPa)
    total_dp_bar: float = 0.0           # 管网总阻力 (bar)
    total_head_m: float = 0.0           # 水泵总设计扬程 (mH2O)
    hydraulic_power_kw: float = 0.0     # 水力有效功率 (kW)
    pump_shaft_power_kw: float = 0.0    # 水泵轴功率 (kW, 考虑水力效率)
    motor_electric_power_kw: float = 0.0# 电机输入电功率 (kW, 考虑电机效率)
    system_flow_resistance_r: float = 0.0 # 系统流阻系数 R = ΔP / Q^2 (kPa / (m³/h)^2)


class HydraulicSizingEngine:
    """
    数据中心液冷二次侧水力计算与水泵选型引擎
    Hydraulic Sizing Engine for Data Center Liquid Cooling Secondary Circuit
    """

    def __init__(
        self,
        rack_count: int = DEFAULT_RACK_COUNT,
        rack_power_kw: float = DEFAULT_RACK_POWER_KW,
        delta_t_c: float = DEFAULT_DELTA_T_C,
        fluid_type: str = DEFAULT_FLUID,
        supply_temp_c: float = DEFAULT_SUPPLY_TEMP_C,
        return_temp_c: float = DEFAULT_RETURN_TEMP_C,
        layout_config: Optional[CircuitLayoutConfig] = None,
        pipe_roughness_m: float = PIPE_ROUGHNESS_M,
    ):
        self.rack_count = int(rack_count)
        self.rack_power_kw = float(rack_power_kw)
        self.delta_t_c = float(delta_t_c)
        self.supply_temp_c = float(supply_temp_c)
        self.return_temp_c = float(return_temp_c)
        self.avg_temp_c = (self.supply_temp_c + self.return_temp_c) / 2.0
        self.fluid_type = fluid_type
        self.fluid = get_fluid_properties(fluid_type, self.avg_temp_c)
        self.layout = layout_config or CircuitLayoutConfig()
        self.roughness_m = pipe_roughness_m

    def solve(self, preferred_dn: Optional[str] = None) -> SizingSummary:
        """
        执行完整水力求解计算流程
        Execute full hydraulic solving workflow
        """
        # Step 1: 总热负荷计算 / Total Thermal Power
        total_power_kw = self.rack_count * self.rack_power_kw
        total_power_w = total_power_kw * 1000.0

        # Step 2: 热平衡求解循环流量 / Flow rate by thermal energy conservation
        # P = m_dot * Cp * ΔT  =>  m_dot = P / (Cp * ΔT)
        delta_t = max(self.delta_t_c, 0.1)
        mass_flow_kg_s = total_power_w / (self.fluid.specific_heat * delta_t)
        volume_flow_m3_s = mass_flow_kg_s / self.fluid.density
        volume_flow_m3_h = volume_flow_m3_s * 3600.0
        volume_flow_lpm = volume_flow_m3_s * 60000.0
        rack_flow_lpm = volume_flow_lpm / max(self.rack_count, 1)

        # Step 3: 扫描所有标准管径，评估流速与沿程/局部阻力
        # Evaluate standard pipe diameters for main distribution manifold
        pipe_evaluations: List[PipeSizingResult] = []
        best_recommended_dn: Optional[str] = None
        min_abs_velocity_diff = 999.0

        # 主管等效局部阻力总系数 (弯头 + 阀门 + 流量计 + 三通)
        total_manifold_k = (
            self.layout.manifold_elbows_count * self.layout.elbow_k_factor
            + self.layout.manifold_valves_count * self.layout.valve_k_factor
            + self.layout.manifold_flowmeter_k
            + self.layout.manifold_tee_k
        )

        for dn, spec in STANDARD_PIPES.items():
            # 计算截面流速 v (m/s)
            v = calc_velocity(volume_flow_m3_s, spec.inner_dia_m)
            # 计算雷诺数 Re
            re = calc_reynolds_number(self.fluid.density, v, spec.inner_dia_m, self.fluid.dynamic_viscosity)
            regime = determine_flow_regime(re)
            # 达西摩擦阻力系数 f
            f = calc_darcy_friction_factor(re, spec.inner_dia_m, self.roughness_m)
            # 沿程水头损失 (供回水主管总长)
            dp_major_kpa, dp_per_m_pa = calc_major_loss(
                f, self.layout.manifold_length_m, spec.inner_dia_m, self.fluid.density, v
            )
            # 主管附件局部阻力损失
            dp_minor_kpa = calc_minor_loss(total_manifold_k, self.fluid.density, v)
            dp_manifold_total = dp_major_kpa + dp_minor_kpa
            head_loss_m = pressure_to_head_m(dp_manifold_total, self.fluid.density)

            # 流速评估准则 (依据 ASHRAE TC 9.9 & OCP 液冷规范，经济推荐流速 1.2 ~ 2.0 m/s)
            if v > 2.5:
                tag = "HIGH_VELOCITY"
                cn_desc = "流速超标 (>2.5m/s)，存在剧烈冲刷腐蚀与水锤噪音风险"
                is_rec = False
            elif v > 2.0:
                tag = "ACCEPTABLE_HIGH"
                cn_desc = "流速偏高 (2.0~2.5m/s)，阻力偏大，可按特殊限径场景采用"
                is_rec = False
            elif 1.2 <= v <= 2.0:
                tag = "RECOMMENDED"
                cn_desc = "推荐流速区间 (1.2~2.0m/s)，阻力与管材投资最佳平衡点"
                is_rec = True
            elif 0.8 <= v < 1.2:
                tag = "ACCEPTABLE_LOW"
                cn_desc = "流速偏低 (0.8~1.2m/s)，水阻极低但管径偏大增加投资"
                is_rec = False
            else:
                tag = "OVERSIZED"
                cn_desc = "管径严重过大 (<0.8m/s)，初投资过高且微气泡不易带走"
                is_rec = False

            # 寻找最接近 1.6 m/s 黄金经济流速的标准管径
            target_v = 1.60
            if abs(v - target_v) < min_abs_velocity_diff:
                min_abs_velocity_diff = abs(v - target_v)
                best_recommended_dn = dn

            eval_res = PipeSizingResult(
                dn=dn,
                nominal_inch=spec.nominal_inch,
                outer_dia_mm=spec.outer_dia_mm,
                wall_thick_mm=spec.wall_thick_mm,
                inner_dia_mm=spec.inner_dia_mm,
                velocity_m_s=v,
                reynolds_number=re,
                flow_regime=regime,
                friction_factor=f,
                dp_per_meter_pa_m=dp_per_m_pa,
                dp_major_kpa=dp_major_kpa,
                dp_minor_kpa=dp_minor_kpa,
                dp_manifold_total_kpa=dp_manifold_total,
                head_loss_m=head_loss_m,
                status_tag=tag,
                status_cn=cn_desc,
                is_recommended=is_rec,
            )
            pipe_evaluations.append(eval_res)

        # 确定选定管径：若用户未指定，则选用最佳推荐管径
        chosen_dn = preferred_dn if preferred_dn in STANDARD_PIPES else best_recommended_dn
        selected_pipe = next((p for p in pipe_evaluations if p.dn == chosen_dn), pipe_evaluations[0])

        # Step 4: 细化全管网压力损失分解 (Component Breakdown)
        # 板换阻力 (CDU Secondary Heat Exchanger)
        dp_phex = self.layout.phex_rated_dp_kpa
        # CDU 内部管阀与过滤器 (CDU Internal Strainer & Valves)
        dp_cdu_int = self.layout.cdu_internal_dp_kpa
        # 主供回水管直管沿程阻力 (Main Manifold Friction Loss)
        dp_manifold_major = selected_pipe.dp_major_kpa
        # 主供回水管管件局部阻力 (Main Manifold Fittings & Valves)
        dp_manifold_minor = selected_pipe.dp_minor_kpa
        # 机柜进出快接头对阻力 (Quick Disconnect Couplings per Rack)
        dp_qd = self.layout.qd_pair_rated_dp_kpa
        # 机柜内部集管与服务器冷板总阻力 (Rack Cold Plates & Internal RDM)
        dp_coldplates = self.layout.rack_coldplates_dp_kpa
        # 机柜支管平衡阀与软管 (Branch Hose & Balancing Valve)
        dp_branch_valve = self.layout.rack_branch_valve_dp_kpa

        # 20 个机柜并联回路阻力取单支最不利机柜阻力:
        # ΔP_rack_branch = ΔP_QD + ΔP_coldplates + ΔP_branch_valve
        dp_rack_branch_total = dp_qd + dp_coldplates + dp_branch_valve

        # 系统管网总压降:
        # ΔP_total = ΔP_phex + ΔP_cdu_int + ΔP_manifold_major + ΔP_manifold_minor + ΔP_rack_branch_total
        total_dp_kpa = dp_phex + dp_cdu_int + dp_manifold_major + dp_manifold_minor + dp_rack_branch_total
        total_dp_bar = total_dp_kpa / 100.0
        total_head_m = pressure_to_head_m(total_dp_kpa, self.fluid.density)

        # 构建各部件损耗明细
        raw_components = [
            ("板式换热器二次侧阻力", "Plate Heat Exchanger (PHE)", "CDU", dp_phex),
            ("CDU内部附件(过滤器/止回阀/内管)", "CDU Internal Piping & Strainer", "CDU", dp_cdu_int),
            (f"供回水主管沿程阻力 ({selected_pipe.dn})", f"Main Manifold Major Loss ({selected_pipe.dn})", "Distribution", dp_manifold_major),
            (f"供回水主管管件局部阻力", f"Main Manifold Fittings Minor Loss", "Distribution", dp_manifold_minor),
            ("机柜级快接头对阻力 (进水QD+回水QD)", "Quick Disconnects (Supply+Return QD)", "Rack Branch", dp_qd),
            ("机柜内服务器冷板及分配管阻力", "Server Cold Plates & Chassis RDM", "Rack Branch", dp_coldplates),
            ("机柜支路平衡调节阀与软管", "Rack Branch Valve & Flexible Hose", "Rack Branch", dp_branch_valve),
        ]

        component_losses = [
            ComponentPressureLoss(
                name_cn=cn,
                name_en=en,
                category=cat,
                dp_kpa=dp,
                head_m=pressure_to_head_m(dp, self.fluid.density),
                percentage=(dp / total_dp_kpa) * 100.0 if total_dp_kpa > 0 else 0.0,
            )
            for cn, en, cat, dp in raw_components
        ]

        # Step 5: 水泵与电机功率推导
        # 水力有效功率: P_hyd (kW) = Q (m³/s) * ΔP (kPa)
        hydraulic_power_kw = volume_flow_m3_s * total_dp_kpa
        pump_shaft_power_kw = hydraulic_power_kw / max(self.layout.pump_hydraulic_efficiency, 0.1)
        motor_electric_power_kw = pump_shaft_power_kw / max(self.layout.motor_efficiency, 0.1)

        # 系统流阻特性常数: R_sys = ΔP / (Q^2) [kPa / (m³/h)^2]
        system_r = total_dp_kpa / (volume_flow_m3_h ** 2) if volume_flow_m3_h > 0 else 0.0

        return SizingSummary(
            rack_count=self.rack_count,
            rack_power_kw=self.rack_power_kw,
            total_power_kw=total_power_kw,
            delta_t_c=self.delta_t_c,
            supply_temp_c=self.supply_temp_c,
            return_temp_c=self.return_temp_c,
            fluid=self.fluid,
            mass_flow_kg_s=mass_flow_kg_s,
            volume_flow_m3_s=volume_flow_m3_s,
            volume_flow_m3_h=volume_flow_m3_h,
            volume_flow_lpm=volume_flow_lpm,
            rack_flow_lpm=rack_flow_lpm,
            pipe_evaluations=pipe_evaluations,
            selected_pipe=selected_pipe,
            component_losses=component_losses,
            total_dp_kpa=total_dp_kpa,
            total_dp_bar=total_dp_bar,
            total_head_m=total_head_m,
            hydraulic_power_kw=hydraulic_power_kw,
            pump_shaft_power_kw=pump_shaft_power_kw,
            motor_electric_power_kw=motor_electric_power_kw,
            system_flow_resistance_r=system_r,
        )

    def generate_system_curve(
        self,
        summary: SizingSummary,
        num_points: int = 50,
        flow_range_factor: Tuple[float, float] = (0.2, 1.5),
    ) -> Dict[str, List[float]]:
        """
        生成管网特性阻力曲线数据 (Q vs ΔP / Head)
        Generates system resistance curve points across flow range [0.2*Q_0, 1.5*Q_0].

        :param summary: 计算汇总对象
        :param num_points: 采样点数
        :param flow_range_factor: 流量范围比例 (最小比例, 最大比例)
        :return: 包含流量、总阻力、总扬程与各部件分项阻力的字典列表
        """
        q_rated_m3h = summary.volume_flow_m3_h
        min_factor, max_factor = flow_range_factor
        step = (max_factor - min_factor) / (num_points - 1)

        q_m3h_list = []
        q_lpm_list = []
        dp_total_kpa_list = []
        head_total_m_list = []
        dp_phex_kpa_list = []
        dp_manifold_kpa_list = []
        dp_rack_branch_kpa_list = []

        # 选定管径规格
        pipe_spec = STANDARD_PIPES[summary.selected_pipe.dn]
        total_manifold_k = (
            self.layout.manifold_elbows_count * self.layout.elbow_k_factor
            + self.layout.manifold_valves_count * self.layout.valve_k_factor
            + self.layout.manifold_flowmeter_k
            + self.layout.manifold_tee_k
        )

        for i in range(num_points):
            factor = min_factor + i * step
            q_m3h = q_rated_m3h * factor
            q_m3s = q_m3h / 3600.0
            q_lpm = q_m3s * 60000.0

            # 1. 板换与CDU内部阻力 (近似与流速平方成正比)
            dp_phex = summary.component_losses[0].dp_kpa * (factor ** 2)
            dp_cdu = summary.component_losses[1].dp_kpa * (factor ** 2)

            # 2. 供回水主管阻力 (严格基于 Darcy-Weisbach 随 Re 动态变化)
            v = calc_velocity(q_m3s, pipe_spec.inner_dia_m)
            re = calc_reynolds_number(self.fluid.density, v, pipe_spec.inner_dia_m, self.fluid.dynamic_viscosity)
            f = calc_darcy_friction_factor(re, pipe_spec.inner_dia_m, self.roughness_m)
            dp_major, _ = calc_major_loss(f, self.layout.manifold_length_m, pipe_spec.inner_dia_m, self.fluid.density, v)
            dp_minor = calc_minor_loss(total_manifold_k, self.fluid.density, v)
            dp_manifold = dp_major + dp_minor

            # 3. 机柜支路阻力 (快接头 + 冷板 + 平衡阀)
            # 支路流量与总流量等比例增减
            dp_qd = self.layout.qd_pair_rated_dp_kpa * (factor ** 2)
            dp_coldplates = self.layout.rack_coldplates_dp_kpa * (factor ** 2)
            dp_branch_valve = self.layout.rack_branch_valve_dp_kpa * (factor ** 2)
            dp_rack = dp_qd + dp_coldplates + dp_branch_valve

            # 总压降与总扬程
            dp_total = dp_phex + dp_cdu + dp_manifold + dp_rack
            head_total = pressure_to_head_m(dp_total, self.fluid.density)

            q_m3h_list.append(q_m3h)
            q_lpm_list.append(q_lpm)
            dp_total_kpa_list.append(dp_total)
            head_total_m_list.append(head_total)
            dp_phex_kpa_list.append(dp_phex + dp_cdu)
            dp_manifold_kpa_list.append(dp_manifold)
            dp_rack_branch_kpa_list.append(dp_rack)

        return {
            'q_m3h': q_m3h_list,
            'q_lpm': q_lpm_list,
            'dp_total_kpa': dp_total_kpa_list,
            'head_total_m': head_total_m_list,
            'dp_phex_kpa': dp_phex_kpa_list,
            'dp_manifold_kpa': dp_manifold_kpa_list,
            'dp_rack_branch_kpa': dp_rack_branch_kpa_list,
        }
