$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Installer = Join-Path $ScriptDir "scripts\install_tool_shed_from_github.py"

function Test-PythonCandidate {
    param([string[]]$CommandParts)

    $exe = $CommandParts[0]
    $rest = @()
    if ($CommandParts.Length -gt 1) {
        $rest = $CommandParts[1..($CommandParts.Length - 1)]
    }
    & $exe @rest -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 8) else 1)" *> $null
    return $LASTEXITCODE -eq 0
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    if (Test-PythonCandidate @("py", "-3")) {
        & py -3 $Installer @args
        exit $LASTEXITCODE
    }
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    if (Test-PythonCandidate @("python")) {
        & python $Installer @args
        exit $LASTEXITCODE
    }
}

if (Get-Command python3 -ErrorAction SilentlyContinue) {
    if (Test-PythonCandidate @("python3")) {
        & python3 $Installer @args
        exit $LASTEXITCODE
    }
}

Write-Error "Tool Shed install requires Python 3. Install Python or add py/python/python3 to PATH."
exit 1
