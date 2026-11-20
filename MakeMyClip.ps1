$ErrorActionPreference = 'Stop'
$localData = Join-Path $PSScriptRoot 'projects'
$dataRoot = if ($env:OLLAMA_VIDEO_DATA) {
    $env:OLLAMA_VIDEO_DATA
} elseif (Test-Path -LiteralPath $localData) {
    $PSScriptRoot
} else {
    Join-Path $env:USERPROFILE 'IA\Ollama-Video-Studio'
}
$env:MAKEMYCLIP_WORKSPACE = if ($env:OLLAMA_VIDEO_MAKEMYCLIP_WORKSPACE) {
    $env:OLLAMA_VIDEO_MAKEMYCLIP_WORKSPACE
} else {
    Join-Path $dataRoot 'state\makemyclip-workspace'
}
$env:MAKEMYCLIP_FFMPEG_PATH = if ($env:MAKEMYCLIP_FFMPEG_PATH) { $env:MAKEMYCLIP_FFMPEG_PATH } else { (Get-Command ffmpeg -ErrorAction Stop).Source }
$env:MAKEMYCLIP_WHISPER_PATH = if ($env:MAKEMYCLIP_WHISPER_PATH) { $env:MAKEMYCLIP_WHISPER_PATH } else { Join-Path $dataRoot 'tools\whisper.cpp-b5454\Release\whisper-cli.exe' }
$env:MAKEMYCLIP_WHISPER_MODEL = if ($env:MAKEMYCLIP_WHISPER_MODEL) { $env:MAKEMYCLIP_WHISPER_MODEL } else { Join-Path $env:USERPROFILE 'IA\modelos\ggml-large-v3-turbo-q5_0.bin' }
$clip = if ($env:OLLAMA_VIDEO_MAKEMYCLIP_CLI) { $env:OLLAMA_VIDEO_MAKEMYCLIP_CLI } else { Join-Path $dataRoot 'tools\makemyclip\node_modules\.bin\clip.cmd' }

if (-not (Test-Path -LiteralPath $clip)) {
    throw 'MakeMyClip Editor não está instalado na pasta esperada.'
}

& $clip @args
exit $LASTEXITCODE
