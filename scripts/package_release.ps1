$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

if (-not (Test-Path "dist\auto_arxiv\auto_arxiv.exe")) {
  & ".\scripts\build_exe.ps1"
}

$runtimePaths = @(
  "dist\auto_arxiv\config.toml",
  "dist\auto_arxiv\profiles.json",
  "dist\auto_arxiv\data",
  "dist\auto_arxiv\downloads",
  "dist\auto_arxiv\recommendations"
)
foreach ($path in $runtimePaths) {
  if (Test-Path -LiteralPath $path) {
    Remove-Item -LiteralPath $path -Recurse -Force
  }
}

if (Test-Path "release") {
  Remove-Item -LiteralPath "release" -Recurse -Force
}
New-Item -ItemType Directory -Path "release" | Out-Null

$zipPath = "release\auto_arxiv-windows-x64.zip"
Compress-Archive -Path "dist\auto_arxiv\*" -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "Release package complete:"
Write-Host "  $zipPath"
Write-Host ""
Write-Host "Upload this zip to GitHub Releases."
