$ErrorActionPreference = 'Stop'

$tracked = @(git ls-files)
if ($LASTEXITCODE -ne 0) { throw 'Execute dentro do repositório Git.' }

$forbiddenExtensions = @('.wav', '.mp3', '.flac', '.m4a', '.aac', '.mp4', '.mov', '.mkv', '.jpg', '.jpeg', '.png', '.gguf', '.onnx', '.bin', '.pem', '.key', '.token', '.log', '.srt', '.vtt', '.fcpxml', '.edl')
$badFiles = @($tracked | Where-Object { $forbiddenExtensions -contains [IO.Path]::GetExtension($_).ToLowerInvariant() })

$patterns = @(
    @{ Label = 'caminho de perfil Windows'; Regex = 'C:\\Users\\' },
    @{ Label = 'caminho privado do disco de IA'; Regex = 'D:\\IA' },
    @{ Label = 'identificador pessoal'; Regex = 'bielm|bielmedeiros' },
    @{ Label = 'token GitHub'; Regex = 'gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}' },
    @{ Label = 'chave OpenAI'; Regex = 'sk-[A-Za-z0-9]{20,}' },
    @{ Label = 'chave AWS'; Regex = 'AKIA[0-9A-Z]{16}' },
    @{ Label = 'chave privada'; Regex = 'BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY' },
    @{ Label = 'segredo atribuído em texto'; Regex = '(api[_-]?key|token|secret|password|senha)[[:space:]]*[:=][[:space:]]*["''][^"'']{8,}' }
)

$matches = @()
foreach ($pattern in $patterns) {
    $paths = @(git grep -Il -E -- $pattern.Regex -- . ':(exclude)scripts/check_repository_safety.ps1' 2>$null)
    foreach ($path in $paths) {
        $matches += "[$($pattern.Label)] $path"
    }
}

if ($badFiles.Count -or $matches.Count) {
    Write-Error "Repositório reprovado para envio.`nArquivos privados rastreados: $($badFiles -join ', ')`nCorrespondências: $($matches -join '; ')"
}

if (-not (Select-String -LiteralPath 'config/channels/noticias.json' -Pattern '"auto_publish"\s*:\s*false' -Quiet)) {
    throw 'auto_publish precisa permanecer false durante o desenvolvimento.'
}

Write-Output "Verificação aprovada: $($tracked.Count) arquivos rastreados, sem mídia, credenciais ou caminhos privados conhecidos."
