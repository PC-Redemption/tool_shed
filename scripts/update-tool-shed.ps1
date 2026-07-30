$ErrorActionPreference = "Stop"
$Updater = Join-Path $PSScriptRoot "update_snapshot.py"

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $Updater @args
    exit $LASTEXITCODE
}
if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $Updater @args
    exit $LASTEXITCODE
}
throw "Tool Shed requires Python 3."
