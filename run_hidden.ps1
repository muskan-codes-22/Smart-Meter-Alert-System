# Run main.py hidden via PowerShell, capturing output to log
$logFile = "C:\PK\Projects\sbpdcl-monitor\logs\task_scheduler.log"
$python = "C:\PK\Projects\sbpdcl-monitor\.venv\Scripts\python.exe"
$script = "C:\PK\Projects\sbpdcl-monitor\main.py"

function Strip-Ansi {
    param([string]$text)
    return $text -replace '\x1b\[[0-9;]*m', ''
}

function Write-Log {
    param([string]$message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] $message" | Out-File -FilePath $logFile -Append -Encoding utf8
}

# Ensure log directory exists
$logDir = Split-Path $logFile -Parent
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

# Header
"=" * 60 | Out-File -FilePath $logFile -Append -Encoding utf8
Write-Log "SBPDCL Monitor - Task Started"
Write-Log "Script: $script"
"=" * 60 | Out-File -FilePath $logFile -Append -Encoding utf8

$startTime = Get-Date

# Run python hidden, capture output line-by-line
$env:SBPDCL_TASK_SCHEDULER = "1"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $python
$psi.Arguments = "`"$script`""
$psi.WorkingDirectory = "C:\PK\Projects\sbpdcl-monitor"
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true

$proc = [System.Diagnostics.Process]::Start($psi)

# Stream stdout line-by-line (logger + print both go to stdout now)
while (-not $proc.StandardOutput.EndOfStream) {
    $line = $proc.StandardOutput.ReadLine()
    $clean = Strip-Ansi $line
    if ($clean) { Write-Log $clean }
}

$proc.WaitForExit()

$endTime = Get-Date
$duration = ($endTime - $startTime).TotalSeconds

# Footer
"=" * 60 | Out-File -FilePath $logFile -Append -Encoding utf8
Write-Log "Task Finished | Exit Code: $($proc.ExitCode) | Duration: $([math]::Round($duration, 1))s"
"=" * 60 | Out-File -FilePath $logFile -Append -Encoding utf8
"" | Out-File -FilePath $logFile -Append -Encoding utf8
