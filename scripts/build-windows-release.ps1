[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BackendDirectory = Join-Path $ProjectRoot 'backend'
$FrontendDirectory = Join-Path $ProjectRoot 'frontend'
$BuildDirectory = Join-Path $ProjectRoot '.build\windows-release'
$BrowserDirectory = Join-Path $ProjectRoot '.build\playwright-browsers'
$InitialStateDirectory = Join-Path $BuildDirectory 'initial-state'
$ReleaseDirectory = Join-Path $ProjectRoot 'release'

function Invoke-ExternalCommand {
    param([string]$FilePath, [string[]]$Arguments)
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv is required on the build machine. Install it from https://docs.astral.sh/uv/.'
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'Node.js and npm are required on the build machine to create the frontend bundle.'
}

if (Test-Path -LiteralPath $BuildDirectory) { Remove-Item -LiteralPath $BuildDirectory -Recurse -Force }
if (Test-Path -LiteralPath $ReleaseDirectory) { Remove-Item -LiteralPath $ReleaseDirectory -Recurse -Force }
New-Item -ItemType Directory -Path $BuildDirectory -Force | Out-Null

Push-Location $FrontendDirectory
try {
    Invoke-ExternalCommand 'npm' @('ci')
    Invoke-ExternalCommand 'npm' @('run', 'build')
}
finally { Pop-Location }

Push-Location $BackendDirectory
try {
    Invoke-ExternalCommand 'uv' @('sync', '--group', 'packaging')
    Invoke-ExternalCommand 'uv' @('run', 'python', (Join-Path $ProjectRoot 'scripts\prepare-initial-data.py'), '--project-root', $ProjectRoot, '--destination', $InitialStateDirectory)
    $env:PLAYWRIGHT_BROWSERS_PATH = $BrowserDirectory
    Invoke-ExternalCommand 'uv' @('run', 'playwright', 'install', 'chromium')
    Invoke-ExternalCommand 'uv' @(
        'run', 'pyinstaller', '--noconfirm', '--clean', '--windowed', '--name', 'TrendScope', '--paths', '.',
        '--collect-submodules', 'app', '--collect-submodules', 'alembic', '--collect-all', 'playwright',
        '--add-data', "$FrontendDirectory\dist;frontend", '--add-data', "$BackendDirectory\alembic;alembic",
        '--add-data', "$BrowserDirectory;playwright-browsers", '--add-data', "$InitialStateDirectory;initial-state", '--distpath', $ReleaseDirectory,
        '--workpath', (Join-Path $BuildDirectory 'pyinstaller-work'), '--specpath', (Join-Path $BuildDirectory 'spec'),
        'app\desktop.py'
    )
}
finally {
    Remove-Item Env:PLAYWRIGHT_BROWSERS_PATH -ErrorAction SilentlyContinue
    Pop-Location
}

$Executable = Join-Path $ReleaseDirectory 'TrendScope\TrendScope.exe'
if (-not (Test-Path -LiteralPath $Executable)) {
    throw "Packaging completed without the expected executable: $Executable"
}
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'docs\WINDOWS_PORTABLE_RELEASE.md') -Destination (Join-Path $ReleaseDirectory 'TrendScope\README.txt') -Force
Write-Host "Release ready: $Executable"
Write-Host 'Distribute the entire release\TrendScope folder. Users only need to double-click TrendScope.exe.'
