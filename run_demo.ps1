[CmdletBinding()]
param(
    [string]$BackendHost = "127.0.0.1",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5500,
    [switch]$Reload,
    [switch]$OpenBrowser
)

$ErrorActionPreference = "Stop"

function Write-Status {
    param([string]$Message)
    Write-Host "[run_demo] $Message"
}

function Import-DotEnv {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Status "No .env file found. Using existing shell environment values."
        return
    }

    Write-Status "Loading environment variables from $Path"
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $parts = $trimmed -split "=", 2
        if ($parts.Count -ne 2) {
            continue
        }

        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (-not $name -or $name -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
            Write-Status "Skipping invalid .env variable name: $name"
            continue
        }
        if ($name -ieq "PATH") {
            Write-Status "Skipping PATH from .env to avoid Windows environment conflicts."
            continue
        }

        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Get-PythonCommand {
    $venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        return $venvPython
    }
    return "python"
}

function Test-PortAvailable {
    param([int]$Port)

    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Parse("127.0.0.1"), $Port)
        $listener.Start()
        $listener.Stop()
        return $true
    } catch {
        return $false
    }
}

function Get-AvailablePort {
    param([int]$PreferredPort)

    $port = $PreferredPort
    while (-not (Test-PortAvailable -Port $port)) {
        $port++
    }
    return $port
}

function Reset-LogFile {
    param([string]$Path)

    try {
        "" | Set-Content -LiteralPath $Path -ErrorAction Stop
        return $Path
    } catch [System.IO.IOException] {
        $directory = Split-Path -Parent $Path
        $filename = [System.IO.Path]::GetFileNameWithoutExtension($Path)
        $extension = [System.IO.Path]::GetExtension($Path)
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $fallbackPath = Join-Path $directory "$filename.$timestamp$extension"

        Write-Status "Log file is locked by another process: $Path"
        Write-Status "Using alternate log file: $fallbackPath"
        "" | Set-Content -LiteralPath $fallbackPath -ErrorAction Stop
        return $fallbackPath
    }
}

function Show-LogTail {
    param(
        [string]$Path,
        [int]$Lines = 30
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Status "Log file not found: $Path"
        return
    }

    Write-Status "Last $Lines lines from $Path"
    Get-Content -LiteralPath $Path -Tail $Lines | ForEach-Object {
        Write-Host "  $_"
    }
}

$python = Get-PythonCommand
Import-DotEnv -Path (Join-Path $PSScriptRoot ".env")

$logsDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
$backendLog = Join-Path $logsDir "backend.log"
$backendErrLog = Join-Path $logsDir "backend.err.log"
$frontendLog = Join-Path $logsDir "frontend.log"
$frontendErrLog = Join-Path $logsDir "frontend.err.log"
$backendLog = Reset-LogFile -Path $backendLog
$backendErrLog = Reset-LogFile -Path $backendErrLog
$frontendLog = Reset-LogFile -Path $frontendLog
$frontendErrLog = Reset-LogFile -Path $frontendErrLog

$backendPort = Get-AvailablePort -PreferredPort $BackendPort
$frontendPort = Get-AvailablePort -PreferredPort $FrontendPort

$backendUrl = "http://${BackendHost}:$backendPort"
$encodedBackendUrl = [System.Uri]::EscapeDataString($backendUrl)
$frontendUrl = "http://${BackendHost}:$frontendPort/index.html?apiBase=$encodedBackendUrl"

$backendArgs = @("-m", "uvicorn", "backend.main:app", "--host", $BackendHost, "--port", "$backendPort")
if ($Reload) {
    $backendArgs += "--reload"
}

$frontendArgs = @("-m", "http.server", "$frontendPort", "--bind", $BackendHost, "--directory", "frontend")

$backendArgString = ($backendArgs | ForEach-Object { "'$($_ -replace "'", "''")'" }) -join " "
$frontendArgString = ($frontendArgs | ForEach-Object { "'$($_ -replace "'", "''")'" }) -join " "
$backendCommand = @"
Set-Location -LiteralPath '$($PSScriptRoot -replace "'", "''")'
& '$($python -replace "'", "''")' $backendArgString 1> '$($backendLog -replace "'", "''")' 2> '$($backendErrLog -replace "'", "''")'
"@

$frontendCommand = @"
Set-Location -LiteralPath '$($PSScriptRoot -replace "'", "''")'
& '$($python -replace "'", "''")' $frontendArgString 1> '$($frontendLog -replace "'", "''")' 2> '$($frontendErrLog -replace "'", "''")'
"@

Write-Status "Starting backend at $backendUrl"
$backendProcess = Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-Command",
    $backendCommand
) -WindowStyle Hidden -PassThru

Write-Status "Starting frontend at $frontendUrl"
$frontendProcess = Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-Command",
    $frontendCommand
) -WindowStyle Hidden -PassThru

Write-Status "Waiting for backend health check..."
$backendReady = $false
for ($attempt = 1; $attempt -le 30; $attempt++) {
    if ($backendProcess.HasExited) {
        break
    }
    try {
        $health = Invoke-RestMethod -Uri "$backendUrl/health" -TimeoutSec 1
        if ($health.status -eq "ok") {
            $backendReady = $true
            break
        }
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $backendReady) {
    Write-Status "Backend did not answer /health."
    if ($backendProcess.HasExited) {
        Write-Status "Backend process exited with code $($backendProcess.ExitCode)."
    }
    Show-LogTail -Path $backendErrLog
    Show-LogTail -Path $backendLog
}

Write-Status "Waiting for frontend server..."
$frontendReady = $false
for ($attempt = 1; $attempt -le 20; $attempt++) {
    if ($frontendProcess.HasExited) {
        break
    }
    try {
        $response = Invoke-WebRequest -Uri $frontendUrl -TimeoutSec 1 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            $frontendReady = $true
            break
        }
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $frontendReady) {
    Write-Status "Frontend did not answer."
    if ($frontendProcess.HasExited) {
        Write-Status "Frontend process exited with code $($frontendProcess.ExitCode)."
    }
    Show-LogTail -Path $frontendErrLog
    Show-LogTail -Path $frontendLog
}

Write-Status "Frontend URL: $frontendUrl"
Write-Status "Backend URL:  $backendUrl"
Write-Status "Backend logs: $backendLog"
Write-Status "Backend errors: $backendErrLog"
Write-Status "Frontend logs: $frontendLog"
Write-Status "Frontend errors: $frontendErrLog"
Write-Status "If .env contains API keys, they were loaded into the launched processes."

if ($OpenBrowser -and $backendReady -and $frontendReady) {
    Write-Status "Opening browser..."
    Start-Process $frontendUrl
}
