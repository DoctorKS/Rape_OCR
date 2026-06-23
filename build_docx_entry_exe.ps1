$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found: $python"
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name Rape_DOCX_Entry `
    --paths src `
    --add-data "docs/example/prototype.docx;docs/example" `
    src/rape_ocr/data_entry_launcher.py

Write-Host "Created: $PSScriptRoot\dist\Rape_DOCX_Entry.exe"
