<#
.SYNOPSIS
    Ghost Writer - установка одной командой для Windows.

.DESCRIPTION
    Скачивает GhostWriter-Windows-Setup.exe из последнего GitHub Release и
    запускает его в тихом режиме (Inno Setup /VERYSILENT /SUPPRESSMSGBOXES).

.EXAMPLE
    iex (irm https://raw.githubusercontent.com/Amirk4an/GhostWriter/main/install.ps1)

    # Приватный репозиторий (нужен PAT с доступом к repo):
    #   $env:GITHUB_TOKEN = gh auth token   # или вставьте PAT
    #   iex (irm -Headers @{ Authorization = "Bearer $($env:GITHUB_TOKEN)"; Accept = "application/vnd.github.raw" } "https://api.github.com/repos/Amirk4an/GhostWriter/contents/install.ps1?ref=main")

.NOTES
    Требования:
      - Windows 10 / 11
      - PowerShell 5.1 или выше
      - Права администратора (попросит UAC при запуске установщика)
#>

[CmdletBinding()]
param(
    [string]$GhOwner = $(if ($env:GHOSTWRITER_GH_OWNER) { $env:GHOSTWRITER_GH_OWNER } else { 'Amirk4an' }),
    [string]$GhRepo  = $(if ($env:GHOSTWRITER_GH_REPO)  { $env:GHOSTWRITER_GH_REPO  } else { 'GhostWriter' }),
    [string]$AppName = $(if ($env:GHOSTWRITER_APP_NAME) { $env:GHOSTWRITER_APP_NAME } else { 'Ghost Writer' })
)

$ErrorActionPreference = 'Stop'

# --- Утилиты вывода ---
function Write-Info  { param([string]$Message) Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Message) Write-Host "OK  $Message" -ForegroundColor Green }
function Write-Warn2 { param([string]$Message) Write-Host "!   $Message" -ForegroundColor Yellow }
function Write-Err   { param([string]$Message) Write-Host "X   $Message" -ForegroundColor Red }

# --- Проверка PowerShell версии ---
if ($PSVersionTable.PSVersion.Major -lt 5) {
    Write-Err "Требуется PowerShell 5.1 или новее. Текущая версия: $($PSVersionTable.PSVersion)."
    exit 1
}

# Включаем TLS 1.2 для совместимости с ранними версиями Windows 10.
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.ServicePointManager]::SecurityProtocol
} catch {
    Write-Warn2 "Не удалось включить TLS 1.2: $($_.Exception.Message). Продолжаем с настройками по умолчанию."
}

$AssetName    = 'GhostWriter-Windows-Setup.exe'
$DownloadUrl  = "https://github.com/$GhOwner/$GhRepo/releases/latest/download/$AssetName"
$InstallerPath = Join-Path $env:TEMP $AssetName
$LogPath       = Join-Path $env:TEMP "GhostWriter_Install_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

Write-Info "Установка $AppName"

# --- Скачивание ---
if (Test-Path $InstallerPath) {
    Remove-Item $InstallerPath -Force
}

$ghToken = $env:GITHUB_TOKEN
if (-not $ghToken) { $ghToken = $env:GH_TOKEN }

if ($ghToken) {
    Write-Info "Скачивание «$AssetName» через GitHub API (есть GITHUB_TOKEN или GH_TOKEN)…"
    try {
        $apiHeaders = @{
            Authorization        = "Bearer $ghToken"
            Accept                 = 'application/vnd.github+json'
            'X-GitHub-Api-Version' = '2022-11-28'
        }
        $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$GhOwner/$GhRepo/releases/latest" -Headers $apiHeaders -Method Get
        $asset = $rel.assets | Where-Object { $_.name -eq $AssetName } | Select-Object -First 1
        if (-not $asset) {
            throw "В последнем релизе нет файла $AssetName."
        }
        $dlHeaders = @{
            Authorization        = "Bearer $ghToken"
            Accept                 = 'application/octet-stream'
            'X-GitHub-Api-Version' = '2022-11-28'
        }
        Invoke-WebRequest -Uri "https://api.github.com/repos/$GhOwner/$GhRepo/releases/assets/$($asset.id)" -Headers $dlHeaders -OutFile $InstallerPath -UseBasicParsing
    } catch {
        Write-Err "Не удалось скачать через API: $($_.Exception.Message)"
        Write-Err "Проверьте токен (нужен доступ к репозиторию) и наличие релиза с артефактом $AssetName."
        exit 1
    }
} else {
    Write-Info "Скачивание: $DownloadUrl"
    try {
        Invoke-WebRequest -Uri $DownloadUrl -OutFile $InstallerPath -UseBasicParsing
    } catch {
        Write-Err "Не удалось скачать установщик: $($_.Exception.Message)"
        Write-Err "Если репозиторий приватный: задайте `$env:GITHUB_TOKEN (PAT с правом repo) и запустите скрипт снова. См. docs/INSTALL.md."
        Write-Err "Публичный репозиторий: проверьте https://github.com/$GhOwner/$GhRepo/releases/latest"
        exit 1
    }
}

if (-not (Test-Path $InstallerPath) -or (Get-Item $InstallerPath).Length -lt 1024) {
    Write-Err "Скачанный файл пуст или повреждён: $InstallerPath"
    exit 1
}

Write-Ok "Скачано: $InstallerPath ($([math]::Round((Get-Item $InstallerPath).Length / 1MB, 2)) МБ)"

# --- Запуск установщика ---
# /VERYSILENT     - без окон мастера
# /SUPPRESSMSGBOXES - подавить дополнительные диалоги
# /NORESTART      - не перезагружать систему
# /LOG            - писать лог установки (поможет диагностике)
$installerArgs = @(
    '/VERYSILENT',
    '/SUPPRESSMSGBOXES',
    '/NORESTART',
    "/LOG=$LogPath"
)

Write-Info "Запуск установщика (потребуется подтверждение UAC)"
try {
    $proc = Start-Process -FilePath $InstallerPath -ArgumentList $installerArgs -Wait -PassThru -Verb RunAs
} catch {
    Write-Err "Не удалось запустить установщик: $($_.Exception.Message)"
    Remove-Item $InstallerPath -Force -ErrorAction SilentlyContinue
    exit 1
}

if ($proc.ExitCode -ne 0) {
    Write-Err "Установщик завершился с кодом $($proc.ExitCode)."
    if (Test-Path $LogPath) {
        Write-Err "Лог установки: $LogPath"
    }
    exit $proc.ExitCode
}

# --- Очистка ---
Remove-Item $InstallerPath -Force -ErrorAction SilentlyContinue

Write-Ok "$AppName установлен."
Write-Host ""
Write-Host "Что дальше:" -ForegroundColor Cyan
Write-Host "  1. Запустите $AppName из меню Пуск."
Write-Host "  2. Разрешите доступ к микрофону:"
Write-Host "       Параметры -> Конфиденциальность и безопасность -> Микрофон"
Write-Host "  3. Если SmartScreen покажет 'Неизвестный издатель' - это нормально для unsigned билда:"
Write-Host "       нажмите 'Подробнее' -> 'Выполнить в любом случае'."
Write-Host ""
Write-Host "Документация: https://github.com/$GhOwner/$GhRepo/blob/main/docs/INSTALL.md" -ForegroundColor DarkGray
