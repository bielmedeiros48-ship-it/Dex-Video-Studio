$ErrorActionPreference = 'Stop'
$localData = Join-Path $PSScriptRoot 'projects'
$env:OLLAMA_VIDEO_DATA = if ($env:OLLAMA_VIDEO_DATA) {
    $env:OLLAMA_VIDEO_DATA
} elseif (Test-Path -LiteralPath $localData) {
    $PSScriptRoot
} else {
    Join-Path $env:USERPROFILE 'IA\Ollama-Video-Studio'
}
$env:OLLAMA_VIDEO_STATE = if ($env:OLLAMA_VIDEO_STATE) { $env:OLLAMA_VIDEO_STATE } else { Join-Path $env:LOCALAPPDATA 'OllamaVideoStudio\state' }
$env:PYTHONUTF8 = '1'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path $python)) { $python = 'python' }
& $python "$PSScriptRoot\src\ollama_video.py" @args
exit $LASTEXITCODE
