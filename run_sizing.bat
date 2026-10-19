@echo off
chcp 65001 >nul
echo 正在启动液冷二次侧网页版大屏...
cd /d "%~dp0"
streamlit run main.py