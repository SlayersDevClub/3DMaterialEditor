@echo off
REM --- Path to Blender executable ---
set BLENDER_PATH="C:\Program Files\Blender Foundation\Blender 4.0\blender.exe"

REM --- Path to your daemon script ---
set SCRIPT_PATH="C:\Path\To\Your\Script\blender_daemon.py"

REM --- Path to save the Blender PID ---
set PID_FILE="C:\Path\To\Your\Script\blender_pid.txt"

REM --- Launch Blender in background mode and capture its PID ---
for /f "tokens=2 delims==; " %%i in ('wmic process call create ^"%BLENDER_PATH% --background --python %SCRIPT_PATH%" ^| find "ProcessId"') do echo %%i > %PID_FILE%
