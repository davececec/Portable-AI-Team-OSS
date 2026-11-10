# upgrade_carry.ps1 - Portable AI Team stable-path upgrade (V4.1).
#
# Usage:
#   powershell -File <new-capsule>\AI-Team\upgrade_carry.ps1 `
#     -NewVersion V4.1 -NewCapsulePath <new-capsule> -ProjectRoot <project-root>
#
# The current team always lives at <project-root>\Portable-AI-Team.
# The version is read from VERSION.json and AI-Team\team.json; it is never
# appended to the runtime path.
param(
    [Parameter(Mandatory)][string]$NewVersion,
    [string]$NewCapsulePath,
    [string]$ProjectRoot,
    [string]$OldVersion = '',
    [switch]$RemoveOld,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $PSCommandPath
$ScriptCapsule = Split-Path -Parent $Here
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$StableName = 'Portable-AI-Team'
$HistoryManifestRel = 'AI-Team\history\manifest.json'
$HistoryWorkspacesRel = 'AI-Team\history\workspaces'

function Say([string]$message) {
    Write-Host "[upgrade] $message"
}

function Fail([string]$message) {
    Write-Host "[upgrade] FAIL: $message"
    exit 2
}

function Read-Json([string]$path) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "JSON 文件不存在: $path"
    }
    return Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Normalize-Version([string]$value) {
    if (-not $value) { return '' }
    $parts = ($value.Trim().TrimStart('V', 'v')).Split('.')
    if ($parts.Count -lt 2 -or $parts.Count -gt 3) { return '' }
    if ($parts | Where-Object { $_ -notmatch '^\d+$' }) { return '' }
    if ($parts.Count -eq 2) { return "$($parts[0]).$($parts[1]).0" }
    return "$($parts[0]).$($parts[1]).$($parts[2])"
}

function Assert-CapsuleVersion([string]$capsuleRoot, [string]$expectedVersion) {
    $teamPath = Join-Path $capsuleRoot 'AI-Team\team.json'
    $versionPath = Join-Path $capsuleRoot 'VERSION.json'
    $team = Read-Json $teamPath
    $release = Read-Json $versionPath
    $teamVersion = [string]$team.team_version
    $releaseVersion = [string]$release.team_version
    if ($teamVersion -ne $expectedVersion) {
        throw "来源 team.json 版本为 $teamVersion，期望 $expectedVersion"
    }
    if ($releaseVersion -ne $teamVersion) {
        throw "来源 VERSION.json=$releaseVersion 与 team.json=$teamVersion 不一致"
    }
    if ([string]$release.capsule_id -ne [string]$team.capsule_id) {
        throw "来源 VERSION.json 与 team.json 的记忆谱系 ID 不一致"
    }
    $aliases = @(Get-ChildItem -LiteralPath $capsuleRoot -Filter 'VERSION_V*.json' -File -ErrorAction SilentlyContinue)
    if ($aliases.Count -eq 0) {
        throw "来源缺少 VERSION_V<版本>.json 展示副本"
    }
    foreach ($alias in $aliases) {
        $aliasData = Read-Json $alias.FullName
        if ([string]$aliasData.team_version -ne $teamVersion) {
            throw "$($alias.Name) 版本为 $($aliasData.team_version)，与 team.json=$teamVersion 不一致"
        }
    }
    return [pscustomobject]@{ Team = $team; Release = $release }
}

function Find-ProjectRoot([string]$start) {
    $path = (Resolve-Path -LiteralPath $start).Path
    while ($path) {
        if (Test-Path -LiteralPath (Join-Path $path '.portable-ai-team.json')) { return $path }
        if (Test-Path -LiteralPath (Join-Path $path '.git')) { return $path }
        if ((Test-Path -LiteralPath (Join-Path $path 'AGENTS.md')) -and
            ((Test-Path -LiteralPath (Join-Path $path '.agents')) -or
             (Test-Path -LiteralPath (Join-Path $path '.codex')))) { return $path }
        $parent = Split-Path -Parent $path
        if (-not $parent -or $parent -eq $path) { break }
        $path = $parent
    }
    return $null
}

function Find-CapsuleInContainer([string]$container) {
    $candidates = @(
        (Join-Path $container 'AI-Team'),
        (Join-Path $container 'dist\Portable-AI-Team\AI-Team'),
        (Join-Path $container 'Portable-AI-Team\AI-Team')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Container) {
            return (Resolve-Path -LiteralPath (Split-Path -Parent $candidate)).Path
        }
    }
    return $null
}

function Find-CurrentCapsule([string]$root) {
    $markerPath = Join-Path $root '.portable-ai-team.json'
    if (Test-Path -LiteralPath $markerPath -PathType Leaf) {
        $marker = Read-Json $markerPath
        if ($marker.capsule_rel) {
            $fromMarker = Join-Path $root ([string]$marker.capsule_rel).Replace('/', '\')
            if (Test-Path -LiteralPath (Join-Path $fromMarker 'AI-Team') -PathType Container) {
                return [pscustomobject]@{
                    Capsule = (Resolve-Path -LiteralPath $fromMarker).Path
                    Source = '项目标记'
                }
            }
        }
    }

    $stable = Join-Path $root $StableName
    if (Test-Path -LiteralPath (Join-Path $stable 'AI-Team') -PathType Container) {
        return [pscustomobject]@{
            Capsule = (Resolve-Path -LiteralPath $stable).Path
            Source = '稳定路径'
        }
    }

    $legacy = @(
        Get-ChildItem -LiteralPath $root -Directory -Filter 'Portable-AI-TeamV*' -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending
    )
    foreach ($folder in $legacy) {
        $capsule = Find-CapsuleInContainer $folder.FullName
        if ($capsule) {
            return [pscustomobject]@{
                Capsule = $capsule
                Source = '旧式版本目录'
            }
        }
    }
    return $null
}

function Copy-LocalStateIfMissing([string]$sourceRoot, [string]$targetRoot, [string]$relative, [string]$label) {
    $source = Join-Path $sourceRoot $relative
    $target = Join-Path $targetRoot $relative
    if ((Test-Path -LiteralPath $source -PathType Leaf) -and
        -not (Test-Path -LiteralPath $target -PathType Leaf)) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $source -Destination $target -Force
        Say "已继承${label}: $target"
    }
}

function Copy-FullTree([string]$source, [string]$destination, [string]$excludeDirectory = '') {
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    if ($excludeDirectory) {
        robocopy $source $destination /E /XD $excludeDirectory /NFL /NDL /NJH /NJS | Out-Null
    }
    else {
        robocopy $source $destination /E /NFL /NDL /NJH /NJS | Out-Null
    }
    if ($LASTEXITCODE -ge 8) {
        throw "复制历史目录失败: $source -> $destination (robocopy exit $LASTEXITCODE)"
    }
}

function Get-SafeSnapshotName([string]$value) {
    $safe = $value.Trim().TrimStart('.').Trim()
    $safe = [regex]::Replace($safe, '[^0-9A-Za-z._-]', '_')
    if (-not $safe) { return 'workspace' }
    return $safe
}

function Read-CapsuleVersion([string]$container) {
    $candidates = @(
        (Join-Path $container 'VERSION.json'),
        (Join-Path $container 'AI-Team\team.json'),
        (Join-Path $container 'dist\Portable-AI-Team\VERSION.json'),
        (Join-Path $container 'dist\Portable-AI-Team\AI-Team\team.json')
    )
    foreach ($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        try {
            $data = Read-Json $candidate
            if ($data.team_version) { return [string]$data.team_version }
        }
        catch {
            continue
        }
    }
    return ''
}

function Read-HistoryEntries([string]$capsuleRoot) {
    $manifestPath = Join-Path $capsuleRoot $HistoryManifestRel
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { return @() }
    $data = Read-Json $manifestPath
    return @($data.workspaces | Where-Object { $_ -and $_.snapshot })
}

function Add-WorkspaceSnapshot(
    [string]$source,
    [string]$stagingCapsule,
    [string]$label,
    [string]$version,
    [string]$kind,
    [string]$stamp
) {
    if (-not (Test-Path -LiteralPath $source -PathType Container)) { return $null }
    $workspacesRoot = Join-Path $stagingCapsule $HistoryWorkspacesRel
    New-Item -ItemType Directory -Force -Path $workspacesRoot | Out-Null
    $baseName = Get-SafeSnapshotName $label
    $snapshotName = $baseName
    $destination = Join-Path $workspacesRoot $snapshotName
    if (Test-Path -LiteralPath $destination) {
        $snapshotName = "$baseName-$stamp"
        $destination = Join-Path $workspacesRoot $snapshotName
    }

    $nestedHistory = Join-Path $source 'AI-Team\history'
    Copy-FullTree $source $destination $nestedHistory
    $files = @(Get-ChildItem -LiteralPath $destination -Recurse -File -Force -ErrorAction SilentlyContinue)
    $bytes = 0
    if ($files.Count -gt 0) {
        $bytes = [int64](($files | Measure-Object -Property Length -Sum).Sum)
    }
    $snapshotRel = "$HistoryWorkspacesRel\$snapshotName".Replace('\', '/')
    Say "历史快照已保存: $snapshotRel ($($files.Count) 个文件)"
    return [pscustomobject][ordered]@{
        snapshot = $snapshotRel
        source = (Resolve-Path -LiteralPath $source).Path
        version = $version
        kind = $kind
        copied_at = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        files = $files.Count
        bytes = $bytes
    }
}

function Get-TopLevelContainer([string]$root, [string]$capsule) {
    $prefix = $root.TrimEnd('\') + '\'
    $fullCapsule = (Resolve-Path -LiteralPath $capsule).Path
    if (-not $fullCapsule.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "当前胶囊不在项目根目录内: $fullCapsule"
    }
    $relative = $fullCapsule.Substring($prefix.Length)
    $parts = $relative.Split([char[]]@('\', '/'))
    if ($parts.Count -lt 1) { throw "无法解析当前胶囊的顶层容器: $relative" }
    $container = Join-Path $root $parts[0]
    return (Resolve-Path -LiteralPath $container).Path
}

if ($ProjectRoot) {
    if (-not (Test-Path -LiteralPath $ProjectRoot -PathType Container)) {
        Fail "指定的项目根不存在或不是目录: $ProjectRoot"
    }
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
}
else {
    $ProjectRoot = Find-ProjectRoot $ScriptCapsule
}
if (-not $ProjectRoot) {
    Fail "无法定位业务项目根（向上未找到 .portable-ai-team.json / .git / AGENTS.md + .agents）"
}

if (-not $NewCapsulePath) { $NewCapsulePath = $ScriptCapsule }
if (-not (Test-Path -LiteralPath $NewCapsulePath -PathType Container)) {
    Fail "新胶囊路径不存在: $NewCapsulePath"
}
$SourceCapsule = (Resolve-Path -LiteralPath $NewCapsulePath).Path
if (-not (Test-Path -LiteralPath (Join-Path $SourceCapsule 'AI-Team') -PathType Container)) {
    Fail "新胶囊路径不含 AI-Team: $SourceCapsule"
}

$RequestedVersion = Normalize-Version $NewVersion
if (-not $RequestedVersion) { Fail "版本参数无效: $NewVersion" }
try {
    $NewIdentity = Assert-CapsuleVersion $SourceCapsule $RequestedVersion
}
catch {
    Fail $_.Exception.Message
}
$NewTeam = $NewIdentity.Team

$Current = Find-CurrentCapsule $ProjectRoot
if (-not $Current) { Fail "未找到当前团队：项目标记、$StableName 或旧式版本目录均无有效胶囊" }
$OldCapsule = $Current.Capsule
$OldTeam = Read-Json (Join-Path $OldCapsule 'AI-Team\team.json')
$OldTeamVersion = [string]$OldTeam.team_version
$OldContainer = Get-TopLevelContainer $ProjectRoot $OldCapsule
$OldContainerName = Split-Path -Leaf $OldContainer
$TargetCapsule = Join-Path $ProjectRoot $StableName

if ($OldCapsule -eq $SourceCapsule) {
    Fail "来源胶囊就是当前团队，不能原地执行升级。请从外部母版或独立新版目录运行。"
}

Say "项目根: $ProjectRoot"
Say "当前胶囊: $OldCapsule ($($Current.Source))"
Say "新胶囊来源: $SourceCapsule"
Say "稳定目标: $TargetCapsule"
Say "版本: $OldTeamVersion -> $($NewTeam.team_version)"
if ($OldVersion) {
    Say "兼容参数 OldVersion=$OldVersion 已忽略；当前版本以旧 team.json 为准"
}
if ($RemoveOld) {
    Say "兼容参数 RemoveOld 已忽略；旧当前目录始终归档保留"
}

$snapshotCandidates = @(
    [pscustomobject]@{
        Path = $OldContainer
        Version = $OldTeamVersion
        Kind = 'current'
        Label = if ($OldContainerName -eq $StableName) { "$StableName-V$OldTeamVersion" } else { $OldContainerName }
    }
)
$knownSnapshotSources = @{}
$knownSnapshotSources[$OldContainerName.ToLowerInvariant()] = $true
$legacyCandidates = @(
    Get-ChildItem -LiteralPath $ProjectRoot -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like 'Portable-AI-TeamV*' -or
            $_.Name -like '.archive-Portable-AI-Team*'
        }
)
foreach ($candidate in $legacyCandidates) {
    $key = $candidate.Name.ToLowerInvariant()
    if ($knownSnapshotSources.ContainsKey($key)) { continue }
    $knownSnapshotSources[$key] = $true
    $snapshotCandidates += [pscustomobject]@{
        Path = $candidate.FullName
        Version = (Read-CapsuleVersion $candidate.FullName)
        Kind = if ($candidate.Name.StartsWith('.archive-')) { 'archive' } else { 'legacy' }
        Label = $candidate.Name
    }
}

if ($DryRun) {
    Say "DRY RUN：归档当前顶层容器 $OldContainer"
    Say "DRY RUN：从 $OldCapsule 继承团队状态、安装清单、记忆状态、LLM 配置、凭据和记忆账本"
    Say "DRY RUN：将 $($snapshotCandidates.Count) 个完整工作区快照写入 $HistoryWorkspacesRel（含工单、dist、.git 和缓存）"
    Say "DRY RUN：把新版放入稳定目录 $TargetCapsule"
    Say "DRY RUN：备份桥接并运行 enable --project --force"
    Say "DRY RUN：运行 doctor 并写入 upgrade_history"
    exit 0
}

$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackupDir = Join-Path $ProjectRoot ".upgrade-backup-$Stamp"
$StagingRoot = Join-Path $ProjectRoot ".upgrade-staging-$Stamp"
$StagingCapsule = Join-Path $StagingRoot $StableName
$Archive = Join-Path $ProjectRoot ".archive-$OldContainerName-$Stamp"
$BridgeRel = @(
    'AGENTS.md', 'CLAUDE.md', '.portable-ai-team.json',
    '.agents\rules\portable-ai-team.md',
    '.agents\agents\agent-b\agent.md',
    '.agents\agents\agent-c\agent.md',
    '.agents\agents\agent-d\agent.md',
    '.trae\rules\portable-ai-team.md',
    '.workbuddy\rules\portable-ai-team.md',
    '.codex\agents\agent-b.toml',
    '.codex\agents\agent-c.toml',
    '.codex\agents\agent-d.toml'
)
$OldMoved = $false
$NewMoved = $false

try {
    if (Test-Path -LiteralPath $StagingRoot) { throw "暂存目录已存在: $StagingRoot" }
    if (Test-Path -LiteralPath $Archive) { throw "归档目录已存在: $Archive" }

    # 1) Build the complete next team in staging, excluding disposable runtime state.
    New-Item -ItemType Directory -Force -Path $StagingCapsule | Out-Null
    robocopy $SourceCapsule $StagingCapsule /E `
        /XD state __pycache__ .pytest_cache .git `
        /XF 'LLM配置.json' 'credentials.md' '记忆账本.json' `
        /NFL /NDL /NJH /NJS | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "复制新胶囊失败 (robocopy exit $LASTEXITCODE)" }
    Say "新版已复制到暂存目录"

    # 2) Carry local state and private configuration by default.
    Copy-LocalStateIfMissing $OldCapsule $StagingCapsule '团队状态.json' '团队状态'
    Copy-LocalStateIfMissing $OldCapsule $StagingCapsule 'state\installation.json' '安装清单'
    Copy-LocalStateIfMissing $OldCapsule $StagingCapsule 'state\memory.json' '记忆修订状态'
    Copy-LocalStateIfMissing $OldCapsule $StagingCapsule 'LLM配置.json' '本地 LLM 配置'
    Copy-LocalStateIfMissing $OldCapsule $StagingCapsule 'AI-Team\memory\credentials.md' '本地凭据'
    Copy-LocalStateIfMissing $OldCapsule $StagingCapsule 'AI-Team\memory\记忆账本.json' '记忆账本'

    # 3) Merge prior history, then snapshot every complete workspace before the
    # runtime entity is replaced. Legacy directories are immutable sources.
    $stagingWorkspaces = Join-Path $StagingCapsule $HistoryWorkspacesRel
    New-Item -ItemType Directory -Force -Path $stagingWorkspaces | Out-Null
    $oldWorkspaces = Join-Path $OldCapsule $HistoryWorkspacesRel
    if (Test-Path -LiteralPath $oldWorkspaces -PathType Container) {
        Copy-FullTree $oldWorkspaces $stagingWorkspaces
        Say "已合并旧团队历史区: $oldWorkspaces"
    }
    $historyEntries = @()
    $seenSnapshots = @{}
    foreach ($entry in @((Read-HistoryEntries $SourceCapsule) + (Read-HistoryEntries $OldCapsule))) {
        $snapshotKey = ([string]$entry.snapshot).ToLowerInvariant()
        if (-not $snapshotKey -or $seenSnapshots.ContainsKey($snapshotKey)) { continue }
        $seenSnapshots[$snapshotKey] = $true
        $historyEntries += $entry
    }
    foreach ($candidate in $snapshotCandidates) {
        $entry = Add-WorkspaceSnapshot `
            -source $candidate.Path `
            -stagingCapsule $StagingCapsule `
            -label $candidate.Label `
            -version $candidate.Version `
            -kind $candidate.Kind `
            -stamp $Stamp
        if ($entry) {
            $snapshotKey = ([string]$entry.snapshot).ToLowerInvariant()
            if (-not $seenSnapshots.ContainsKey($snapshotKey)) {
                $seenSnapshots[$snapshotKey] = $true
                $historyEntries += $entry
            }
        }
    }
    $historyManifestPath = Join-Path $StagingCapsule $HistoryManifestRel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $historyManifestPath) | Out-Null
    $historyManifest = [ordered]@{
        schema = 1
        updated_at = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        workspaces = @($historyEntries)
    }
    [IO.File]::WriteAllText(
        $historyManifestPath,
        ($historyManifest | ConvertTo-Json -Depth 10),
        $Utf8
    )
    Say "完整历史清单已写入: $historyManifestPath"

    # 4) Back up every managed bridge before touching the project.
    foreach ($relative in $BridgeRel) {
        $source = Join-Path $ProjectRoot $relative
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }
        $target = Join-Path $BackupDir $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $source -Destination $target -Force
    }
    Say "桥接已备份: $BackupDir"

    # 5) Archive the current top-level container, then install the stable path.
    Move-Item -LiteralPath $OldContainer -Destination $Archive
    $OldMoved = $true
    Say "旧当前容器已归档: $Archive"
    $marker = Join-Path $Archive "UPGRADED_TO_V$($NewTeam.team_version).md"
    $markerText = @"
# Archived after upgrade to V$($NewTeam.team_version)

- Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
- Replaced by: $TargetCapsule
- Reason: runtime paths must remain stable at Portable-AI-Team/.
"@
    [IO.File]::WriteAllText($marker, $markerText, $Utf8)

    if (Test-Path -LiteralPath $TargetCapsule) {
        throw "归档后稳定目标仍存在: $TargetCapsule"
    }
    Move-Item -LiteralPath $StagingCapsule -Destination $TargetCapsule
    $NewMoved = $true
    if (Test-Path -LiteralPath $StagingRoot -PathType Container) {
        Remove-Item -LiteralPath $StagingRoot -Force -ErrorAction SilentlyContinue
    }
    Say "新版已就位: $TargetCapsule"

    # 6) Re-render bridges and run independent health checks.
    $pythonConfig = Join-Path $TargetCapsule 'Python路径.txt'
    $python = 'python'
    if (Test-Path -LiteralPath $pythonConfig -PathType Leaf) {
        $configured = (Get-Content -LiteralPath $pythonConfig -TotalCount 1 -Encoding UTF8).Trim()
        if ($configured) { $python = $configured }
    }
    try {
        $python = (Get-Command $python -ErrorAction Stop).Source
    } catch {
        throw "Python 不存在: $python（请在胶囊根目录创建 Python路径.txt 指向本机解释器）"
    }

    & $python (Join-Path $TargetCapsule 'AI-Team\capsule.py') enable --project $ProjectRoot --python $python --force
    if ($LASTEXITCODE -ne 0) { throw "新版 enable 失败 (exit $LASTEXITCODE)" }
    Say "新版 enable 完成"

    & $python (Join-Path $TargetCapsule 'AI-Team\capsule.py') doctor --project $ProjectRoot --python $python
    if ($LASTEXITCODE -ne 0) { throw "doctor 体检未通过 (exit $LASTEXITCODE)" }
    Say "doctor 体检通过"

    # 7) Record the migration without changing bridge paths.
    $statusPath = Join-Path $TargetCapsule '团队状态.json'
    $state = Read-Json $statusPath
    $entry = [ordered]@{
        from_version = $OldTeamVersion
        to_version = [string]$NewTeam.team_version
        from_dir = $OldContainerName
        to_dir = $StableName
        at = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        bridges = $BridgeRel.Count
        backup = $BackupDir
        archived_to = $Archive
        path_contract = 'stable'
        history_manifest = $HistoryManifestRel.Replace('\', '/')
        history_snapshots = $historyEntries.Count
        status = 'ok'
    }
    $history = @()
    if ($state.PSObject.Properties.Name -contains 'upgrade_history' -and $state.upgrade_history) {
        $history = @($state.upgrade_history)
    }
    $history += [pscustomobject]$entry
    $state | Add-Member -NotePropertyName upgrade_history -NotePropertyValue $history -Force
    $state | Add-Member -NotePropertyName team_version -NotePropertyValue ([string]$NewTeam.team_version) -Force
    [IO.File]::WriteAllText($statusPath, ($state | ConvertTo-Json -Depth 10), $Utf8)
    Say "upgrade_history 已写入: $statusPath"

    Say "升级完成: $($NewTeam.team_version)，桥接路径保持 Portable-AI-Team"
    exit 0
}
catch {
    $message = $_.Exception.Message
    Say "升级失败: $message"
    if ($message -match 'Access to the path' -and $message -match 'denied') {
        Say "目录被占用：请关闭打开当前胶囊目录的资源管理器窗口后重试。"
    }

    if (Test-Path -LiteralPath $BackupDir) {
        foreach ($relative in $BridgeRel) {
            $backup = Join-Path $BackupDir $relative
            if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) { continue }
            $target = Join-Path $ProjectRoot $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
            Copy-Item -LiteralPath $backup -Destination $target -Force
        }
        Say "桥接已从备份还原"
    }

    if ($NewMoved -and (Test-Path -LiteralPath $TargetCapsule)) {
        $failedDir = Join-Path $ProjectRoot ".failed-upgrade-$Stamp"
        Move-Item -LiteralPath $TargetCapsule -Destination $failedDir
        Say "失败的新版已移到: $failedDir"
    }
    elseif (Test-Path -LiteralPath $StagingRoot) {
        $failedDir = Join-Path $ProjectRoot ".failed-upgrade-$Stamp"
        Move-Item -LiteralPath $StagingRoot -Destination $failedDir
        Say "失败的暂存目录已移到: $failedDir"
    }

    if ($OldMoved -and (Test-Path -LiteralPath $Archive) -and
        -not (Test-Path -LiteralPath $OldContainer)) {
        Move-Item -LiteralPath $Archive -Destination $OldContainer
        Say "旧当前容器已恢复: $OldContainer"
    }
    exit 3
}
