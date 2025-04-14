@echo off
set PID_FILE="C:\Path\To\Your\Script\blender_pid.txt"

if exist %PID_FILE% (
    set /p BLENDER_PID=<%PID_FILE%
    echo Killing Blender with PID %BLENDER_PID%
    taskkill /PID %BLENDER_PID% /F
    del %PID_FILE%
) else (
    echo No Blender PID file found.
)
