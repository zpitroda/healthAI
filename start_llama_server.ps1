$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LlamaDir = Join-Path $ScriptDir "llama.cpp"

# Auto-detect Qwen 3.8 / 3.6 model GGUF path (Unsloth Dynamic UD-Q6_K_M / UD-Q6_K / standard)
$CandidateModels = @(
    (Join-Path $ScriptDir "models\Qwen3.8-27B-UD-Q6_K_M.gguf"),
    (Join-Path $ScriptDir "models\qwen3.8-27b-ud-q6_k_m.gguf"),
    (Join-Path $ScriptDir "models\Qwen3.8-27B-UD-Q6_K.gguf"),
    (Join-Path $ScriptDir "models\qwen3.8-27b-ud-q6_k.gguf"),
    (Join-Path $ScriptDir "models\Qwen3.8-27B-UD-Q4_K_M.gguf"),
    (Join-Path $ScriptDir "models\qwen3.8-27b-ud-q4_k_m.gguf"),
    (Join-Path $ScriptDir "models\qwen3.8-27b-q6_k.gguf"),
    (Join-Path $ScriptDir "models\qwen3.6-27b-q6_k.gguf"),
    (Join-Path $ScriptDir "models\qwen3.8-27b.gguf"),
    (Join-Path $ScriptDir "models\qwen3.6-27b.gguf")
)

$MODEL_PATH = $CandidateModels | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $MODEL_PATH) {
    $FallbackPath = Join-Path $ScriptDir "models\Qwen3.8-27B-UD-Q6_K_M.gguf"
    if (-not (Test-Path $FallbackPath)) {
        Write-Warning "Model file not found at default locations."
        $MODEL_PATH = Read-Host "Please enter full path to model GGUF (default: $FallbackPath)"
        if (-not $MODEL_PATH) { $MODEL_PATH = $FallbackPath }
    } else {
        $MODEL_PATH = $FallbackPath
    }
}

# Detect optional MTP draft model for speculative decoding
$SpecArgs = @()
$MtpCandidate1 = Join-Path $ScriptDir "models\mtp-Qwen3.8-27B-Q4_0.gguf"
$MtpCandidate2 = Join-Path $ScriptDir "models\MTP\mtp-Qwen3.8-27B-Q4_0.gguf"
$SpecMsg = "Disabled (auto-detect if mtp draft model present)"

if (Test-Path $MtpCandidate1) {
    $SpecArgs = @("-md", $MtpCandidate1, "--spec-type", "draft-mtp", "--spec-draft-n-max", "2")
    $SpecMsg = "Enabled (mtp-Qwen3.8-27B-Q4_0.gguf)"
} elseif (Test-Path $MtpCandidate2) {
    $SpecArgs = @("-md", $MtpCandidate2, "--spec-type", "draft-mtp", "--spec-draft-n-max", "2")
    $SpecMsg = "Enabled (MTP\mtp-Qwen3.8-27B-Q4_0.gguf)"
}

$ContextSize = if ($env:LLAMA_CTX) { [int]$env:LLAMA_CTX } else { 32768 }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  healthAI - llama-server (Unsloth Dynamic V3.0 / RTX 5090)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  - Model: $MODEL_PATH" -ForegroundColor White
Write-Host "  - GPU Offload: All Layers (-ngl 99)" -ForegroundColor White
Write-Host "  - Flash Attention: -fa on" -ForegroundColor White
Write-Host "  - 8-bit KV Cache Quantization: -ctk q8_0 -ctv q8_0" -ForegroundColor White
Write-Host "  - Context Window: $ContextSize tokens (-c $ContextSize)" -ForegroundColor White
Write-Host "  - Batch Processing: -b 2048 -ub 1024" -ForegroundColor White
Write-Host "  - Jinja Template Parser: --jinja" -ForegroundColor White
Write-Host "  - Reasoning Stream Extractor: --reasoning-format deepseek" -ForegroundColor White
Write-Host "  - Speculative MTP Decoding: $SpecMsg" -ForegroundColor White
Write-Host "  - Port: 8080" -ForegroundColor White
Write-Host ""

if (Test-Path $LlamaDir) { Set-Location $LlamaDir }

$ServerArgs = @(
    "-m", $MODEL_PATH,
    "-ngl", "99",
    "-c", "$ContextSize",
    "-b", "2048",
    "-ub", "1024",
    "-fa", "on",
    "-ctk", "q8_0",
    "-ctv", "q8_0",
    "--jinja",
    "--reasoning-format", "deepseek",
    "--load-mode", "mlock",
    "--port", "8080"
) + $SpecArgs

& "llama-server.exe" $ServerArgs
