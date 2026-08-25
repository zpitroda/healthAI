$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$MODEL_PATH = "C:\models\qwen3.8-27b-q6_k.gguf"
$LlamaDir = Join-Path $ScriptDir "llama.cpp"

if (-not (Test-Path $MODEL_PATH)) {
    Write-Warning "Model file not found at $MODEL_PATH"
    $MODEL_PATH = Read-Host "Please enter full path to model GGUF"
}

# Optimization flags explained:
# -ngl 99                 : Offload all model layers to RTX 5090 VRAM
# -fa on                  : Flash Attention (drastically saves VRAM and speeds up long context)
# -ctk q8_0 -ctv q8_0     : KV cache quantization to 8-bit (massive memory savings for 16k context)
# -c 16384                : 16k context window
# -b 2048                 : Batch size for prompt evaluation
# --spec-type draft-mtp   : Multi-Target Prediction Speculative Decoding (massive generation speedup)
# --spec-draft-n-max 2    : Maximum 2 draft tokens per step
# --jinja                 : Accurately renders Qwen chat templates without breaking
# --load-mode mlock       : Locks model weights in memory (prevents paging/swapping)
# --port 8080             : Standard port (matches HealthAI OPENAI_BASE_URL default)

Write-Host "Starting llama-server with RTX 5090 optimizations on port 8080..." -ForegroundColor Cyan
Set-Location $LlamaDir
.\llama-server.exe -m $MODEL_PATH `
    -ngl 99 `
    -c 16384 `
    -b 2048 `
    -fa on `
    -ctk q8_0 `
    -ctv q8_0 `
    --spec-type draft-mtp `
    --spec-draft-n-max 2 `
    --jinja `
    --load-mode mlock `
    --port 8080
