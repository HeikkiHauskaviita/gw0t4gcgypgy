#!/usr/bin/env python3
"""
Parsi S-kaupat-tilausten PDF-yhteenvedot ja tuota historia.json.

Lähde: kansio "S-kaupat - tehdyt tilaukset/" jossa kaksi PDF:ää:
  - "Tilaus _ S-kaupat ruoan verkkokauppa.pdf"   (yksittäinen tilaus, täysi data)
  - "Tilaushistoria _ S-kaupat ruoan verkkokauppa.pdf" (kaikki tilaukset; ensimmäisen
    aiemman tilauksen tuotteet hinnoilla, muiden vain yhteenvedot)

Tuotos: historia.json
{
  "paivitetty": "2026-04-26T20:00:00",
  "tilaukset": [
    {
      "id": "1233714256",
      "pvm": "2026-04-27",
      "kauppa": "Prisma Kaleva",
      "summa_euroa": 73.02,
      "tuotteet": [
        {"nimi": "Paprika keltainen", "kpl": 1, "hinta_kpl": 1.12, "yht": 1.12}
      ]
    },
    ...
  ],
  "hinnat": {
    "Coop mozzarella juustoraaste 150 g": {
      "keski_kpl": 1.28, "viimeisin_kpl": 1.28, "viimeisin_pvm": "2026-04-27",
      "ostokerrat": 2, "tilausIdt": ["1233714256", "1227571612"]
    }
  }
}
"""
import json
import re
import subprocess
import sys
from datetime import datetime, date
from pathlib import Path

# pdfplumber on platform-riippumaton (toimii Windowsissa ilman pdftotext.exe).
# Jos puuttuu, Linux/Mac fallback käyttää pdftotext-komentoa.
try:
    import pdfplumber  # type: ignore
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

SCRIPT_DIR = Path(__file__).resolve().parent
TILAUS_DIR = SCRIPT_DIR / "S-kaupat - tehdyt tilaukset"
OUT = SCRIPT_DIR / "historia.json"

KK = {
    "tammikuuta": 1, "helmikuuta": 2, "maaliskuuta": 3, "huhtikuuta": 4,
    "toukokuuta": 5, "kesäkuuta": 6, "heinäkuuta": 7, "elokuuta": 8,
    "syyskuuta": 9, "lokakuuta": 10, "marraskuuta": 11, "joulukuuta": 12,
}
PAIVA_NIMET = {
    "Maanantai": 0, "Tiistai": 1, "Keskiviikko": 2, "Torstai": 3,
    "Perjantai": 4, "Lauantai": 5, "Sunnuntai": 6,
}


def pdftotext(path: Path) -> str:
    """Pura PDF:n tekstit. Käyttää pdfplumberia jos saatavilla (Windows-yhteensopiva),
    muuten fallback `pdftotext`-komentoon (Linux/Mac, jos asennettu)."""
    if not path.exists():
        raise FileNotFoundError(path)
    if HAS_PDFPLUMBER:
        sivut = []
        with pdfplumber.open(str(path)) as pdf:
            for sivu in pdf.pages:
                t = sivu.extract_text(layout=True) or ""
                sivut.append(t)
        return "\n".join(sivut)
    # Fallback: pdftotext-komento
    out = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True, capture_output=True, text=True,
    )
    return out.stdout


def hinta_to_float(s: str) -> float:
    """'1,12 €' → 1.12"""
    return float(s.replace("€", "").replace(",", ".").strip())


def paattele_vuosi(kk: int, ref_vuosi: int = None, ref_kk: int = None) -> int:
    if ref_vuosi is None or ref_kk is None:
        from datetime import date as _date
        _t = _date.today()
        if ref_vuosi is None: ref_vuosi = _t.year
        if ref_kk is None: ref_kk = _t.month
    """Tilaushistoriassa lukee 'Maanantai 17.6.' ilman vuotta. Päätellään: jos kk on
    suurempi kuin ref_kk, tilaus on viime vuodelta; muuten tämän vuoden alkupuoli.
    Ref oletetaan PDF:n generointihetkeksi."""
    if kk > ref_kk:
        return ref_vuosi - 1
    return ref_vuosi


def parsi_otsikko(rivit: list[str], idx: int) -> dict | None:
    """Etsi tilauksen otsikko ja yhteenveto rivistä idx alkaen.
    Palauta None jos ei tunnista.

    Esim.
       Nouto - Prisma Linnainmaa
       Keskiviikko 22.4. klo 13.00–14.00 | 88,21 €
       Toimitettu
       Tilausnumero: 1227571612
    """
    if idx + 3 >= len(rivit):
        return None
    r1 = rivit[idx].strip()
    # Vaadi väliviiva ja kauppanimi — vältää "Nouto 1,90 €" -tyyliset false positivet
    m_kauppa = re.match(r"(Nouto|Kotiinkuljetus|Tunnin toimitus|Robokuljetus)\s*-\s*([A-ZÅÄÖ][\wåäöÅÄÖ\s\-]+?)\s*$", r1)
    if not m_kauppa:
        return None
    # Etsi päivämäärä-rivi seuraavilta enintään 10 riviltä (pdfplumber lisää tyhjiä)
    pvm_re = re.compile(
        r"(Maanantai|Tiistai|Keskiviikko|Torstai|Perjantai|Lauantai|Sunnuntai)\s+(\d+)\.(\d+)\.\s+klo\s+([\d.]+)[–-]([\d.]+)\s*\|\s*([\d,]+)\s*€"
    )
    m_pvm = None
    for jj in range(idx + 1, min(idx + 12, len(rivit))):
        m_pvm = pvm_re.search(rivit[jj])
        if m_pvm:
            break
    if not m_pvm:
        return None
    paiva, pp, kk, klo_alku, klo_loppu, summa_s = m_pvm.groups()
    pp, kk = int(pp), int(kk)
    vuosi = paattele_vuosi(kk)
    pvm = date(vuosi, kk, pp).isoformat()
    summa = hinta_to_float(summa_s + " €")
    # Tilausnumero seuraavilta riveiltä — voi olla sivuvaihdon takia kaukana
    tilausnumero = None
    for j in range(idx + 2, min(idx + 15, len(rivit))):
        m_tn = re.search(r"Tilausnumero:\s*(\d+)", rivit[j])
        if m_tn:
            tilausnumero = m_tn.group(1)
            break
    if not tilausnumero:
        return None
    return {
        "id": tilausnumero,
        "pvm": pvm,
        "kauppa": m_kauppa.group(2).strip(),
        "tapa": m_kauppa.group(1),
        "klo": f"{klo_alku}-{klo_loppu}",
        "summa_euroa": summa,
        "tuotteet": [],
    }


def parsi_tuotteet(rivit: list[str], alku_idx: int, loppu_idx: int) -> list[dict]:
    """Etsi tuotteet välillä [alku_idx, loppu_idx). Tukee kahta muotoa:

    Muoto A (pdftotext -layout):
       Tuotenimi
       X,XX €     N kpl

    Muoto B (pdfplumber):
       Tuotenimi

       X,XX €
                                  N kpl

    Palauta [{nimi, kpl, hinta_kpl, yht}].
    """
    tuotteet = []
    i = alku_idx
    hint_skip = re.compile(
        r"^\s*("
        r"Tarvitsetko apua\?|https://|Tilaamasi tuotteet|©|Yhteystiedot|Ohjeet|"
        r"Info|S-ryhmän palvelut|Lisää tuotteet ostoskoriin|Aktiiviset tilaukset|"
        r"Aiemmat tilaukset|Toimitettu|Maksukortti|Korttimaksu|Tilausnumero:|"
        r"Tuotteet\s*$|Tilaukset\s*$|Hae tuotteita"
        r")"
    )
    hinta_re = re.compile(r"^([\d,]+)\s*€\s*$")
    kpl_re = re.compile(r"^(\d+)\s*kpl\s*$")
    yhdistetty_re = re.compile(r"^([\d,]+)\s*€\s+(\d+)\s*kpl\s*$")
    sivu_header = re.compile(r"^\d+\.\d+\.\d+\s+klo")

    def is_skippable(rivi: str) -> bool:
        if not rivi.strip():
            return True
        if hint_skip.match(rivi):
            return True
        if sivu_header.match(rivi):
            return True
        return False

    while i < loppu_idx:
        rivi = rivit[i].strip()
        if is_skippable(rivi):
            i += 1
            continue
        # Skipataan jo käytetty hinta tai kpl-rivi (jos parser silmukkaa)
        if hinta_re.match(rivi) or kpl_re.match(rivi) or yhdistetty_re.match(rivi):
            i += 1
            continue

        # Tuotenimi: etsi seuraavilta enintään 5 ei-skipattavalta riviltä hinta + kpl
        # (saman rivin tai erillisten rivien yhdistelmänä)
        nimi = rivi
        hinta = None
        kpl = None
        steps = 0
        j = i + 1
        while j < loppu_idx and steps < 6:
            r = rivit[j].strip()
            if not r:
                j += 1
                continue
            if is_skippable(r):
                # ohjeteksti voi sotkea — break ja jatka seuraavasta tuotteesta
                break
            m_yh = yhdistetty_re.match(r)
            if m_yh:
                hinta = float(m_yh.group(1).replace(",", "."))
                kpl = int(m_yh.group(2))
                j += 1
                break
            m_h = hinta_re.match(r)
            if m_h:
                hinta = float(m_h.group(1).replace(",", "."))
                j += 1
                steps += 1
                continue
            m_k = kpl_re.match(r)
            if m_k:
                kpl = int(m_k.group(1))
                j += 1
                break
            # Jos törmää uuteen tuotenimeen ennen hintaa, ei tuote-pari
            break

        if hinta is not None and kpl is not None:
            tuotteet.append({
                "nimi": nimi,
                "kpl": kpl,
                "hinta_kpl": hinta,
                "yht": round(hinta * kpl, 2),
            })
            i = j
        else:
            i += 1
    return tuotteet


def parsi_yksittainen_tilaus(teksti: str) -> dict:
    """Yksittäisen tilauksen PDF: 'Tilaus _ S-kaupat...pdf'."""
    rivit = teksti.split("\n")
    # Etsi otsikkotiedot (Tilausnumero, summa)
    tilausnumero = None
    summa = None
    pvm = None
    kauppa = None
    klo = None
    for i, r in enumerate(rivit):
        m = re.search(r"Tilausnumero:\s*(\d+)", r)
        if m and not tilausnumero:
            tilausnumero = m.group(1)
        # Joissain PDF-tulosteissa "Tilausnumero:"-otsikko on edellisellä rivillä
        # ja itse numero seuraavalla rivillä yksinään (lopussa).
        if not tilausnumero and i > 0 and "Tilausnumero" in rivit[i - 1]:
            mm = re.search(r"(\d{6,})", r)
            if mm:
                tilausnumero = mm.group(1)
        # Tai numero rivin lopussa päivämäärä-rivin perään
        if not tilausnumero:
            mm = re.search(
                r"klo\s+[\d.]+[–-][\d.]+\s+(\d{6,})\s*$", r
            )
            if mm:
                tilausnumero = mm.group(1)
        # Tilauksen otsikko: yksittäinen PDF voi sisältää päiväyksen samalla rivillä
        # tilausnumeron kanssa. Etsi missä tahansa rivissä päiväyssyntaksi.
        m = re.search(
            r"(Maanantai|Tiistai|Keskiviikko|Torstai|Perjantai|Lauantai|Sunnuntai)\s+(\d+)\.(\d+)\.\s+klo\s+([\d.]+)[–-]([\d.]+)",
            r,
        )
        if m and not pvm:
            _, pp, kk, klo_a, klo_l = m.groups()
            pp, kk = int(pp), int(kk)
            vuosi = paattele_vuosi(kk)
            pvm = date(vuosi, kk, pp).isoformat()
            klo = f"{klo_a}-{klo_l}"
        m = re.search(r"Kokonaissumma\s+([\d,]+)\s*€", r)
        if m and not summa:
            summa = float(m.group(1).replace(",", "."))
        # Kauppa: 'Prisma Kaleva noutolokero' tai vastaava
        if "Prisma" in r and not kauppa:
            mk = re.search(r"(Prisma\s+\w+)", r)
            if mk:
                kauppa = mk.group(1)
        elif "Sale" in r and not kauppa:
            mk = re.search(r"(Sale\s+\w+)", r)
            if mk:
                kauppa = mk.group(1)
    # Tuotteet alkavat "Tilaamasi tuotteet" -otsikon jälkeen
    alku = 0
    for i, r in enumerate(rivit):
        if "Tilaamasi tuotteet" in r:
            alku = i + 1
            break
    tuotteet = parsi_tuotteet(rivit, alku, len(rivit))
    return {
        "id": tilausnumero or "?",
        "pvm": pvm,
        "kauppa": kauppa or "?",
        "klo": klo,
        "summa_euroa": summa,
        "tuotteet": tuotteet,
    }


def parsi_tilaushistoria(teksti: str) -> list[dict]:
    """Tilaushistoria-PDF: useita tilausyhteenvetoja, ensimmäiselle myös tuotelista."""
    rivit = teksti.split("\n")
    tilaukset = []
    # Etsi kaikki otsikot
    otsikko_idxt = []
    for i, r in enumerate(rivit):
        if re.match(r"\s*(Nouto|Kotiinkuljetus|Tunnin toimitus|Robokuljetus)\s*-\s*[A-ZÅÄÖ]", r):
            ots = parsi_otsikko(rivit, i)
            if ots:
                otsikko_idxt.append((i, ots))
    # Tuotteet ovat "Tilaamasi tuotteet" -otsikon jälkeen seuraavaan otsikkoon asti
    for k, (idx, ots) in enumerate(otsikko_idxt):
        seur_idx = otsikko_idxt[k + 1][0] if k + 1 < len(otsikko_idxt) else len(rivit)
        tuote_alku = _parsi_tilaushistoria_tuoteOtsikko(rivit, idx, seur_idx)
        if tuote_alku is not None:
            ots["tuotteet"] = parsi_tuotteet(rivit, tuote_alku, seur_idx)
        tilaukset.append(ots)
    return tilaukset


def _parsi_tilaushistoria_tuoteOtsikko(rivit, idx, seur_idx):
    """Etsii 'Tilaamasi tuotteet' -otsikon rivinumeron, joustavasti välilyönneillä."""
    for j in range(idx, seur_idx):
        r = rivit[j]
        if "Tilaamasi" in r and "tuotteet" in r:
            return j + 1
    return None


def yhdista_hinnat(tilaukset: list[dict]) -> dict:
    """Kerää per-tuote-tiedot kaikista tilauksista."""
    hinnat = {}
    for t in tilaukset:
        if not t.get("pvm") or not t.get("tuotteet"):
            continue
        for tu in t["tuotteet"]:
            nimi = tu["nimi"]
            if nimi not in hinnat:
                hinnat[nimi] = {
                    "ostokerrat": 0,
                    "yht_kpl": 0,
                    "yht_eur": 0.0,
                    "viimeisin_kpl": tu["hinta_kpl"],
                    "viimeisin_pvm": t["pvm"],
                    "tilausIdt": [],
                }
            h = hinnat[nimi]
            h["ostokerrat"] += 1
            h["yht_kpl"] += tu["kpl"]
            h["yht_eur"] += tu["yht"]
            if t["pvm"] >= h["viimeisin_pvm"]:
                h["viimeisin_kpl"] = tu["hinta_kpl"]
                h["viimeisin_pvm"] = t["pvm"]
            h["tilausIdt"].append(t["id"])
    # Laske keskiarvot
    for nimi, h in hinnat.items():
        h["keski_kpl"] = round(h["yht_eur"] / h["yht_kpl"], 2) if h["yht_kpl"] else 0
    return hinnat


def main():
    if not TILAUS_DIR.exists():
        print(f"⚠ Kansiota ei löydy: {TILAUS_DIR}", file=sys.stderr)
        sys.exit(1)
    yks_pdf = TILAUS_DIR / "Tilaus _ S-kaupat ruoan verkkokauppa.pdf"
    his_pdf = TILAUS_DIR / "Tilaushistoria _ S-kaupat ruoan verkkokauppa.pdf"

    tilaukset = []
    if yks_pdf.exists():
        teksti = pdftotext(yks_pdf)
        ots = parsi_yksittainen_tilaus(teksti)
        if ots["id"] != "?":
            tilaukset.append(ots)
            print(f"✓ Yksittäinen tilaus {ots['id']}: {len(ots['tuotteet'])} tuotetta, {ots['summa_euroa']} €")
    if his_pdf.exists():
        teksti = pdftotext(his_pdf)
        hist = parsi_tilaushistoria(teksti)
        # Vältä duplikaatti — id-perusteella
        olemassa = {t["id"] for t in tilaukset}
        for t in hist:
            if t["id"] not in olemassa:
                tilaukset.append(t)
        print(f"✓ Tilaushistoria: {len(hist)} tilausta, {sum(len(t.get('tuotteet', [])) for t in hist)} tuotetta hinnoilla")

    # Lajittele uusin ensin
    tilaukset.sort(key=lambda t: t.get("pvm") or "", reverse=True)

    hinnat = yhdista_hinnat(tilaukset)

    out = {
        "paivitetty": datetime.now().isoformat(timespec="seconds"),
        "tilaukset": tilaukset,
        "hinnat": hinnat,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ Tallennettu: {OUT}")
    print(f"  Tilauksia: {len(tilaukset)}")
    print(f"  Uniikkeja tuotteita hinnoilla: {len(hinnat)}")
    keskiarvo_summa = sum(t.get("summa_euroa") or 0 for t in tilaukset) / max(1, len([t for t in tilaukset if t.get("summa_euroa")]))
    print(f"  Keskiarvo per tilaus: {keskiarvo_summa:.2f} €")


if __name__ == "__main__":
    main()
