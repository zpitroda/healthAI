$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LlamaDir = Join-Path $ScriptDir "llama.cpp"

# Auto-detect Qwen 3.8 / 3.6 model GGUF path
$CandidateModels = @(
    (Join-Path $ScriptDir "models\qwen3.8-27b-q6_k.gguf"),
    (Join-Path $ScriptDir "models\qwen3.6-27b-q6_k.gguf"),
    (Join-Path $ScriptDir "models\qwen3.8-27b.gguf"),
    (Join-Path $ScriptDir "models\qwen3.6-27b.gguf")
)

$MODEL_PATH = $CandidateModels | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $MODEL_PATH) {
    $FallbackPath = Join-Path $ScriptDir "models\qwen3.8-27b-q6_k.gguf"
    if (-not (Test-Path $FallbackPath)) {
        Write-Warning "Model file not found at default locations."
        $MODEL_PATH = Read-Host "Please enter full path to model GGUF"
    } else {
        $MODEL_PATH = $FallbackPath
    }
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
# --reasoning-effort medium : Sets balanced reasoning effort level in chat template
# --reasoning-budget 512  : Caps reasoning tokens to prevent runaway thinking loops
# --reasoning-format deepseek : Cleanly separates reasoning thoughts from final content
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
    --reasoning-effort medium `
    --reasoning-budget 512 `
    --reasoning-format deepseek `
    --load-mode mlock `
    --port 8080
