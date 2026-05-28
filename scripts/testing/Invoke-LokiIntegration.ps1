param(
    [switch]$SetupTautulli,
    [switch]$Destructive,
    [switch]$CreateLibrary,
    [switch]$Browser,
    [string]$EnvFile = "Downshiftarr.test.env",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

if ($SetupTautulli) {
    & $Python -m scripts.testing.tautulli_manager up --env-file $EnvFile
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

$argsList = @("-m", "scripts.testing.run_loki_matrix", "--env-file", $EnvFile)
if ($Destructive) {
    $argsList += "--destructive"
}
if ($CreateLibrary) {
    $argsList += "--create-library"
}

& $Python @argsList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($Browser) {
    & $Python -m scripts.testing.loki_browser_smoke --env-file $EnvFile
    exit $LASTEXITCODE
}
