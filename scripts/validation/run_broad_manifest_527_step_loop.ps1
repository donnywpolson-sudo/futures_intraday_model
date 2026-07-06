param(
    [Parameter(Mandatory = $true)]
    [string]$Token,
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = "Stop"
$ApprovalToken = "APPROVE_BROAD_MANIFEST_527_REBUILD_V1_BUILD_460_ROWS_EXCLUDING_6M_2012_ROLL_MATURITY_ONLY_UNDER_VENDOR_OHLCV_POLICY"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$CurrentRoot = (Resolve-Path (Get-Location)).Path
if ($CurrentRoot -ne $RepoRoot) {
    Write-Error ("FAIL step_loop: must run from repo root {0}; current cwd is {1}" -f $RepoRoot, $CurrentRoot)
    exit 1
}
if ($Token -ne $ApprovalToken) {
    Write-Error "FAIL step_loop: missing or incorrect broad build approval token"
    exit 1
}

$LogPath = "reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1_monitor\step_loop_ps.log"
$Checkpoint = "reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1\build_progress.jsonl"
$Payloads = "reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1\build_result_payloads.jsonl"
$OutputRoot = "data\causally_gated_normalized"
$Manifest = "reports\data_audit\causal_base_rebuild\broad_manifest_527_rebuild_v1\causal_base_manifest.json"

function Write-LoopLog {
    param([string]$Message)
    $parent = Split-Path -Parent $LogPath
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    Add-Content -Path $LogPath -Value $Message
}

function Get-LineCount {
    param([string]$Path)
    if (Test-Path $Path) {
        return (Get-Content $Path | Measure-Object).Count
    }
    return 0
}

function Get-ParquetCount {
    param([string]$Path)
    if (Test-Path $Path) {
        return (Get-ChildItem -Recurse -Filter *.parquet $Path | Measure-Object).Count
    }
    return 0
}

function Write-Checker {
    param([int]$ReturnCode)
    $last = ""
    if (Test-Path $Checkpoint) {
        $last = Get-Content $Checkpoint -Tail 1
    }
    Write-LoopLog (
        "checker at={0:o} rc={1} payload_count={2} parquet_count={3} last={4}" -f
        (Get-Date), $ReturnCode, (Get-LineCount $Payloads), (Get-ParquetCount $OutputRoot), $last
    )
}

Write-LoopLog ("step_loop_start at={0:o} interval_seconds={1} runner=one_market_year_per_invocation" -f (Get-Date), $IntervalSeconds)
$lastTick = Get-Date "2000-01-01"
while ($true) {
    & python -m scripts.validation.build_broad_manifest_527_rebuild --one-market-year-per-invocation --resume-existing-partial --broad-build-approval-token $Token
    $rc = [int]$LASTEXITCODE
    $now = Get-Date
    if ((($now - $lastTick).TotalSeconds -ge $IntervalSeconds) -or $rc -ne 0 -or (Test-Path $Manifest)) {
        Write-Checker $rc
        $lastTick = $now
    }
    if ($rc -ne 0) {
        Write-LoopLog ("step_loop_end status=FAIL rc={0}" -f $rc)
        exit $rc
    }
    if (Test-Path $Manifest) {
        Write-LoopLog "step_loop_end status=PASS"
        exit 0
    }
}
