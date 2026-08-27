@echo off
title healthAI - llama-server (RTX 5090 Optimized)
setlocal

echo ============================================================
echo   healthAI - llama-server Launcher (RTX 5090 Optimized)
echo ============================================================
echo.

:: Auto-install CUDA llama.cpp binaries if not found
set "LLAMA_EXE="
if exist "%~dp0llama.cpp\llama-server.exe" (
    set "LLAMA_EXE=%~dp0llama.cpp\llama-server.exe"
    cd /d "%~dp0llama.cpp"
) else (
    where llama-server.exe >nul 2>&1
    if %errorlevel% equ 0 (
        set "LLAMA_EXE=llama-server.exe"
    ) else (
        echo [*] llama-server.exe was not found.
        echo [*] Automatically downloading CUDA-accelerated llama.cpp for Windows...
        python "%~dp0scripts\setup_llama_cpp.py"
        if exist "%~dp0llama.cpp\llama-server.exe" (
            set "LLAMA_EXE=%~dp0llama.cpp\llama-server.exe"
            cd /d "%~dp0llama.cpp"
        )
    )
)

:: Auto-detect Qwen 3.8 / 3.6 model path (Unsloth Dynamic UD-Q6_K_M / UD-Q6_K / standard)
if exist "%~dp0models\Qwen3.8-27B-UD-Q6_K_M.gguf" (
    set "MODEL_PATH=%~dp0models\Qwen3.8-27B-UD-Q6_K_M.gguf"
) else if exist "%~dp0models\qwen3.8-27b-ud-q6_k_m.gguf" (
    set "MODEL_PATH=%~dp0models\qwen3.8-27b-ud-q6_k_m.gguf"
) else if exist "%~dp0models\Qwen3.8-27B-UD-Q6_K.gguf" (
    set "MODEL_PATH=%~dp0models\Qwen3.8-27B-UD-Q6_K.gguf"
) else if exist "%~dp0models\qwen3.8-27b-ud-q6_k.gguf" (
    set "MODEL_PATH=%~dp0models\qwen3.8-27b-ud-q6_k.gguf"
) else if exist "%~dp0models\Qwen3.8-27B-UD-Q4_K_M.gguf" (
    set "MODEL_PATH=%~dp0models\Qwen3.8-27B-UD-Q4_K_M.gguf"
) else if exist "%~dp0models\qwen3.8-27b-ud-q4_k_m.gguf" (
    set "MODEL_PATH=%~dp0models\qwen3.8-27b-ud-q4_k_m.gguf"
) else if exist "%~dp0models\qwen3.8-27b-q6_k.gguf" (
    set "MODEL_PATH=%~dp0models\qwen3.8-27b-q6_k.gguf"
) else if exist "%~dp0models\qwen3.6-27b-q6_k.gguf" (
    set "MODEL_PATH=%~dp0models\qwen3.6-27b-q6_k.gguf"
) else if exist "%~dp0models\qwen3.8-27b.gguf" (
    set "MODEL_PATH=%~dp0models\qwen3.8-27b.gguf"
) else if exist "%~dp0models\qwen3.6-27b.gguf" (
    set "MODEL_PATH=%~dp0models\qwen3.6-27b.gguf"
) else (
    set "MODEL_PATH=%~dp0models\Qwen3.8-27B-UD-Q6_K_M.gguf"
)

if not exist "%MODEL_PATH%" (
    echo [!] Model file not found at default locations.
    echo [*] Please edit start_llama_server.bat to set your MODEL_PATH,
    echo     or enter the full path to your .gguf file below:
    set /p "MODEL_PATH=Model GGUF Path: "
)

:: Detect optional MTP draft model for speculative decoding
set "SPEC_FLAGS="
set "SPEC_MSG=Disabled (auto-detect if mtp draft model present)"
if exist "%~dp0models\mtp-Qwen3.8-27B-Q4_0.gguf" (
    set "SPEC_FLAGS=-md "%~dp0models\mtp-Qwen3.8-27B-Q4_0.gguf" --spec-type draft-mtp --spec-draft-n-max 2"
    set "SPEC_MSG=Enabled (mtp-Qwen3.8-27B-Q4_0.gguf)"
) else if exist "%~dp0models\MTP\mtp-Qwen3.8-27B-Q4_0.gguf" (
    set "SPEC_FLAGS=-md "%~dp0models\MTP\mtp-Qwen3.8-27B-Q4_0.gguf" --spec-type draft-mtp --spec-draft-n-max 2"
    set "SPEC_MSG=Enabled (MTP\mtp-Qwen3.8-27B-Q4_0.gguf)"
)

:: Context window (defaults to 32768 for RTX 5090; fits 21.5GB Q6_K_M + 32k Q8_0 KV Cache within 28GB)
if not defined LLAMA_CTX set "LLAMA_CTX=32768"

echo.
echo [*] Launching llama-server with Unsloth Dynamic V3.0 / RTX 5090 optimizations:
echo     - Model: %MODEL_PATH%
echo     - GPU Offload: All Layers (-ngl 99)
echo     - Flash Attention (-fa on)
echo     - 8-bit KV Cache Quantization (-ctk q8_0 -ctv q8_0)
echo     - Context Window: %LLAMA_CTX% tokens (-c %LLAMA_CTX%)
echo     - Physical Batch Size: -b 2048 -ub 1024
echo     - Jinja Template Parser (--jinja)
echo     - Reasoning Stream Extractor (--reasoning-format deepseek)
echo     - Speculative MTP Decoding: %SPEC_MSG%
echo     - Memory Lock (--load-mode mlock)
echo.

"%LLAMA_EXE%" -m "%MODEL_PATH%" %SPEC_FLAGS% -ngl 99 -c %LLAMA_CTX% -b 2048 -ub 1024 -fa on -ctk q8_0 -ctv q8_0 --jinja --reasoning-format deepseek --load-mode mlock --port 8080

if %errorlevel% neq 0 (
    echo.
    echo [!] llama-server exited with error code %errorlevel%.
    pause
)
