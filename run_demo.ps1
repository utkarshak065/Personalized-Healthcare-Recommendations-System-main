# One-click demo (Windows PowerShell). Run from the repository root.
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$apiPortStart = if ($env:CARECONNECT_API_PORT) { [int]$env:CARECONNECT_API_PORT } else { 8001 }
$uiPortStart = if ($env:CARECONNECT_STREAMLIT_PORT) { [int]$env:CARECONNECT_STREAMLIT_PORT } else { 8501 }

function Find-FreePort([int]$start) {
    for ($port = $start; $port -lt ($start + 100) -and $port -le 65535; $port++) {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
        try {
            $listener.Start()
            return $port
        } catch {
            # Try the next local port.
        } finally {
            $listener.Stop()
        }
    }
    throw "No free local port found starting at $start."
}

if (-not (Test-Path $python)) {
    py -3 -m venv (Join-Path $root ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment." }
}

& $python -m pip install -q -r (Join-Path $root "requirements-demo.txt")
if ($LASTEXITCODE -ne 0) { throw "Could not install demo dependencies." }

$apiPort = Find-FreePort $apiPortStart
$uiPort = Find-FreePort $uiPortStart
$env:FASTAPI_ENDPOINT = "http://127.0.0.1:$apiPort"
$api = $null

try {
    $api = Start-Process -PassThru -NoNewWindow -WorkingDirectory $root -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "main:app", "--app-dir", "fastapi",
            "--host", "127.0.0.1", "--port", "$apiPort")

    $apiReady = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($api.HasExited) { throw "FastAPI stopped during startup. Check the API startup output above." }
        try {
            Invoke-WebRequest -UseBasicParsing -Uri "$($env:FASTAPI_ENDPOINT)/openapi.json" -TimeoutSec 1 | Out-Null
            $apiReady = $true
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $apiReady) { throw "FastAPI did not become ready at $($env:FASTAPI_ENDPOINT)." }

    Write-Host "CareConnect API is ready at $($env:FASTAPI_ENDPOINT)"
    Write-Host "Opening the app at http://127.0.0.1:$uiPort"
    Start-Process "http://127.0.0.1:$uiPort"
    Push-Location (Join-Path $root "Streamlit")
    try {
        & $python -m streamlit run Home.py --server.address 127.0.0.1 --server.port $uiPort `
            --server.headless true --browser.gatherUsageStats false
    } finally {
        Pop-Location
    }
} finally {
    if ($api -and -not $api.HasExited) {
        Stop-Process -Id $api.Id -Force
    }
}
