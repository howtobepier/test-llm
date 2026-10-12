# Avvio JARVIS (Windows) — evita processi duplicati su porte già in ascolto.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"

function Test-LocalPort([int]$Port) {
  try {
    $client = New-Object System.Net.Sockets.TcpClient
    $iar = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(400)
    if ($ok -and $client.Connected) {
      $client.EndConnect($iar) | Out-Null
      $client.Close()
      return $true
    }
    $client.Close()
    return $false
  } catch {
    return $false
  }
}

Write-Host "=== JARVIS ===" -ForegroundColor Cyan

if (-not (Test-Path $VenvPython)) {
  Write-Host "Ambiente Python assente. Esegui una volta: python -m venv backend\.venv; backend\.venv\Scripts\pip install -r backend\requirements.txt"
  exit 1
}

if (-not (Test-Path (Join-Path $Backend ".env"))) {
  Copy-Item (Join-Path $Backend ".env.example") (Join-Path $Backend ".env")
  Write-Host "Creato backend\.env da esempio."
}

foreach ($cfg in @("apps.json", "routines.json")) {
  $target = Join-Path $Backend "config\$cfg"
  $example = Join-Path $Backend "config\$($cfg -replace '\.json$', '.example.json')"
  if (-not (Test-Path $target) -and (Test-Path $example)) {
    Copy-Item $example $target
  }
}

try {
  $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
  Write-Host "Ollama: OK ($($tags.models.Count) modelli)"
} catch {
  Write-Host "Ollama non raggiungibile su 127.0.0.1:11434 — strumenti locali resteranno disponibili." -ForegroundColor Yellow
}

$backendPid = $null
if (Test-LocalPort 8000) {
  Write-Host "Backend già in ascolto su http://127.0.0.1:8000 — nessun nuovo processo."
} else {
  Write-Host "Avvio backend su http://127.0.0.1:8000 ..."
  $backend = Start-Process -FilePath $VenvPython -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory $Backend -PassThru -WindowStyle Minimized
  $backendPid = $backend.Id
  Start-Sleep -Seconds 2
  try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/statu-model-server" -TimeoutSec 5 | Out-Null
    Write-Host "Backend: OK"
  } catch {
    Write-Host "Backend non risponde ancora; controlla la finestra del processo." -ForegroundColor Yellow
  }
}

$frontendPid = $null
if (Test-LocalPort 4200) {
  Write-Host "Frontend già in ascolto su http://localhost:4200 — nessun nuovo processo."
} elseif (Test-Path (Join-Path $Frontend "node_modules")) {
  Write-Host "Avvio frontend su http://localhost:4200 ..."
  $frontend = Start-Process -FilePath "npm" -ArgumentList "start" -WorkingDirectory $Frontend -PassThru -WindowStyle Minimized
  $frontendPid = $frontend.Id
} else {
  Write-Host "Frontend: esegui prima 'npm install' in frontend/" -ForegroundColor Yellow
}

if ($backendPid -or $frontendPid) {
  Write-Host "PID avviati: backend=$backendPid frontend=$frontendPid"
}

Write-Host ""
Write-Host "Dashboard: http://localhost:4200" -ForegroundColor Green
Write-Host "API:       http://127.0.0.1:8000/docs"
Write-Host "Per arrestare: chiudi le finestre dei processi o termina i PID."

try {
  Start-Process "http://localhost:4200"
} catch {
  # browser non obbligatorio
}
