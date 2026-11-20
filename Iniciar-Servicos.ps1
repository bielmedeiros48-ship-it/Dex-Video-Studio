$ErrorActionPreference = 'Stop'
$voiceUrl = 'http://127.0.0.1:3900/v1/audio/capabilities'
try {
    Invoke-RestMethod -Uri $voiceUrl -TimeoutSec 2 | Out-Null
    Write-Host 'VoiceStudio já está ativo.'
    exit 0
} catch {}

$localData = Join-Path $PSScriptRoot 'projects'
$dataRoot = if ($env:OLLAMA_VIDEO_DATA) {
    $env:OLLAMA_VIDEO_DATA
} elseif (Test-Path -LiteralPath $localData) {
    $PSScriptRoot
} else {
    Join-Path $env:USERPROFILE 'IA\Ollama-Video-Studio'
}
$repo = if ($env:OLLAMA_VIDEO_VOICESTUDIO_REPO) {
    $env:OLLAMA_VIDEO_VOICESTUDIO_REPO
} else {
    Join-Path (Split-Path -Parent $dataRoot) 'repositorios\voicestudio'
}
$python = Join-Path $repo '.venv\Scripts\python.exe'
$logDir = Join-Path $dataRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$env:OMNIVOICE_DATA_DIR = Join-Path $repo 'local-data'
$env:HF_HOME = Join-Path $env:OMNIVOICE_DATA_DIR 'hf_cache'
$env:HUGGINGFACE_HUB_CACHE = Join-Path $env:HF_HOME 'hub'
$env:OMNIVOICE_AUDIOCPP_DOTS_MODEL = if ($env:OMNIVOICE_AUDIOCPP_DOTS_MODEL) { $env:OMNIVOICE_AUDIOCPP_DOTS_MODEL } else { Join-Path $env:USERPROFILE 'IA\modelos\VoiceStudio\dots-tts-soar-q8_0.gguf' }
Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','main:app','--app-dir','backend','--host','127.0.0.1','--port','3900') -WorkingDirectory $repo -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logDir 'voicestudio.out.log') -RedirectStandardError (Join-Path $logDir 'voicestudio.err.log')
Write-Host 'VoiceStudio iniciado localmente em 127.0.0.1:3900.'
