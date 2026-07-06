$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

function Invoke-Step {
  param(
    [Parameter(Mandatory = $true)]
    [scriptblock]$Command
  )

  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code $LASTEXITCODE"
  }
}

if (-not (Test-Path ".venv")) {
  Invoke-Step { python -m venv .venv }
}

Invoke-Step { & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip }
Invoke-Step { & ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]" }
Invoke-Step { & ".\.venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm auto_arxiv_desktop.spec }

Write-Host ""
Write-Host "Build complete:"
Write-Host "  dist\auto_arxiv\auto_arxiv.exe"
Write-Host ""
Write-Host "Distribute the whole folder dist\auto_arxiv, not only the exe."
