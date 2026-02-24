@echo off
REM llama-server Vulkan GPU 가속 실행 스크립트
REM RX 9070 XT + Vulkan 백엔드

set SCRIPT_DIR=%~dp0
set TOOLS_DIR=%SCRIPT_DIR%..\tools\llama-vulkan
set MODEL_PATH=%SCRIPT_DIR%..\models\phi-4-Q4_K_M.gguf

echo ============================================
echo   llama-server (Vulkan GPU)
echo   Model: phi-4 Q4_K_M (14B)
echo   Port: 8080
echo ============================================

"%TOOLS_DIR%\llama-server.exe" ^
    -m "%MODEL_PATH%" ^
    --host 0.0.0.0 ^
    --port 8080 ^
    -ngl 99 ^
    -c 4096 ^
    --flash-attn

pause
