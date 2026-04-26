# Automatisoitu tilaushistorian päivitys (Windows)

Tällä asetetaan Windows-kone automaattisesti seuraamaan **Heikin Keittiö/S-kaupat - tehdyt tilaukset/** -kansiota: kun lataat sinne uuden tilausvahvistus-PDF:n, automaatio parsii sen, päivittää sivuston ja pushaa muutokset GitHubiin.

## Kertaluonteinen asennus

### Vaihe 1: Asenna riippuvuudet

Avaa PowerShell **järjestelmänvalvojana** ja aja:

```powershell
# Python (jos ei jo asennettu) — lataa https://www.python.org/downloads/windows/
# Varmista että "Add Python to PATH" on valittuna.

# Asenna pdfplumber-kirjasto (PDF-parsintaan)
pip install pdfplumber

# Git for Windows (jos ei jo asennettu) — lataa https://git-scm.com/download/win
```

Tarkista että kaikki toimii — tavallisessa PowerShell-ikkunassa:

```powershell
python --version    # esim. Python 3.12.5
git --version       # esim. git version 2.45.x
```

### Vaihe 2: Alusta git julkaisukansiossa

Jos `julkaisu/`-kansiossa ei vielä ole git-yhteyttä reposi, alusta:

```powershell
cd "C:\polku\Heikin Keittiö\julkaisu"
git init
git remote add origin https://github.com/HeikkiHauskaviita/perheen-ruokalista.git
git branch -M main
git pull origin main
```

Jos git pyytää käyttäjätietoja, syötä **GitHub-käyttäjänimi + Personal Access Token** (PAT). Luo PAT osoitteessa: https://github.com/settings/tokens → "Generate new token (classic)" → valitse oikeudet "repo".

Tallenna tunnukset Windowsin tunnushallintaan ettei niitä tarvitse syöttää joka pushissa:

```powershell
git config --global credential.helper manager
```

### Vaihe 3: Testaa skripti käsin

Aja kerran käsin varmistaaksesi että kaikki toimii:

```powershell
cd "C:\polku\Heikin Keittiö"
powershell -ExecutionPolicy Bypass -File .\paivita_historia.ps1
```

Tarkista `paivita_historia.log` — pitäisi nähdä rivit "Ei uusia/päivittyneitä PDF:iä" tai jos olet juuri pudottanut PDF:n kansioon, "Löytyi N PDF:ää" → "Pushed GitHubiin".

### Vaihe 4: Aja Task Scheduler -konfiguraatio

Avaa **Task Scheduler** (suomeksi: Tehtävien ajoitusohjelma):

1. Klikkaa oikealla **Create Task** (Luo tehtävä)
2. **General** -välilehti:
   - Name: `Heikin Keittiö - tilaushistoria`
   - Description: `Päivittää tilaushistorian PDF-parsinnan jälkeen ja pushaa GitHubiin.`
   - Run only when user is logged on (oletus)
   - Configure for: `Windows 10`
3. **Triggers** -välilehti → **New**:
   - Begin the task: `On a schedule`
   - Daily, Start: ohjelmoi vapaaksi (esim. 06:00)
   - **Repeat task every:** `15 minutes`
   - **for a duration of:** `Indefinitely`
   - OK
4. **Actions** -välilehti → **New**:
   - Action: `Start a program`
   - Program/script: `powershell.exe`
   - Add arguments:
     ```
     -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\polku\Heikin Keittiö\paivita_historia.ps1"
     ```
     (vaihda polku oikeaan)
   - OK
5. **Conditions** -välilehti:
   - Poista valinta "Start the task only if the computer is on AC power" (jos haluat sen toimivan myös akulla)
6. **Settings** -välilehti:
   - Allow task to be run on demand: ON
   - If the task fails, restart every: 1 minute, max 3 times
7. OK → anna salasanasi tarvittaessa.

### Vaihe 5: Testaa automaattinen ajo

Etsi tehtävä Task Scheduler -listalta, klikkaa oikealla **Run**. Avaa `paivita_historia.log` ja tarkista että ajo onnistui.

## Käyttötapa jatkossa

1. Tee tilaus s-kaupat.fi:ssä
2. Lataa "Tilaus _ S-kaupat ruoan verkkokauppa.pdf" -tiedosto kansioon **Heikin Keittiö/S-kaupat - tehdyt tilaukset/**
3. **Odota enintään 15 minuuttia** — Task Scheduler huomaa uuden PDF:n ja:
   - Parsii sen → päivittää `historia.json`
   - Ajaa `julkaise.py` → päivittää sivut ja vk 3 -ehdotukset
   - Commitoi ja pushaa muutokset GitHubiin
   - GitHub Pages deployaa automaattisesti
4. Hinnat ja merkit päivittyvät kaikkiin viikkoihin live-sivulla.

## Vianmääritys

**Loki**: `Heikin Keittiö/paivita_historia.log` näyttää viimeiset ajot.

**Tehtävä ei ajaudu** → Task Scheduler → kaksoisklikkaa tehtävää → **History**-välilehti → tarkista virheilmoitukset.

**Git push epäonnistuu** → tarkista että PAT on tallennettu credential manageriin. Aja `git push` käsin julkaisukansiossa kerran.

**PDF:ää ei tunnistettu** → tarkista `paivita_historia.log`. Voi olla että S-kauppa muutti PDF:n rakennetta — katso `parse_tilaukset.py`-virheilmoitukset ja päivitä parserin regex-säännöt.

**Halutaan ajaa heti, ei odotella 15 min** → Task Scheduler → klikkaa oikealla tehtävää → Run.

## Manuaalinen ajo

Jos automaatio ei jostain syystä toimi, voit aina ajaa skriptin käsin:

```powershell
cd "C:\polku\Heikin Keittiö"
.\paivita_historia.ps1
```

Tai vaiheittain:

```powershell
python parse_tilaukset.py
python julkaise.py
cd julkaisu
git add -A
git commit -m "Päivitys"
git push
```
