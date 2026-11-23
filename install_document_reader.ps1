$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$taskEnvironment=Join-Path $taskRoot '.ocr-venv'
if (-not (Test-Path -LiteralPath (Join-Path $taskEnvironment 'Scripts\python.exe'))) {
    python -m venv $taskEnvironment
    if ($LASTEXITCODE -ne 0) {throw 'Could not create OCR environment'}
}
& (Join-Path $taskEnvironment 'Scripts\python.exe') -m pip install -r (Join-Path $taskRoot 'requirements-ocr.txt')
if ($LASTEXITCODE -ne 0) {throw 'OCR dependency installation failed'}
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    ollama pull qwen3-vl:2b-instruct
    if ($LASTEXITCODE -ne 0) {throw 'Local vision model download failed'}
}
Write-Output 'Document reader installed. Start the platform using its existing shortcut.'
