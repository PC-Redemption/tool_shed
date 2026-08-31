param(
    [Parameter(Mandatory = $true)]
    [string]$Workspace,
    [switch]$ObserveNaturalInterval,
    [int]$TimeoutSeconds = 1200
)

$ErrorActionPreference = "Stop"
$workspacePath = (Resolve-Path -LiteralPath $Workspace).Path
$scriptsPath = $PSScriptRoot
$reporterPath = Join-Path $scriptsPath "dashboard_reporter.py"
$identityPath = Join-Path $scriptsPath "project_identity.py"
$bootstrapPython = (Get-Command python.exe -ErrorAction Stop).Source

Add-Type -TypeDefinition @'
using System;
using System.Collections.Concurrent;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public static class ToolShedWindowObserver {
    private delegate void WinEventDelegate(IntPtr hook, uint eventType, IntPtr hwnd,
        int objectId, int childId, uint eventThread, uint eventTime);
    [StructLayout(LayoutKind.Sequential)] private struct POINT { public int X; public int Y; }
    [StructLayout(LayoutKind.Sequential)] private struct MSG {
        public IntPtr hwnd; public uint message; public UIntPtr wParam; public IntPtr lParam;
        public uint time; public POINT point;
    }
    [DllImport("user32.dll")] private static extern IntPtr SetWinEventHook(
        uint eventMin, uint eventMax, IntPtr module, WinEventDelegate callback,
        uint processId, uint threadId, uint flags);
    [DllImport("user32.dll")] private static extern bool UnhookWinEvent(IntPtr hook);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetClassName(
        IntPtr hwnd, StringBuilder className, int maxCount);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(
        IntPtr hwnd, out uint processId);
    [DllImport("user32.dll")] private static extern sbyte GetMessage(
        out MSG message, IntPtr hwnd, uint min, uint max);
    [DllImport("user32.dll")] private static extern bool PostThreadMessage(
        uint threadId, uint message, UIntPtr wParam, IntPtr lParam);
    [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
    [DllImport("kernel32.dll", SetLastError = true)] private static extern IntPtr OpenProcess(
        uint access, bool inheritHandle, uint processId);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool QueryFullProcessImageName(
        IntPtr process, uint flags, StringBuilder imageName, ref int size);
    [DllImport("kernel32.dll", SetLastError = true)] private static extern bool CloseHandle(IntPtr handle);

    private const uint EVENT_OBJECT_SHOW = 0x8002;
    private const uint WINEVENT_OUTOFCONTEXT = 0;
    private const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;
    private const int OBJID_WINDOW = 0;
    private const uint WM_QUIT = 0x0012;
    private static readonly ConcurrentQueue<string> Events = new ConcurrentQueue<string>();
    private static readonly ManualResetEvent Ready = new ManualResetEvent(false);
    private static WinEventDelegate Callback;
    private static Thread ObserverThread;
    private static uint ObserverThreadId;
    private static volatile string Phase = "setup";

    public static void SetPhase(string phase) { Phase = phase; }

    public static void Start() {
        string ignored;
        while (Events.TryDequeue(out ignored)) {}
        Ready.Reset();
        ObserverThread = new Thread(() => {
            ObserverThreadId = GetCurrentThreadId();
            Callback = Observe;
            IntPtr hook = SetWinEventHook(EVENT_OBJECT_SHOW, EVENT_OBJECT_SHOW, IntPtr.Zero,
                Callback, 0, 0, WINEVENT_OUTOFCONTEXT);
            if (hook == IntPtr.Zero) throw new InvalidOperationException("SetWinEventHook failed");
            Ready.Set();
            MSG message;
            while (GetMessage(out message, IntPtr.Zero, 0, 0) > 0) {}
            UnhookWinEvent(hook);
        });
        ObserverThread.IsBackground = true;
        ObserverThread.Start();
        if (!Ready.WaitOne(5000)) throw new TimeoutException("window observer did not start");
    }

    private static void Observe(IntPtr hook, uint eventType, IntPtr hwnd, int objectId,
        int childId, uint eventThread, uint eventTime) {
        if (hwnd == IntPtr.Zero || objectId != OBJID_WINDOW || childId != 0 || !IsWindowVisible(hwnd)) return;
        StringBuilder value = new StringBuilder(256);
        GetClassName(hwnd, value, value.Capacity);
        string className = value.ToString();
        if (className != "ConsoleWindowClass" && className != "CASCADIA_HOSTING_WINDOW_CLASS") return;
        uint processId;
        GetWindowThreadProcessId(hwnd, out processId);
        Events.Enqueue(DateTime.UtcNow.ToString("o") + "|" + Phase + "|" + processId + "|" +
            className + "|" + ProcessImage(processId));
    }

    private static string ProcessImage(uint processId) {
        IntPtr process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, processId);
        if (process == IntPtr.Zero) return "unavailable";
        try {
            int size = 1024;
            StringBuilder imageName = new StringBuilder(size);
            return QueryFullProcessImageName(process, 0, imageName, ref size)
                ? imageName.ToString() : "unavailable";
        } finally {
            CloseHandle(process);
        }
    }

    public static string[] Stop() {
        PostThreadMessage(ObserverThreadId, WM_QUIT, UIntPtr.Zero, IntPtr.Zero);
        ObserverThread.Join(5000);
        return Events.ToArray();
    }
}
'@

$identity = (& $bootstrapPython $identityPath --workspace $workspacePath identity --operation dashboard-report --json | ConvertFrom-Json)
$taskName = "ToolShedDashboardSafety-$($identity.project_id)"
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
$pythonw = ([string]$task.Actions[0].Execute).Trim('"')
if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) {
    throw "the scheduled dashboard task Python executable does not exist: $pythonw"
}
$python = Join-Path (Split-Path -Parent $pythonw) "python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "python.exe was not found beside the scheduled dashboard task executable: $python"
}
$statusBefore = (& $python $reporterPath --workspace $workspacePath --json status | ConvertFrom-Json)
if ($statusBefore.connection -ne "connected" -or -not $statusBefore.credential_present) {
    throw "dashboard reporter must be connected before qualification"
}

[ToolShedWindowObserver]::SetPhase("scheduled-safety")
[ToolShedWindowObserver]::Start()
$windowEvents = @()
$burstId = [guid]::NewGuid().ToString("N")
$burstPath = Join-Path ([System.IO.Path]::GetTempPath()) ("tool-shed-dashboard-burst-" + $burstId + ".py")
$burstPidPath = Join-Path ([System.IO.Path]::GetTempPath()) ("tool-shed-dashboard-burst-" + $burstId + ".pid")
$burstTaskName = "ToolShedDashboardBurst-$burstId"

try {
    $taskInfoBefore = Get-ScheduledTaskInfo -TaskName $taskName
    if ($ObserveNaturalInterval) {
        $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
        do {
            Start-Sleep -Milliseconds 500
            $taskInfoAfter = Get-ScheduledTaskInfo -TaskName $taskName
        } while ($taskInfoAfter.LastRunTime -le $taskInfoBefore.LastRunTime -and (Get-Date) -lt $deadline)
        do {
            Start-Sleep -Milliseconds 250
            $taskState = (Get-ScheduledTask -TaskName $taskName).State
            $taskInfoAfter = Get-ScheduledTaskInfo -TaskName $taskName
        } while (($taskState -eq "Running" -or $taskInfoAfter.LastTaskResult -eq 0x00041301) -and (Get-Date) -lt $deadline)
    } else {
        $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
        do {
            $taskState = (Get-ScheduledTask -TaskName $taskName).State
            $taskInfoBefore = Get-ScheduledTaskInfo -TaskName $taskName
            if ($taskState -eq "Running" -or $taskInfoBefore.LastTaskResult -eq 0x00041301) {
                Start-Sleep -Milliseconds 250
            }
        } while (($taskState -eq "Running" -or $taskInfoBefore.LastTaskResult -eq 0x00041301) -and (Get-Date) -lt $deadline)
        if ($taskState -eq "Running" -or $taskInfoBefore.LastTaskResult -eq 0x00041301) {
            throw "scheduled safety pass was still running at the qualification timeout"
        }
        Start-ScheduledTask -TaskName $taskName
        do {
            Start-Sleep -Milliseconds 250
            $taskInfoAfter = Get-ScheduledTaskInfo -TaskName $taskName
            $taskState = (Get-ScheduledTask -TaskName $taskName).State
        } while (($taskInfoAfter.LastRunTime -le $taskInfoBefore.LastRunTime -or $taskState -eq "Running" -or $taskInfoAfter.LastTaskResult -eq 0x00041301) -and (Get-Date) -lt $deadline)
    }
    if ($taskInfoAfter.LastRunTime -le $taskInfoBefore.LastRunTime) {
        throw "scheduled safety pass did not run before the qualification timeout"
    }
    if ($taskInfoAfter.LastTaskResult -ne 0) {
        throw "scheduled safety pass result was $($taskInfoAfter.LastTaskResult), expected 0"
    }

    [ToolShedWindowObserver]::SetPhase("managed-write-burst")
    $burstSource = @"
import sys
import os
from pathlib import Path
sys.path.insert(0, r'$($scriptsPath.Replace("'", "''"))')
import dashboard_reporter
workspace = Path(r'$($workspacePath.Replace("'", "''"))')
Path(r'$($burstPidPath.Replace("'", "''"))').write_text(str(os.getpid()), encoding='utf-8')
for _ in range(10):
    dashboard_reporter.enqueue_if_connected(workspace, reason='managed-update')
"@
    Set-Content -LiteralPath $burstPath -Value $burstSource -Encoding UTF8
    $burstAction = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$burstPath`""
    $burstPrincipal = New-ScheduledTaskPrincipal `
        -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
        -LogonType Interactive -RunLevel Limited
    $burstSettings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $burstTaskName -Action $burstAction `
        -Principal $burstPrincipal -Settings $burstSettings -Force | Out-Null
    Start-ScheduledTask -TaskName $burstTaskName
    $burstDeadline = (Get-Date).AddSeconds(60)
    do {
        Start-Sleep -Milliseconds 100
        $burstState = (Get-ScheduledTask -TaskName $burstTaskName).State
        $burstInfo = Get-ScheduledTaskInfo -TaskName $burstTaskName
    } while ((-not (Test-Path -LiteralPath $burstPidPath) -or $burstState -eq "Running" -or $burstInfo.LastTaskResult -eq 0x00041301) -and (Get-Date) -lt $burstDeadline)
    if (-not (Test-Path -LiteralPath $burstPidPath)) {
        throw "managed-write burst did not start within 60 seconds"
    }
    if ($burstState -eq "Running" -or $burstInfo.LastTaskResult -eq 0x00041301) {
        throw "managed-write burst did not exit within 60 seconds"
    }
    if ($burstInfo.LastTaskResult -ne 0) {
        throw "managed-write burst exited with $($burstInfo.LastTaskResult)"
    }
    $burstProcessId = [int](Get-Content -LiteralPath $burstPidPath -Raw)
    $workerProcesses = @(Get-CimInstance Win32_Process | Where-Object {
        $_.ParentProcessId -eq $burstProcessId -and
        $_.Name -like "python*.exe"
    })
    if ($workerProcesses.Count -ne 1) {
        throw "managed-write burst created $($workerProcesses.Count) persistent worker processes, expected 1"
    }

    [ToolShedWindowObserver]::SetPhase("report-delivery")
    $deliveryDeadline = (Get-Date).AddSeconds([Math]::Min($TimeoutSeconds, 300))
    do {
        $statusAfter = (& $python $reporterPath --workspace $workspacePath --json status | ConvertFrom-Json)
        if ($statusAfter.pending_events -eq 0) { break }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deliveryDeadline)
    if ($statusAfter.pending_events -ne 0) {
        throw "dashboard outbox did not drain after the managed-write burst"
    }
} finally {
    $windowEvents = @([ToolShedWindowObserver]::Stop())
    Unregister-ScheduledTask -TaskName $burstTaskName -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $burstPath,$burstPidPath -Force -ErrorAction SilentlyContinue
}

if ($windowEvents.Count -ne 0) {
    throw "visible console-class windows were observed: $($windowEvents -join ', ')"
}

[pscustomobject]@{
    schema_version = 1
    kind = "tool-shed-windows-dashboard-qualification"
    project_id = $identity.project_id
    task_name = $taskName
    natural_interval = [bool]$ObserveNaturalInterval
    task_result = $taskInfoAfter.LastTaskResult
    report_delivery = "outbox-drained"
    burst_enqueue_count = 10
    process_observation = "cim-parent-snapshot"
    persistent_worker_processes_started = $workerProcesses.Count
    visible_console_windows = $windowEvents.Count
    status = "passed"
} | ConvertTo-Json -Depth 4
