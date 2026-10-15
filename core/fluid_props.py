"""
工质热物性计算模块 - Coolant Thermophysical Properties Module
提供去离子水 (Deionized Water)、25%丙二醇水溶液 (PG25)、25%乙二醇水溶液 (EG25) 的精确温度相关物性计算。
Provides temperature-dependent physical properties: Density, Specific Heat Capacity, Dynamic Viscosity.
遵循 ASHRAE Fundamentals 及国际标准水物性 (IAPWS / Tanaka 经验公式)。
"""

from dataclasses import dataclass
import math
from typing import Dict, Union


@dataclass
class FluidProperties:
    """工质热物理特性结构 / Fluid Thermophysical Properties Data Class"""
    name: str                       # 工质中文全称 / Chinese Name
    code: str                       # 简写标识码 / Code Identifier
    temp_c: float                   # 物性计算温度 (degC) / Reference Temperature
    density: float                  # 密度 (kg/m3) / Fluid Density (rho)
    specific_heat: float            # 比定压热容 (J/(kg·K)) / Specific Heat Capacity (Cp)
    dynamic_viscosity: float        # 动力粘度 (Pa·s) / Dynamic Viscosity (mu)
    kinematic_viscosity: float      # 运动粘度 (m2/s) / Kinematic Viscosity (nu = mu/rho)
    prandtl_number: float           # 普朗特数 (Pr) / Prandtl Number
    thermal_conductivity: float     # 导热系数 (W/(m·K)) / Thermal Conductivity (k)

    def __repr__(self) -> str:
        return (
            f"<FluidProperties {self.code} at {self.temp_c:.1f}C: "
            f"rho={self.density:.1f} kg/m3, "
            f"Cp={self.specific_heat:.1f} J/(kg·K), "
            f"mu={self.dynamic_viscosity*1000:.3f} mPa·s>"
        )


def get_water_properties(temp_c: float = 40.0) -> FluidProperties:
    """
    计算去离子水在指定温度下的热物理性质 (Tanaka 标准水密度公式与 IAPWS-IF97 物性拟合)
    Calculate Deionized Water properties based on standard empirical formulations.

    :param temp_c: 流体温度 (degC) / Fluid Temperature (0C ~ 100C)
    :return: FluidProperties 实例
    """
    t = float(temp_c)

    # 1. 密度 rho (kg/m3) - Tanaka et al. 精确公式
    # At 20C ~ 998.2 kg/m3, at 40C ~ 992.2 kg/m3
    rho = 999.84 * (1.0 - (((t - 3.98) ** 2) * (t + 283.0)) / (508929.0 * (t + 68.12)))

    # 2. 定压比热容 Cp (J/(kg·K))
    # At 20C ~ 4182 J/(kg·K), at 40C ~ 4178 J/(kg·K)
    cp = 4217.4 - 3.720283 * t + 0.1412855 * (t ** 2) \
         - 2.654387e-3 * (t ** 3) + 2.09186e-5 * (t ** 4)

    # 3. 动力粘度 mu (Pa·s) - Vogel-Fulcher-Tammann 公式
    # At 20C ~ 1.002 mPa·s, at 40C ~ 0.651 mPa·s
    mu = 2.414e-5 * (10.0 ** (247.8 / (t + 273.15 - 140.0)))

    # 4. 导热系数 k (W/(m·K))
    k = 0.56112 + 0.00193 * t - 8.1e-6 * (t ** 2)

    nu = mu / rho
    pr = (cp * mu) / k

    return FluidProperties(
        name="去离子水 (Deionized Water)",
        code="WATER",
        temp_c=t,
        density=rho,
        specific_heat=cp,
        dynamic_viscosity=mu,
        kinematic_viscosity=nu,
        prandtl_number=pr,
        thermal_conductivity=k,
    )


def get_pg25_properties(temp_c: float = 40.0) -> FluidProperties:
    """
    计算25%质量分数丙二醇水溶液 (PG25) 在指定温度下的热物理性质 (依据 ASHRAE Fundamentals 数据表)
    Calculate 25 wt% Propylene Glycol aqueous solution properties.

    :param temp_c: 流体温度 (degC) / Fluid Temperature (10C ~ 80C)
    :return: FluidProperties 实例
    """
    t = float(temp_c)

    # 1. 密度 rho (kg/m3) - 25 wt% PG
    # At 20C ~ 1030 kg/m3, at 40C ~ 1022 kg/m3
    rho = 1038.5 - 0.385 * t - 0.0012 * (t ** 2)

    # 2. 定压比热容 Cp (J/(kg·K))
    # At 20C ~ 3930 J/(kg·K), at 40C ~ 3985 J/(kg·K)
    cp = 3875.0 + 2.75 * t

    # 3. 动力粘度 mu (Pa·s) - Andrade 方程精准拟合
    # At 20C ~ 2.85 mPa·s, at 40C ~ 1.68 mPa·s, at 60C ~ 1.06 mPa·s
    mu = 7.245e-7 * math.exp(2426.5 / (t + 273.15))

    # 4. 导热系数 k (W/(m·K))
    k = 0.470 + 0.0012 * t - 3.5e-6 * (t ** 2)

    nu = mu / rho
    pr = (cp * mu) / k

    return FluidProperties(
        name="25%丙二醇水溶液 (PG25 - Propylene Glycol 25%)",
        code="PG25",
        temp_c=t,
        density=rho,
        specific_heat=cp,
        dynamic_viscosity=mu,
        kinematic_viscosity=nu,
        prandtl_number=pr,
        thermal_conductivity=k,
    )


def get_eg25_properties(temp_c: float = 40.0) -> FluidProperties:
    """
    计算25%质量分数乙二醇水溶液 (EG25) 在指定温度下的热物理性质 (依据 ASHRAE Fundamentals 数据表)
    Calculate 25 wt% Ethylene Glycol aqueous solution properties.

    :param temp_c: 流体温度 (degC) / Fluid Temperature (10C ~ 80C)
    :return: FluidProperties 实例
    """
    t = float(temp_c)

    # 1. 密度 rho (kg/m3) - 25 wt% EG
    # At 20C ~ 1040 kg/m3, at 40C ~ 1031 kg/m3
    rho = 1047.8 - 0.370 * t - 0.0010 * (t ** 2)

    # 2. 定压比热容 Cp (J/(kg·K))
    # At 20C ~ 3860 J/(kg·K), at 40C ~ 3920 J/(kg·K)
    cp = 3800.0 + 3.00 * t

    # 3. 动力粘度 mu (Pa·s) - Andrade 方程精准拟合
    # At 20C ~ 2.10 mPa·s, at 40C ~ 1.35 mPa·s, at 60C ~ 0.92 mPa·s
    mu = 2.074e-6 * math.exp(2028.6 / (t + 273.15))

    # 4. 导热系数 k (W/(m·K))
    k = 0.495 + 0.0011 * t - 3.0e-6 * (t ** 2)

    nu = mu / rho
    pr = (cp * mu) / k

    return FluidProperties(
        name="25%乙二醇水溶液 (EG25 - Ethylene Glycol 25%)",
        code="EG25",
        temp_c=t,
        density=rho,
        specific_heat=cp,
        dynamic_viscosity=mu,
        kinematic_viscosity=nu,
        prandtl_number=pr,
        thermal_conductivity=k,
    )


def get_fluid_properties(fluid_type: str = "WATER", temp_c: float = 40.0) -> FluidProperties:
    """
    统一工质物性获取工厂函数 / Factory function to retrieve fluid properties.

    :param fluid_type: 工质标识字符串 (WATER / PG25 / EG25 等)
    :param temp_c: 计算温度 (degC)
    :return: FluidProperties 实例
    """
    key = str(fluid_type).strip().upper()

    if "PG" in key or "丙二醇" in key:
        return get_pg25_properties(temp_c)
    elif "EG" in key or "乙二醇" in key:
        return get_eg25_properties(temp_c)
    elif "WATER" in key or "水" in key or "DI" in key:
        return get_water_properties(temp_c)
    else:
        # 默认回退至去离子水 / Fallback to pure water
        return get_water_properties(temp_c)
