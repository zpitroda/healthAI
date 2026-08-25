@echo off
title healthAI - llama-server (RTX 5090 Optimized)
setlocal

cd /d "%~dp0llama.cpp"

echo ============================================================
echo   healthAI - llama-server Launcher (RTX 5090 Optimized)
echo ============================================================
echo.

:: Set default model path - Edit this line if your GGUF file is located elsewhere
set "MODEL_PATH=C:\models\qwen3.8-27b-q6_k.gguf"

if not exist "%MODEL_PATH%" (
    echo [!] Model file not found at: %MODEL_PATH%
    echo [*] Please edit start_llama_server.bat to set your MODEL_PATH,
    echo     or enter the full path to your .gguf file below:
    set /p "MODEL_PATH=Model GGUF Path: "
)

echo.
echo [*] Launching llama-server with RTX 5090 optimizations:
echo     - GPU Offload: All Layers (-ngl 99)
echo     - Multi-Target Prediction Speculative Decoding (--spec-type draft-mtp)
echo     - Max Draft Lookahead: 2 (--spec-draft-n-max 2)
echo     - Jinja Template Parser (--jinja)
echo     - Flash Attention (-fa on)
echo     - 8-bit KV Cache Quantization (-ctk q8_0 -ctv q8_0)
echo     - Context Window: 16384 (-c 16384)
echo     - Memory Lock (--load-mode mlock)
echo.

llama-server.exe -m "%MODEL_PATH%" -ngl 99 -c 16384 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --spec-draft-n-max 2 --jinja --load-mode mlock --port 8080

if %errorlevel% neq 0 (
    echo.
    echo [!] llama-server exited with error code %errorlevel%.
    pause
)
