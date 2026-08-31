[CmdletBinding()]
param(
    [ValidateSet("Install", "Status", "Start", "Stop", "Remove")]
    [string]$Action = "Status",
    [string]$SshHost = "sup.local",
    [int]$LocalPort = 8443
)

$ErrorActionPreference = "Stop"
$TaskName = "ToolShedDevelopmentTunnel"
$RemoteTarget = "192.168.7.5:8443"

function Get-TunnelTask {
    Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
}

if ($Action -eq "Status") {
    $task = Get-TunnelTask
    if (-not $task) {
        [pscustomobject]@{ Task = $TaskName; State = "NotInstalled"; LocalEndpoint = "http://127.0.0.1:$LocalPort" }
        exit 0
    }
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    [pscustomobject]@{
        Task = $TaskName
        State = [string]$task.State
        LastResult = $info.LastTaskResult
        LocalEndpoint = "http://127.0.0.1:$LocalPort"
        RemoteTarget = $RemoteTarget
    }
    exit 0
}

if ($Action -eq "Install") {
    $ssh = (Get-Command ssh.exe -ErrorAction Stop).Source
    $arguments = "-N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -L 127.0.0.1:${LocalPort}:${RemoteTarget} $SshHost"
    $taskAction = New-ScheduledTaskAction -Execute $ssh -Argument $arguments
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -MultipleInstances IgnoreNew `
        -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $taskAction `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Persistent localhost-only SSH tunnel to the LAN-only Tool Shed development site." `
        -Force | Out-Null
    Start-ScheduledTask -TaskName $TaskName
    Write-Output "Installed and started $TaskName at http://127.0.0.1:$LocalPort"
    exit 0
}

if (-not (Get-TunnelTask)) {
    throw "Scheduled task $TaskName is not installed."
}

switch ($Action) {
    "Start" { Start-ScheduledTask -TaskName $TaskName }
    "Stop" { Stop-ScheduledTask -TaskName $TaskName }
    "Remove" {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
}
