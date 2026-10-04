param([switch]$Demo)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
function Test-AtelierPort([int]$Port) {
    $taskSocket = [System.Net.Sockets.TcpClient]::new()
    try {
        $taskConnect = $taskSocket.ConnectAsync('127.0.0.1', $Port)
        return ($taskConnect.Wait(700) -and $taskSocket.Connected)
    } catch { return $false } finally { $taskSocket.Dispose() }
}
if (-not (Test-Path $taskPython)) {
    python -m venv (Join-Path $taskRoot '.venv')
    & $taskPython -m pip install -r (Join-Path $taskRoot 'backend\requirements.lock')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
}
& $taskPython (Join-Path $PSScriptRoot 'init_local.py')
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed' }
Push-Location (Join-Path $taskRoot 'backend')
try {
    & $taskPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Migration failed' }
    if ($Demo) { & $taskPython -X utf8 -m app.cli.seed_demo; if ($LASTEXITCODE -ne 0) { throw 'Demo creation failed' } }
} finally { Pop-Location }
$taskNodeModules = Join-Path $taskRoot 'frontend\node_modules'
if (-not (Test-Path $taskNodeModules)) { Push-Location (Join-Path $taskRoot 'frontend'); try { npm ci; if ($LASTEXITCODE -ne 0) { throw 'Frontend installation failed' } } finally { Pop-Location } }
$taskProcesses = @()
foreach ($taskSpec in @(@{Port=8014;Name='api';Exe=$taskPython;Args=@('-X','utf8','-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8014');Cwd='backend'},@{Port=5194;Name='web';Exe=(Get-Command node).Source;Args=@((Join-Path $taskRoot 'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1');Cwd='frontend'})) {
    if (Test-AtelierPort $taskSpec.Port) { Write-Host "Port $($taskSpec.Port) is already listening; leaving the process unchanged."; continue }
    $taskProcess = Start-Process -FilePath $taskSpec.Exe -ArgumentList $taskSpec.Args -WorkingDirectory (Join-Path $taskRoot $taskSpec.Cwd) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRoot ".local/$($taskSpec.Name).log") -RedirectStandardError (Join-Path $taskRoot ".local/$($taskSpec.Name).error.log")
    $taskProcesses += @{Name=$taskSpec.Name;Id=$taskProcess.Id}
    $taskReady = $false
    for ($taskTry = 0; $taskTry -lt 40; $taskTry++) {
        if (Test-AtelierPort $taskSpec.Port) { $taskReady = $true; break }
        Start-Sleep -Milliseconds 200
    }
    if (-not $taskReady) { throw "$($taskSpec.Name) did not start. See .local logs." }
}
if ($taskProcesses.Count) { $taskProcesses | ConvertTo-Json | Set-Content (Join-Path $taskRoot '.local\processes.json') }
$taskWorker = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like "*$taskRoot*" -and $_.CommandLine -match 'app.workers.geocoding' }
if (-not $taskWorker) {
    Start-Process -FilePath $taskPython -ArgumentList @('-X','utf8','-m','app.workers.geocoding') -WorkingDirectory (Join-Path $taskRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRoot '.local\worker.log') -RedirectStandardError (Join-Path $taskRoot '.local\worker.error.log') | Out-Null
}
Write-Host 'Web: http://127.0.0.1:5194'
Write-Host 'API: http://127.0.0.1:8014/docs'
