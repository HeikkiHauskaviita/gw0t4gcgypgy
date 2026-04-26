# paivita_historia.ps1
# Windows-skripti joka:
#   1. Tarkistaa onko tilaus-PDF-kansiossa uusia/päivittyneitä PDF-tiedostoja
#   2. Jos on, ajaa parse_tilaukset.py + julkaise.py
#   3. Commitoi ja pushaa julkaisukansion sisällön GitHubiin
#
# Käyttö: tuplaklikkaa tai aja Task Schedulerin kautta.
# Asetukset: ks. SETUP_AUTOMAATIO.md

param(
    [string]$KeittioRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path)
)

$ErrorActionPreference = "Continue"  # älä kaadu kesken — kirjaa virheet
$LogFile      = Join-Path $KeittioRoot "paivita_historia.log"
$TilausDir    = Join-Path $KeittioRoot "S-kaupat - tehdyt tilaukset"
$JulkaisuDir  = Join-Path $KeittioRoot "julkaisu"
$LastRunFile  = Join-Path $KeittioRoot ".last_paivitys"
$HistoriaJson = Join-Path $KeittioRoot "historia.json"

function Log {
    param([string]$msg)
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$stamp | $msg" | Out-File -FilePath $LogFile -Append -Encoding utf8
    Write-Host "$stamp | $msg"
}

# Pidä loki kohtuukokoisena: jos yli 1 MB, katkaise viimeisten 500 rivin kokoiseksi
if (Test-Path $LogFile) {
    $size = (Get-Item $LogFile).Length
    if ($size -gt 1MB) {
        $tail = Get-Content $LogFile -Tail 500
        $tail | Set-Content -Path $LogFile -Encoding utf8
    }
}

Log "=== paivita_historia.ps1 alkaa ==="

# 1) Tarkista onko PDF-kansiossa uusia tiedostoja
if (-not (Test-Path $TilausDir)) {
    Log "Tilauskansiota ei löydy: $TilausDir — lopetetaan."
    exit 0
}

$lastRun = if (Test-Path $LastRunFile) {
    (Get-Item $LastRunFile).LastWriteTime
} else {
    Get-Date "2000-01-01"
}

$uusiaPdf = Get-ChildItem -Path $TilausDir -Filter "*.pdf" -File |
    Where-Object { $_.LastWriteTime -gt $lastRun }

if (-not $uusiaPdf -or $uusiaPdf.Count -eq 0) {
    Log "Ei uusia/päivittyneitä PDF:iä viime ajon jälkeen ($lastRun). Lopetetaan."
    exit 0
}

Log ("Löytyi " + $uusiaPdf.Count + " uutta/päivittynyttä PDF:ää: " +
     ($uusiaPdf | ForEach-Object { $_.Name }) -join ", ")

# 2) Aja parser
Set-Location $KeittioRoot
Log "Ajetaan parse_tilaukset.py..."
$parseOutput = & python parse_tilaukset.py 2>&1
$parseOutput | Out-File -FilePath $LogFile -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    Log "VIRHE: parse_tilaukset.py epäonnistui (exit $LASTEXITCODE)."
    exit 1
}

# 3) Aja julkaise.py
Log "Ajetaan julkaise.py..."
$julkOutput = & python julkaise.py 2>&1
$julkOutput | Out-File -FilePath $LogFile -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) {
    Log "VIRHE: julkaise.py epäonnistui (exit $LASTEXITCODE)."
    exit 1
}

# 4) Kopioi historia.json myös julkaisukansioon (jotta se on saatavilla GitHub Actionsille)
if (Test-Path $HistoriaJson) {
    Copy-Item $HistoriaJson -Destination $JulkaisuDir -Force
    Log "historia.json kopioitu julkaisukansioon."
}

# 5) Git commit + push
if (-not (Test-Path (Join-Path $JulkaisuDir ".git"))) {
    Log "VAROITUS: julkaisu/-kansiossa ei ole .git-hakemistoa. Git-pushia ei tehdä."
    Log "         Pushaa manuaalisesti tai alusta git: cd julkaisu; git init"
} else {
    Set-Location $JulkaisuDir
    Log "Git status..."
    $status = & git status --porcelain 2>&1
    if (-not $status) {
        Log "Ei muutoksia commitoitavaksi."
    } else {
        Log ("Muutoksia: " + ($status -replace "`n", "; "))
        & git add -A 2>&1 | Out-File -FilePath $LogFile -Append -Encoding utf8
        $today = Get-Date -Format "yyyy-MM-dd"
        & git commit -m "Auto: päivitetty tilaushistoria $today" 2>&1 | Out-File -FilePath $LogFile -Append -Encoding utf8
        if ($LASTEXITCODE -ne 0) {
            Log "VAROITUS: git commit palautti exit $LASTEXITCODE — ei pushata."
        } else {
            & git push 2>&1 | Out-File -FilePath $LogFile -Append -Encoding utf8
            if ($LASTEXITCODE -eq 0) {
                Log "✓ Pushed GitHubiin."
            } else {
                Log "VIRHE: git push epäonnistui (exit $LASTEXITCODE)."
            }
        }
    }
}

# 6) Päivitä viimeinen ajopäivä
"" | Set-Content -Path $LastRunFile -Encoding utf8
Log "=== paivita_historia.ps1 valmis ==="
exit 0
