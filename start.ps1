param([switch]$ShowToken)
$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$taskPython=Join-Path $taskRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {$taskPython=Join-Path $env:USERPROFILE 'anaconda3\pythonw.exe'}
if (-not (Test-Path -LiteralPath $taskPython)) {throw 'Python runtime not found'}
Start-Process -FilePath $taskPython -ArgumentList @(('"'+(Join-Path $taskRoot 'launcher.py')+'"')) -WorkingDirectory $taskRoot -WindowStyle Hidden
Write-Host 'Opening Insurance Intelligence. Sign in with your local account; API tokens are managed internally.'
