param(
    [string]$Distro = "Ubuntu-22.04",
    [string]$ProjectLinuxPath = "/home/yjh/projects/soulmate",
    [string]$BackupRoot = "",
    [switch]$SkipWslExport,
    [switch]$SkipProjectArchive,
    [switch]$SkipDbBackup,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($BackupRoot)) {
    $BackupRoot = Join-Path $env:USERPROFILE "SoulMateBackups"
}

function Write-Step([string]$Message) {
    Write-Host ("`n== {0} ==" -f $Message) -ForegroundColor Cyan
}

function Invoke-Checked([scriptblock]$Action, [string]$ErrorMessage) {
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw $ErrorMessage
    }
}

function Convert-LinuxPathToWslUnc([string]$DistroName, [string]$LinuxPath) {
    $normalized = $LinuxPath.Replace("\", "/").Trim()
    if (-not $normalized.StartsWith("/")) {
        throw "Linux path must start with '/': $LinuxPath"
    }

    $relative = $normalized.TrimStart("/").Replace("/", "\")
    if ([string]::IsNullOrWhiteSpace($relative)) {
        return "\\wsl$\$DistroName"
    }
    return "\\wsl$\$DistroName\$relative"
}

function Split-LinuxPath([string]$LinuxPath) {
    $normalized = $LinuxPath.Replace("\", "/").TrimEnd("/")
    if (-not $normalized.StartsWith("/")) {
        throw "Linux path must start with '/': $LinuxPath"
    }
    $idx = $normalized.LastIndexOf("/")
    if ($idx -lt 1) {
        throw "Invalid project path: $LinuxPath"
    }
    $parent = $normalized.Substring(0, $idx)
    $name = $normalized.Substring($idx + 1)
    return @{ Parent = $parent; Name = $name }
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $BackupRoot $timestamp

Write-Step "Backup plan"
Write-Host "Distro             : $Distro"
Write-Host "ProjectLinuxPath   : $ProjectLinuxPath"
Write-Host "BackupRoot         : $BackupRoot"
Write-Host "BackupDir          : $backupDir"
Write-Host "SkipWslExport      : $SkipWslExport"
Write-Host "SkipProjectArchive : $SkipProjectArchive"
Write-Host "SkipDbBackup       : $SkipDbBackup"
Write-Host "DryRun             : $DryRun"

if ($DryRun) {
    Write-Host "`n[dry-run] no files were created."
    exit 0
}

Write-Step "Create backup directory"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$projectParts = Split-LinuxPath -LinuxPath $ProjectLinuxPath
$projectParentUnc = Convert-LinuxPathToWslUnc -DistroName $Distro -LinuxPath $projectParts.Parent
$projectRootUnc = Convert-LinuxPathToWslUnc -DistroName $Distro -LinuxPath $ProjectLinuxPath
$dbUnc = Convert-LinuxPathToWslUnc -DistroName $Distro -LinuxPath "$ProjectLinuxPath/data/app.db"

if (-not $SkipProjectArchive) {
    Write-Step "Archive project directory from \\wsl$"
    if (-not (Test-Path $projectRootUnc)) {
        throw "Project path not found via \\wsl`$: $projectRootUnc"
    }

    $projectTar = Join-Path $backupDir ("project-{0}.tar.gz" -f $timestamp)
    $tarSucceeded = $false
    $excludeNames = @(
        ".venv",
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache"
    )

    try {
        $tarArgs = @()
        foreach ($name in $excludeNames) {
            $tarArgs += "--exclude=$($projectParts.Name)/$name"
        }
        $tarArgs += @(
            "--exclude=$($projectParts.Name)/*.pyc",
            "-czf", $projectTar,
            "-C", $projectParentUnc,
            $projectParts.Name
        )

        Invoke-Checked {
            & tar @tarArgs
        } "Failed to create tar.gz archive with tar."
        $tarSucceeded = $true
        Write-Host "Saved: $projectTar"
    } catch {
        Write-Host "[warn] tar archive failed, fallback to ZIP archive."
        $projectZip = Join-Path $backupDir ("project-{0}.zip" -f $timestamp)
        $zipInputs = Get-ChildItem -LiteralPath $projectRootUnc -Force |
            Where-Object { $_.Name -notin $excludeNames } |
            Select-Object -ExpandProperty FullName
        if (-not $zipInputs) {
            throw "No files found to archive after exclusions."
        }
        Compress-Archive -Path $zipInputs -DestinationPath $projectZip -Force
        Write-Host "Saved: $projectZip"
    }

    if (-not $tarSucceeded) {
        Write-Host "[info] Used ZIP fallback because tar command failed with \\wsl$ path."
    }
}

if (-not $SkipDbBackup) {
    Write-Step "Backup SQLite database (app.db) from \\wsl$"
    if (-not (Test-Path $dbUnc)) {
        throw "Database not found via \\wsl`$: $dbUnc"
    }

    $dbOut = Join-Path $backupDir ("app-{0}.db" -f $timestamp)
    Copy-Item -Path $dbUnc -Destination $dbOut -Force
    Write-Host "Saved: $dbOut"

    $walUnc = "$dbUnc-wal"
    $shmUnc = "$dbUnc-shm"
    if (Test-Path $walUnc) {
        $walOut = Join-Path $backupDir ("app-{0}.db-wal" -f $timestamp)
        Copy-Item -Path $walUnc -Destination $walOut -Force
        Write-Host "Saved: $walOut"
    }
    if (Test-Path $shmUnc) {
        $shmOut = Join-Path $backupDir ("app-{0}.db-shm" -f $timestamp)
        Copy-Item -Path $shmUnc -Destination $shmOut -Force
        Write-Host "Saved: $shmOut"
    }
}

if (-not $SkipWslExport) {
    Write-Step "Export WSL distro (full distro backup, may be large)"
    $wslTar = Join-Path $backupDir ("wsl-{0}-{1}.tar" -f $Distro, $timestamp)

    Invoke-Checked {
        & wsl --shutdown
    } "Failed to shutdown WSL before export."

    Invoke-Checked {
        & wsl --export $Distro $wslTar
    } "Failed to export WSL distro."

    Write-Host "Saved: $wslTar"
}

Write-Step "Done"
Write-Host "All backups completed."
Write-Host "Output directory: $backupDir"
