param([switch]$Database)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskProcesses = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -like "*$taskRoot*" -and (
        ($_.Name -eq 'python.exe' -and ($_.CommandLine -match 'uvicorn app.main:app' -or $_.CommandLine -match 'app.workers.geocoding')) -or
        ($_.Name -eq 'node.exe' -and $_.CommandLine -match 'frontend[\\/]node_modules[\\/]vite[\\/]bin[\\/]vite.js')
    )
}
foreach ($taskProcess in $taskProcesses) { Stop-Process -Id $taskProcess.ProcessId -ErrorAction SilentlyContinue }
if ($Database) {
    $taskPgBin = if ($env:PG_BIN) { $env:PG_BIN } else { 'C:\Program Files\PostgreSQL\18\bin' }
    $taskData = Join-Path $taskRoot '.local\pgdata'
    & (Join-Path $taskPgBin 'pg_ctl.exe') -D $taskData -m fast -w stop
}
Write-Host 'The project development processes have been stopped.'
