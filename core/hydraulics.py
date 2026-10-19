"""
水力计算核心模块 - Hydraulics Physics Engine Module
实现流体动力学经典方程：
1. 达西-威斯巴赫方程 (Darcy-Weisbach Equation) 计算沿程阻力损失
2. 科尔布鲁克-怀特方程 (Colebrook-White Equation) 精确迭代求解摩擦阻力系数 f
3. 局部阻力损失计算 (Minor Head Loss by Resistance Coefficient K)
4. 水头与压强双向换算 (Pressure to Head Conversion)
"""

import math
from typing import Tuple
from config.parameters import GRAVITY_ACCEL, PIPE_ROUGHNESS_M


def calc_velocity(flow_rate_m3_s: float, inner_dia_m: float) -> float:
    """
    计算圆管截面平均流速 (m/s)
    Calculate mean flow velocity inside circular pipe: v = 4*Q / (pi * D^2)

    :param flow_rate_m3_s: 体积流量 (m³/s)
    :param inner_dia_m: 管道内径 (m)
    :return: 流速 v (m/s)
    """
    if inner_dia_m <= 0.0:
        raise ValueError(f"管道内径必须大于0，当前为: {inner_dia_m}")
    area = math.pi * (inner_dia_m / 2.0) ** 2
    return flow_rate_m3_s / area


def calc_reynolds_number(density: float, velocity: float, inner_dia_m: float, dynamic_viscosity: float) -> float:
    """
    计算雷诺数 (Reynolds Number)
    Re = rho * v * D / mu

    :param density: 流体密度 (kg/m³)
    :param velocity: 流速 (m/s)
    :param inner_dia_m: 管道内径 (m)
    :param dynamic_viscosity: 动力粘度 (Pa·s)
    :return: 雷诺数 Re (无量纲)
    """
    if dynamic_viscosity <= 0.0 or inner_dia_m <= 0.0:
        return 0.0
    return (density * abs(velocity) * inner_dia_m) / dynamic_viscosity


def determine_flow_regime(reynolds: float) -> str:
    """
    判定流动状态 / Determine flow regime based on Reynolds number
    """
    if reynolds < 2300.0:
        return "层流 (Laminar)"
    elif reynolds <= 4000.0:
        return "过渡流 (Transitional)"
    else:
        return "紊流/湍流 (Turbulent)"


def calc_darcy_friction_factor(reynolds: float, inner_dia_m: float, roughness_m: float = PIPE_ROUGHNESS_M) -> float:
    """
    计算达西摩擦系数 f (Darcy-Weisbach friction factor)
    - Re <= 2300: 采用泊肃叶层流精确解 f = 64 / Re
    - Re > 4000: 采用牛顿-拉弗森法精确求解科尔布鲁克-怀特方程 (Colebrook-White equation):
        1/sqrt(f) = -2 * log10( (epsilon / (3.7 * D)) + (2.51 / (Re * sqrt(f))) )
      初值选用哈兰德显式公式 (Haaland equation)。
    - 2300 < Re <= 4000: 在层流与紊流分界处进行平滑三次样条插值。

    :param reynolds: 雷诺数
    :param inner_dia_m: 管道内径 (m)
    :param roughness_m: 管道绝对粗糙度 (m)
    :return: 达西摩擦阻力系数 f
    """
    if reynolds <= 1e-6:
        return 0.0

    # 1. 层流区 (Laminar flow, Re <= 2300)
    if reynolds <= 2300.0:
        return 64.0 / reynolds

    relative_roughness = roughness_m / inner_dia_m

    # 内部辅助函数：紊流区 Colebrook-White 迭代求解
    def _colebrook_turbulent(re: float) -> float:
        # 哈兰德公式提供极其优良的迭代初始值 (误差通常 < 1.5%)
        # Haaland initial guess
        term_h = (relative_roughness / 3.7) ** 1.11 + 6.9 / re
        inv_sqrt_f = -1.8 * math.log10(term_h)
        f_val = 1.0 / (inv_sqrt_f ** 2)

        # 牛顿-拉弗森迭代精确收敛 (Newton-Raphson refinement)
        for _ in range(20):
            sqrt_f = math.sqrt(f_val)
            arg = (relative_roughness / 3.7) + (2.51 / (re * sqrt_f))
            if arg <= 0.0:
                break
            # 残差函数: F(f) = 1/sqrt(f) + 2.0 * log10(arg)
            f_res = (1.0 / sqrt_f) + 2.0 * (math.log(arg) / math.log(10.0))

            # 导数 dF/df:
            # d(1/sqrt(f))/df = -0.5 * f^(-1.5)
            # d(2 * log10(arg))/df = (2 / ln10) * (1 / arg) * (-1.255 / (re * f^1.5))
            d_arg_df = -1.255 / (re * (f_val ** 1.5))
            df_res_df = -0.5 * (f_val ** -1.5) + (2.0 / math.log(10.0)) * (1.0 / arg) * d_arg_df

            delta_f = f_res / df_res_df
            f_val -= delta_f
            if abs(delta_f) < 1e-7:
                break
        return f_val

    # 2. 充分发展紊流区 (Turbulent flow, Re > 4000)
    if reynolds >= 4000.0:
        return _colebrook_turbulent(reynolds)

    # 3. 过渡临界区 (Transitional flow, 2300 < Re < 4000)
    # 使用三次Hermite样条平滑过渡，避免不连续跳变
    f_lam_2300 = 64.0 / 2300.0
    f_turb_4000 = _colebrook_turbulent(4000.0)
    alpha = (reynolds - 2300.0) / (4000.0 - 2300.0)
    # 平滑插值函数 S(x) = 3x^2 - 2x^3
    smooth_w = 3.0 * (alpha ** 2) - 2.0 * (alpha ** 3)
    return (1.0 - smooth_w) * f_lam_2300 + smooth_w * f_turb_4000


def calc_major_loss(
    friction_factor: float,
    length_m: float,
    inner_dia_m: float,
    density: float,
    velocity: float
) -> Tuple[float, float]:
    """
    基于达西-威斯巴赫方程计算沿程水头压降损失 (Major Head Loss)
    ΔP_major = f * (L / D) * (rho * v^2 / 2)

    :param friction_factor: 达西阻力系数 f
    :param length_m: 管长 L (m)
    :param inner_dia_m: 管内径 D (m)
    :param density: 密度 rho (kg/m³)
    :param velocity: 流速 v (m/s)
    :return: (压降 dp_kpa, 压降率 dp_per_meter_pa_m)
    """
    if inner_dia_m <= 0.0 or length_m <= 0.0:
        return 0.0, 0.0

    dynamic_pressure = 0.5 * density * (velocity ** 2)
    dp_per_meter_pa = friction_factor * (1.0 / inner_dia_m) * dynamic_pressure
    total_dp_pa = dp_per_meter_pa * length_m
    dp_kpa = total_dp_pa / 1000.0

    return dp_kpa, dp_per_meter_pa


def calc_minor_loss(k_factor: float, density: float, velocity: float) -> float:
    """
    计算局部阻力压降损失 (Minor Head Loss)
    ΔP_minor = K * (rho * v^2 / 2)

    :param k_factor: 局部阻力系数 K
    :param density: 流体密度 (kg/m³)
    :param velocity: 管内流速 (m/s)
    :return: 局部阻力压降 (kPa)
    """
    dp_pa = k_factor * 0.5 * density * (velocity ** 2)
    return dp_pa / 1000.0


def pressure_to_head_m(dp_kpa: float, density: float, g: float = GRAVITY_ACCEL) -> float:
    """
    将压降 (kPa) 转换为水柱高度扬程 (mH2O)
    H = ΔP / (rho * g)

    :param dp_kpa: 压降 (kPa)
    :param density: 流体密度 (kg/m³)
    :param g: 重力加速度 (m/s²)
    :return: 水头扬程 H (mH2O)
    """
    dp_pa = dp_kpa * 1000.0
    return dp_pa / (density * g)


def head_to_pressure_kpa(head_m: float, density: float, g: float = GRAVITY_ACCEL) -> float:
    """
    将水头扬程 (mH2O) 转换为压降 (kPa)
    ΔP = rho * g * H
    """
    dp_pa = density * g * head_m
    return dp_pa / 1000.0
