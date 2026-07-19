# Run main.py hidden via PowerShell, capturing output to log
$logFile = "C:\PK\Projects\sbpdcl-monitor\logs\task_scheduler.log"
$python = "C:\PK\Projects\sbpdcl-monitor\.venv\Scripts\python.exe"
$script = "C:\PK\Projects\sbpdcl-monitor\main.py"

# Write header
"(" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + ") Task started" | Out-File -FilePath $logFile -Append -Encoding utf8

# Run python hidden, capture output
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $python
$psi.Arguments = "`"$script`""
$psi.WorkingDirectory = "C:\PK\Projects\sbpdcl-monitor"
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true

$proc = [System.Diagnostics.Process]::Start($psi)

# Stream stdout
$stdoutTask = $proc.StandardOutput.ReadToEndAsync()
# Stream stderr
$stderrTask = $proc.StandardError.ReadToEndAsync()

$proc.WaitForExit()

$stdout = $stdoutTask.Result
$stderr = $stderrTask.Result

if ($stdout) { $stdout | Out-File -FilePath $logFile -Append -Encoding utf8 }
if ($stderr) { $stderr | Out-File -FilePath $logFile -Append -Encoding utf8 }

"(" + (Get-Date -Format "yyyy-MM-dd HH:mm:ss") + ") Task finished with exit code: $($proc.ExitCode)" | Out-File -FilePath $logFile -Append -Encoding utf8
"" | Out-File -FilePath $logFile -Append -Encoding utf8
