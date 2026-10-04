param([ValidateSet("freight", "pt", "utility", "test")][string]$Which = "test")
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
switch ($Which) {
  "freight" {
    Set-Location "$root\freight_packets"
    python -m freightpkt generate --out sample_data
    python -m freightpkt run --data sample_data --out out
    python -m freightpkt serve --data sample_data --out out
  }
  "pt" {
    Set-Location "$root\pt_auth"
    python -m ptauth generate --out sample_data
    python -m ptauth run --data sample_data --out out
    python -m ptauth serve --data sample_data --out out
  }
  "utility" {
    Set-Location "$root\utility_watch"
    python -m uwatch generate --out sample_data
    python -m uwatch run --data sample_data --out out
    Start-Process "$root\utility_watch\out\report.html"
  }
  "test" {
    Push-Location "$root\freight_packets"; python -m pytest -q; Pop-Location
    Push-Location "$root\pt_auth"; python -m pytest -q; Pop-Location
    Push-Location "$root\utility_watch"; python -m pytest -q; Pop-Location
  }
}
