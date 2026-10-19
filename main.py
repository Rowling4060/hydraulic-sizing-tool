"""
数据中心液冷二次侧流体管网水力计算与水泵选型工具 - Streamlit 网页版
Data Center Liquid Cooling Secondary Loop Hydraulic Sizing & Pump Sizing Tool (Streamlit Web App)

运行方式:
    streamlit run main.py
"""

import streamlit as st
from pathlib import Path
import sys

# 确保当前项目根路径在 sys.path 中
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
from core.fluid_props import get_fluid_properties
from core.hydraulics import pressure_to_head_m


def set_page_config():
    st.set_page_config(
        page_title="数据中心液冷水力计算工具",
        page_icon="💧",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def display_header():
    st.title("💧 数据中心液冷二次侧水力计算与水泵选型工具")
    st.caption("Data Center Liquid Cooling Secondary Loop Hydraulic Sizing & Pump Sizing Tool")


def input_sidebar() -> dict:
    with st.sidebar:
        st.header("🔧 输入参数 / Input Parameters")
        st.markdown("调节以下滑块以设计系统工况：")

        rack_count = st.slider(
            "机柜数量 (Number of Racks)",
            min_value=1,
            max_value=100,
            value=DEFAULT_RACK_COUNT,
            step=1,
            help="机柜总数量",
        )

        total_heat_load_kw = st.slider(
            "总热负荷 (Total Heat Load) [kW]",
            min_value=1.0,
            max_value=5000.0,
            value=DEFAULT_RACK_COUNT * DEFAULT_RACK_POWER_KW,
            step=0.1,
            help="二次侧总散热负荷（千瓦）",
        )

        delta_t_c = st.slider(
            "供回水温差 (Supply‑Return ΔT) [°C]",
            min_value=2.0,
            max_value=20.0,
            value=DEFAULT_DELTA_T_C,
            step=0.1,
            help="供水与回水温度差",
        )

        # 固定参数（可根据需要改为可选）
        fluid_type = st.selectbox(
            "工质类型 (Coolant Fluid)",
            options=["WATER", "PG25", "EG25"],
            index=0,
            help="WATER: 去离子水, PG25: 25%丙二醇, EG25: 25%乙二醇",
        )

        supply_temp_c = st.number_input(
            "供水温度 (Supply Temperature) [°C]",
            min_value=5.0,
            max_value=50.0,
            value=DEFAULT_SUPPLY_TEMP_C,
            step=0.5,
            help="进入系统的供水温度",
        )

        # 计算单机柜功率（避免除零）
        rack_power_kw = total_heat_load_kw / rack_count if rack_count > 0 else 0.0

        st.markdown("---")
        st.subheader("📊 当前工况摘要")
        st.write(f"**机柜数量:** {rack_count}")
        st.write(f"**单机柜功率:** {rack_power_kw:.2f} kW")
        st.write(f"**总热负荷:** {total_heat_load_kw:.2f} kW")
        st.write(f"**供回水温差:** {delta_t_c:.1f} °C")
        st.write(f"**供水温度:** {supply_temp_c:.1f} °C")
        st.write(f"**工质类型:** {fluid_type}")

        return {
            "rack_count": rack_count,
            "rack_power_kw": rack_power_kw,
            "delta_t_c": delta_t_c,
            "fluid_type": fluid_type,
            "supply_temp_c": supply_temp_c,
        }


def compute_and_display(inputs: dict):
    # 初始化计算引擎
    engine = HydraulicSizingEngine(
        rack_count=inputs["rack_count"],
        rack_power_kw=inputs["rack_power_kw"],
        delta_t_c=inputs["delta_t_c"],
        fluid_type=inputs["fluid_type"],
        supply_temp_c=inputs["supply_temp_c"],
        return_temp_c=inputs["supply_temp_c"] + inputs["delta_t_c"],
    )

    # 执行求解
    summary: SizingSummary = engine.solve(preferred_dn=None)

    # 主界面：左侧描述，右侧 KPI 卡片
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("📈 计算结果概览")
        st.markdown(
            f"""
            - **循环质量流量:** {summary.mass_flow_kg_s:.3f} kg/s
            - **循环体积流量:** {summary.volume_flow_m3_h:.2f} m³/h ({summary.volume_flow_lpm:.1f} LPM)
            - **选定集管管径:** {summary.selected_pipe.dn} (内径 {summary.selected_pipe.inner_dia_mm:.1f} mm)
            - **集管流速:** {summary.selected_pipe.velocity_m_s:.2f} m/s ({summary.selected_pipe.flow_regime})
            """
        )
        with st.expander("查看详细部件阻力分解"):
            st.dataframe(
                {
                    "部件": [c.name_cn for c in summary.component_losses],
                    "阻力 (kPa)": [f"{c.dp_kpa:.2f}" for c in summary.component_losses],
                    "水头 (mH₂O)": [f"{c.head_m:.2f}" for c in summary.component_losses],
                    "占比 (%)": [f"{c.percentage:.1f}" for c in summary.component_losses],
                },
                hide_index=True,
                use_container_width=True,
            )

    with col_right:
        st.subheader("🎯 关键性能指标")
        st.metric(
            label="系统总水力阻力",
            value=f"{summary.total_dp_kpa:.2f} kPa",
            help="管网总压降（千帕）",
        )
        st.metric(
            label="水泵设计扬程",
            value=f"{summary.total_head_m:.2f} mH₂O",
            help="泵需要提供的扬程（米水柱）",
        )
        # 可选：显示水泵功率
        st.metric(
            label="水泵轴功率",
            value=f"{summary.pump_shaft_power_kw:.2f} kW",
            help="泵轴功率（考虑水力效率）",
        )
        st.metric(
            label="电机输入功率",
            value=f"{summary.motor_electric_power_kw:.2f} kW",
            help="电机电功率（考虑电机效率）",
        )


def main():
    set_page_config()
    display_header()
    user_inputs = input_sidebar()
    compute_and_display(user_inputs)


if __name__ == "__main__":
    main()