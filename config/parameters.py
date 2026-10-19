"""
配置参数模块 - Configuration Parameters Module
定义数据中心液冷二次侧计算所需的默认设计参数、标准管径库与局部阻力系数。
Defines default design parameters, standard pipe database, and minor loss coefficients.
"""

from dataclasses import dataclass
from typing import Dict, List

# ==============================================================================
# 1. 默认输入工况参数 / Default Operating Parameters
# ==============================================================================
DEFAULT_RACK_COUNT = 20                 # 机柜数量 (个) / Number of IT racks
DEFAULT_RACK_POWER_KW = 50.0            # 单机柜设计功耗 (kW) / Design power per rack
DEFAULT_DELTA_T_C = 10.0                # 供回水设计温差 (℃) / Supply-return temperature difference
DEFAULT_SUPPLY_TEMP_C = 35.0            # 供水温度 (℃) / Supply water temperature (e.g. ASHRAE W35)
DEFAULT_RETURN_TEMP_C = 45.0            # 回水温度 (℃) / Return water temperature

# 工质类型: 'WATER' (去离子水) / 'PG25' (25% 丙二醇水溶液) / 'EG25' (25% 乙二醇水溶液)
DEFAULT_FLUID = 'WATER'

# 重力加速度 / Gravitational acceleration (m/s^2)
GRAVITY_ACCEL = 9.80665

# 管道绝对粗糙度 (不锈钢 304/316 卫生级工业焊管/无缝管)
# Absolute roughness for stainless steel 304/316 pipe (m)
PIPE_ROUGHNESS_M = 0.000045             # 0.045 mm (45 microns)


# ==============================================================================
# 2. 标准管道规格数据库 (工业不锈钢管 Stainless Steel Pipes)
# ==============================================================================
@dataclass
class PipeSpec:
    """标准管径规格数据结构 / Standard Pipe Specification Data Class"""
    dn: str             # 公称通径 (Nominal Diameter, e.g., 'DN100')
    nominal_inch: str   # 公称英制尺寸 (Nominal inches, e.g., '4"')
    outer_dia_mm: float # 外径 (Outer Diameter, mm)
    wall_thick_mm: float# 壁厚 (Wall Thickness, mm)
    inner_dia_mm: float # 内径 (Inner Diameter, mm)

    @property
    def inner_dia_m(self) -> float:
        """内径 (m) / Inner diameter in meters"""
        return self.inner_dia_mm / 1000.0

    @property
    def flow_area_m2(self) -> float:
        """流通截面积 (m^2) / Flow cross-sectional area"""
        import math
        return math.pi * (self.inner_dia_m / 2.0) ** 2


# 常用集管候选标准管径 (依据国标/ISO标准及工业常用 Sch 10S/20 不锈钢管)
STANDARD_PIPES: Dict[str, PipeSpec] = {
    'DN50':  PipeSpec('DN50',  '2"',   60.3,  2.0, 56.3),
    'DN65':  PipeSpec('DN65',  '2.5"', 76.1,  2.0, 72.1),
    'DN80':  PipeSpec('DN80',  '3"',   88.9,  2.5, 83.9),
    'DN100': PipeSpec('DN100', '4"',   114.3, 3.0, 108.3),
    'DN125': PipeSpec('DN125', '5"',   141.3, 3.5, 134.3),
    'DN150': PipeSpec('DN150', '6"',   168.3, 4.0, 160.3),
    'DN200': PipeSpec('DN200', '8"',   219.1, 4.5, 210.1),
}


# ==============================================================================
# 3. 管网物理布局与设备阻力基准 / Network Layout & Component Loss Baselines
# ==============================================================================
@dataclass
class CircuitLayoutConfig:
    """管网回路布局配置 / Hydraulic Circuit Layout Configuration"""
    # 集管总长度 (包含供水集管与回水集管单侧长度之和)
    # Total manifold straight pipe length (Supply + Return, m)
    manifold_length_m: float = 50.0

    # 主管路上局部阻力管件 (Equivalent K-factor or fitting counts on main manifold)
    manifold_elbows_count: int = 4          # 90° 弯头数量 / 90-degree elbows
    elbow_k_factor: float = 0.35            # 单个弯头局部阻力系数 / Single elbow K factor
    manifold_valves_count: int = 2          # 主管蝶阀/隔离阀 / Butterfly isolation valves
    valve_k_factor: float = 0.25            # 单个阀门局部阻力系数 / Single valve K factor
    manifold_flowmeter_k: float = 0.50      # 超声波流量计/孔板 / Flow meter K factor
    manifold_tee_k: float = 1.00            # 集管分流/汇流三通综合阻力 / Manifold tee K factor

    # 板式换热器 (PHE / HEX) 二次侧额定压降 (kPa at rated flow)
    # Plate Heat Exchanger secondary side rated pressure drop
    phex_rated_dp_kpa: float = 45.0

    # CDU 内部附件阻力 (双联Y型过滤器、止回阀、内部管路等, kPa at rated flow)
    # CDU internal components (Y-strainer, check valve, internal piping)
    cdu_internal_dp_kpa: float = 35.0

    # 单机柜支路局部阻力 (20个机柜并联，总阻力取最不利机柜阻力)
    # Single rack branch resistance components (Parallel racks across manifold):
    qd_pair_rated_dp_kpa: float = 25.0       # 机柜进出快接头对阻力 / QD pair (Supply + Return)
    rack_coldplates_dp_kpa: float = 80.0     # 机柜内部RDM集管与服务器冷板压降 / Rack cold plates & RDM
    rack_branch_valve_dp_kpa: float = 15.0   # 机柜支管平衡阀/软管阻力 / Branch balancing valve & hose

    # 水泵与电机效率基准 / Pump and motor efficiency
    pump_hydraulic_efficiency: float = 0.75  # 水泵水力效率 (75%)
    motor_efficiency: float = 0.92           # 电机效率 (92% - IE3/IE4 高效电机)
