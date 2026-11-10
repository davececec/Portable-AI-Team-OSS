# Sync this project capsule's team experience to the master capsule.
# Safe by design: backs up the master first, then pushes incrementally.
# Never deletes anything from the master; never syncs per-project state.
$ErrorActionPreference = 'Stop'

$capsuleRoot = Split-Path -Parent $PSScriptRoot
$masterPathFile = Join-Path $PSScriptRoot 'master_path.txt'
if (-not (Test-Path -LiteralPath $masterPathFile)) {
    Write-Host "[FAIL] master_path.txt not found in AI-Team folder"
    exit 2
}
$master = (Get-Content -LiteralPath $masterPathFile -TotalCount 1).Trim()
if (-not $master -or -not (Test-Path -LiteralPath $master)) {
    Write-Host "[FAIL] master folder not found: $master"
    exit 2
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
$backupRoot = Join-Path (Split-Path -Parent $master) ((Split-Path -Leaf $master) + '-backup')
$backup = Join-Path $backupRoot $stamp
New-Item -ItemType Directory -Force -Path $backup | Out-Null
robocopy $master $backup /E /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Host "[FAIL] master backup failed (robocopy exit $LASTEXITCODE)"
    exit 3
}

# Push incrementally. Excluded: per-project state, carry ledger, legacy
# top-level capsule tickets, build artifacts and caches. Master files are
# never deleted. Project work orders are copied in a second pass because
# project-docs/<project-id>/tasks/ must remain in the reusable archive.
$aiSrc = Join-Path $capsuleRoot 'AI-Team'
# Exclude by directory NAME: robocopy /XD does not reliably match
# absolute paths, but name matching is dependable.
$excludeDirs = @('dist', '__pycache__', 'tasks', 'history', 'merge-inbox', '.git')
robocopy $capsuleRoot $master /E /XF '团队状态.json' '记忆账本.json' /XD $excludeDirs /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Host "[FAIL] push failed (robocopy exit $LASTEXITCODE)"
    exit 4
}

$projectDocs = Join-Path $aiSrc 'project-docs'
$masterProjectDocs = Join-Path $master 'AI-Team\project-docs'
robocopy $projectDocs $masterProjectDocs /E /XF '团队状态.json' '记忆账本.json' /XD 'dist' '__pycache__' 'merge-inbox' '.git' /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Host "[FAIL] project-docs push failed (robocopy exit $LASTEXITCODE)"
    exit 5
}

Write-Host "[OK] capsule synced to master: $master"
Write-Host "[OK] backup: $backup"
exit 0
