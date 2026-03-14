@echo off
cd /d "C:\Users\sjlee\OneDrive\GitHub\fee-income-dashboard"

:: Always open browser
start "" "http://localhost:8501"

:: Check if Streamlit is already running
netstat -ano | findstr ":8501" >nul 2>&1
if %errorlevel%==0 (
    :: Already running, just opened browser
    exit
) else (
    :: Start Streamlit server
    py -m streamlit run app.py
)
