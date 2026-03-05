param(
  [Parameter(Mandatory = $false)]
  [string]$CompanyName,

  [Parameter(Mandatory = $false)]
  [string]$Objective,

  [Parameter(Mandatory = $false)]
  [int]$MaxUrls = 0
)

$ErrorActionPreference = "Stop"

function Get-RootDir {
  Split-Path -Parent $MyInvocation.MyCommand.Path
}

function Get-VenvPython([string]$RootDir) {
  $venvDir = Join-Path $RootDir ".venv"
  $py = Join-Path $venvDir "Scripts\\python.exe"
  if (-not (Test-Path $py)) {
    throw "Virtual environment not found at: $venvDir. Please run the setup steps in the README first."
  }
  return $py
}

$root = $PSScriptRoot
$pythonExe = Get-VenvPython $root

if (-not $CompanyName) {
  $CompanyName = Read-Host "Enter the company name"
}
if (-not $Objective) {
  $Objective = Read-Host "Enter the objective prompt"
}

# Make src layout importable
$srcPath = Join-Path $root "src"
if ($env:PYTHONPATH) {
  $env:PYTHONPATH = "$srcPath;$($env:PYTHONPATH)"
} else {
  $env:PYTHONPATH = $srcPath
}

$argsList = @("--company", $CompanyName, "--objective", $Objective)
if ($MaxUrls -gt 0) {
  $argsList += @("--max-urls", "$MaxUrls")
}

& $pythonExe -m airadar.cli_entrypoint @argsList
exit $LASTEXITCODE

