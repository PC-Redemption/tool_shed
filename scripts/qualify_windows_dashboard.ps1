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
$python = (Get-Command python.exe -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path -Parent $python) "pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) {
    throw "pythonw.exe is required for Windows dashboard qualification"
}

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

    private const uint EVENT_OBJECT_SHOW = 0x8002;
    private const uint WINEVENT_OUTOFCONTEXT = 0;
    private const int OBJID_WINDOW = 0;
    private const uint WM_QUIT = 0x0012;
    private static readonly ConcurrentQueue<string> Events = new ConcurrentQueue<string>();
    private static readonly ManualResetEvent Ready = new ManualResetEvent(false);
    private static WinEventDelegate Callback;
    private static Thread ObserverThread;
    private static uint ObserverThreadId;

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
        Events.Enqueue(DateTime.UtcNow.ToString("o") + "|" + processId + "|" + className);
    }

    public static string[] Stop() {
        PostThreadMessage(ObserverThreadId, WM_QUIT, UIntPtr.Zero, IntPtr.Zero);
        ObserverThread.Join(5000);
        return Events.ToArray();
    }
}
'@

$identity = (& $python $identityPath --workspace $workspacePath identity --operation dashboard-report --json | ConvertFrom-Json)
$taskName = "ToolShedDashboardSafety-$($identity.project_id)"
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
$statusBefore = (& $python $reporterPath --workspace $workspacePath --json status | ConvertFrom-Json)
if ($statusBefore.connection -ne "connected" -or -not $statusBefore.credential_present) {
    throw "dashboard reporter must be connected before qualification"
}

[ToolShedWindowObserver]::Start()
$windowEvents = @()
$burstPath = Join-Path ([System.IO.Path]::GetTempPath()) ("tool-shed-dashboard-burst-" + [guid]::NewGuid() + ".py")

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
        } while ($taskState -eq "Running" -and (Get-Date) -lt $deadline)
    } else {
        Start-ScheduledTask -TaskName $taskName
        $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
        do {
            Start-Sleep -Milliseconds 250
            $taskInfoAfter = Get-ScheduledTaskInfo -TaskName $taskName
            $taskState = (Get-ScheduledTask -TaskName $taskName).State
        } while (($taskInfoAfter.LastRunTime -le $taskInfoBefore.LastRunTime -or $taskState -eq "Running") -and (Get-Date) -lt $deadline)
    }
    if ($taskInfoAfter.LastRunTime -le $taskInfoBefore.LastRunTime) {
        throw "scheduled safety pass did not run before the qualification timeout"
    }
    if ($taskInfoAfter.LastTaskResult -ne 0) {
        throw "scheduled safety pass result was $($taskInfoAfter.LastTaskResult), expected 0"
    }

    $burstSource = @"
import sys
from pathlib import Path
sys.path.insert(0, r'$($scriptsPath.Replace("'", "''"))')
import dashboard_reporter
workspace = Path(r'$($workspacePath.Replace("'", "''"))')
for _ in range(10):
    dashboard_reporter.enqueue_if_connected(workspace, reason='managed-update')
"@
    Set-Content -LiteralPath $burstPath -Value $burstSource -Encoding UTF8
    $burst = Start-Process -FilePath $pythonw -ArgumentList @("`"$burstPath`"") -PassThru -Wait
    if ($burst.ExitCode -ne 0) {
        throw "managed-write burst exited with $($burst.ExitCode)"
    }
    $workerProcesses = @(Get-CimInstance Win32_Process | Where-Object {
        $_.ParentProcessId -eq $burst.Id -and
        $_.Name -in @("python.exe", "pythonw.exe")
    })
    if ($workerProcesses.Count -ne 1) {
        throw "managed-write burst created $($workerProcesses.Count) persistent worker processes, expected 1"
    }

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
    Remove-Item -LiteralPath $burstPath -Force -ErrorAction SilentlyContinue
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
