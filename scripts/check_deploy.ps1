param(
    [string]$HealthUrl = "http://127.0.0.1:8000/api/v1/health/readiness",
    [string]$ComposeFile = "docker-compose.yml",
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $ComposeFile -PathType Leaf)) {
    throw "Arquivo Compose nao encontrado: $ComposeFile"
}

$composeArgs = @("compose")
if ($EnvFile) {
    if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
        throw "Arquivo de ambiente nao encontrado: $EnvFile"
    }
    $composeArgs += @("--env-file", $EnvFile)
}
$composeArgs += @("-f", $ComposeFile, "config", "--quiet")

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Configuracao Docker Compose invalida"
}
Write-Host "Configuracao Docker Compose: OK" -ForegroundColor Green

try {
    $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 10
} catch {
    throw "Falha ao consultar readiness em ${HealthUrl}: $_"
}
if ($health.status -ne "READY" -or $health.postgis -ne "OPERACIONAL") {
    throw "API ou banco PostGIS nao esta pronto"
}
Write-Host "API e PostGIS respondendo (latencia: $($health.latencia_db_ms) ms)" -ForegroundColor Green
Write-Host "Verificacao basica concluida. Antes de implantar, execute testes em ambiente isolado e valide um backup restaurado." -ForegroundColor Yellow
