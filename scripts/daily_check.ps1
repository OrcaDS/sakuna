# Daily DROMIC check, run by Windows Task Scheduler on the PC that holds raw/.
# DROMIC does not answer GitHub's servers (all requests timed out, 2026-11-26), so the check runs
# here: compare DROMIC with the latest release's report_files.csv and open or update one
# `new-reports` issue. Downloads no reports. Log: %LOCALAPPDATA%\sakuna\daily_check.log
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$work = Join-Path $env:LOCALAPPDATA 'sakuna'
New-Item -ItemType Directory -Force $work | Out-Null
Start-Transcript -Path (Join-Path $work 'daily_check.log') -Append | Out-Null
try {
    $known = Join-Path $work 'known'
    $out = Join-Path $work 'new_reports.md'
    Remove-Item $out -ErrorAction SilentlyContinue
    gh release download --pattern report_files.csv --dir $known --clobber
    if ($LASTEXITCODE -ne 0) { throw 'could not download report_files.csv from the latest release' }
    uv run sakuna check --known (Join-Path $known 'report_files.csv') --out $out
    if ($LASTEXITCODE -ne 0) { throw 'sakuna check failed (DROMIC down?)' }
    if (Test-Path $out) {
        gh label create new-reports --color FBCA04 --description 'New DROMIC reports' --force | Out-Null
        $n = gh issue list --label new-reports --state open --json number --jq '.[0].number'
        if ($n) { gh issue edit $n --body-file $out }
        else { gh issue create --title 'New DROMIC reports to add' --label new-reports --body-file $out }
    }
}
finally {
    Stop-Transcript | Out-Null
}
