$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Write-Host "OS:" (Get-CimInstance Win32_OperatingSystem).Caption
Write-Host "RAM GB:" ([math]::Round((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize/1MB,2))
Write-Host "CPU:" (Get-CimInstance Win32_Processor).Name
Get-CimInstance Win32_VideoController | ForEach-Object { Write-Host "GPU:" $_.Name }
try { ollama --version; ollama list } catch { Write-Host "Ollama non in PATH" }
try { Invoke-RestMethod http://127.0.0.1:11434/api/tags | ConvertTo-Json -Depth 2 } catch { Write-Host "Ollama API down" }
try { Invoke-RestMethod http://127.0.0.1:8000/api/diagnostics | ConvertTo-Json -Depth 4 } catch { Write-Host "Backend down" }
if (Test-Path "$Root\backend\.env") { Write-Host "--- .env ---"; Get-Content "$Root\backend\.env" }
