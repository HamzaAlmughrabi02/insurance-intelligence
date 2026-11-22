$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$taskDesktop=[Environment]::GetFolderPath('Desktop')
$taskPython=Join-Path $taskRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {$taskPython=Join-Path $env:USERPROFILE 'anaconda3\pythonw.exe'}
if (-not (Test-Path -LiteralPath $taskPython)) {throw 'Python runtime not found'}
$taskShell=New-Object -ComObject WScript.Shell
$taskLinkPath=Join-Path $taskDesktop 'IntelliSure.lnk'
$taskLink=$taskShell.CreateShortcut($taskLinkPath)
$taskLink.TargetPath=$taskPython
$taskLink.Arguments='"'+(Join-Path $taskRoot 'launcher.py')+'"'
$taskLink.WorkingDirectory=$taskRoot
$taskLink.Description='تشغيل IntelliSure والدخول بالحساب المحلي'
$taskLink.WindowStyle=7
$taskLink.Save()
Write-Output "Created desktop shortcut: $taskLinkPath"
