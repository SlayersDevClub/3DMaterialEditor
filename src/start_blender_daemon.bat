@echo off
REM --- Assumes paths are passed in via arguments ---

set BLENDER_PATH=%1
set BLEND_FILE=%2
set SCRIPT_PATH=%3

REM Optional: echo args for debugging
echo Launching: %BLENDER_PATH% -b %BLEND_FILE% --python %SCRIPT_PATH%

REM Launch Blender directly
"%BLENDER_PATH%" -b "%BLEND_FILE%" --python "%SCRIPT_PATH%"
