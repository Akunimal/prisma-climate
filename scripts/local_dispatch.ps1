# Owner-side daily dispatch for the two archive workflows.
#
# Runs `gh workflow run` for ingest.yml and observations.yml on branch main
# with the owner's existing gh login; both workflows are idempotent no-ops
# when the day is already archived. Each dispatch (or error) is appended as a
# timestamped line to a log file OUTSIDE the repository:
#   %LOCALAPPDATA%\prisma-climate\local_dispatch.log
#
# Registered as the scheduled task "PRISMA daily dispatch" (daily 10:00
# America/Argentina/Buenos_Aires, run-as-soon-as-possible when missed).
# No tokens, no passwords, nothing HF-related: gh authenticates itself.

$ErrorActionPreference = 'Continue'

$repo = 'Akunimal/prisma-climate'
$logDir = Join-Path $env:LOCALAPPDATA 'prisma-climate'
$logFile = Join-Path $logDir 'local_dispatch.log'

if (-not (Test-Path -LiteralPath $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

function Write-DispatchLog {
    param([string]$Line)
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    Add-Content -LiteralPath $logFile -Value ("{0} {1}" -f $stamp, $Line) -Encoding UTF8
}

foreach ($workflow in @('ingest.yml', 'observations.yml')) {
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    $output = gh workflow run $workflow --repo $repo --ref main 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) {
        Write-DispatchLog ("DISPATCH {0} queued" -f $workflow)
    }
    else {
        $detail = ($output -replace '\s+', ' ').Trim()
        Write-DispatchLog ("ERROR {0} exit={1} {2}" -f $workflow, $LASTEXITCODE, $detail)
    }
}
