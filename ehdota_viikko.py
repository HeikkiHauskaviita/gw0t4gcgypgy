#!/usr/bin/env python3
"""
Ehdota seuraavan viikon päivälliset reseptipoolista.

Perusperiaate:
- Priorisoi reseptit joita ei ole keitetty pitkään aikaan (last_cooked = null tai vanhin).
- Suodata arki (ma-pe): max 35 min, ei "viikonloppu"-tagia.
- Viikonloppu (la-su): voi olla pidempiä tai "viikonloppu"-tagilla merkittyjä.
- Ottaa huomioon palautteen (flop = laskee painoarvoa, hitti = ei ekstraa mutta ei haittaa).

Käyttö:
    python3 ehdota_viikko.py                       # ehdotus, ei tallennusta
    python3 ehdota_viikko.py --alkaen 2026-04-27   # näyttää päivät
    python3 ehdota_viikko.py --viikonloppu         # lisää la-su ehdotukset
    python3 ehdota_viikko.py --vahvista 2026-04-27 # merkitsee last_cooked ehdotetuille
    python3 ehdota_viikko.py --vaihda kasvislasagne --paiva la
"""
import argparse
import json
import sys
from datetime import date, timedelta, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RESEPTIT_PATH = SCRIPT_DIR / "reseptit.json"

ARKI_MAX_MIN = 35
PAIVAT_ARKI = ["Ma", "Ti", "Ke", "To", "Pe"]
PAIVAT_VIIKONLOPPU = ["La", "Su"]


def lataa():
    with open(RESEPTIT_PATH, encoding="utf-8") as f:
        return json.load(f)


def tallenna(data):
    with open(RESEPTIT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def palaute_paino(resepti):
    """Palauttaa pieni kerroin joka vähentää valinnan todennäköisyyttä jos flopeja."""
    p = resepti.get("palaute", [])
    if not p:
        return 0
    flopit = sum(1 for x in p if x.get("arvio") == "flop")
    osumia = sum(1 for x in p if x.get("arvio") == "hitti")
    return osumia - flopit * 2  # flop painaa enemmän


def suodata(reseptit, viikonloppu=False):
    tulos = []
    for r in reseptit:
        tagit = r.get("tagit", [])
        if viikonloppu:
            # viikonloppuun käy mikä tahansa, mutta priorisoidaan "viikonloppu"-tagit
            tulos.append(r)
        else:
            # arki: max 35 min, ei viikonloppu-tagia
            if "viikonloppu" in tagit:
                continue
            if r.get("max_minuutit", 999) > ARKI_MAX_MIN:
                continue
            tulos.append(r)
    return tulos


def jarjesta_prioriteetin_mukaan(reseptit):
    """Ensisijainen avain: last_cooked (null = kaikkein kauimmin = korkein prioriteetti).
    Toissijainen: palaute (hitit +, flopit -).
    """
    def avain(r):
        lc = r.get("last_cooked")
        # null = -inf käytännössä, käytetään pvm 1900-01-01
        lc_dt = datetime.fromisoformat(lc).date() if lc else date(1900, 1, 1)
        return (lc_dt, -palaute_paino(r))
    return sorted(reseptit, key=avain)


def valitse(reseptit, maara, vältä_ideja=None):
    vältä_ideja = set(vältä_ideja or [])
    ehdokkaat = [r for r in reseptit if r["id"] not in vältä_ideja]
    jarjestetty = jarjesta_prioriteetin_mukaan(ehdokkaat)
    # välttä myös päähintaraaka-aineen toistumista peräkkäin — yksinkertainen heuristiikka
    valitut = []
    edelliset_paaaines = []
    for r in jarjestetty:
        if len(valitut) >= maara:
            break
        paa = _paaaines(r)
        # jos kaksi samasta pääaineksesta peräkkäin, ohita toista
        if paa and edelliset_paaaines[-1:] == [paa]:
            continue
        valitut.append(r)
        edelliset_paaaines.append(paa)
    # täytä jos ei riitä
    i = 0
    while len(valitut) < maara and i < len(jarjestetty):
        if jarjestetty[i] not in valitut:
            valitut.append(jarjestetty[i])
        i += 1
    return valitut[:maara]


def _paaaines(r):
    """Arvattu pääraaka-aine ensimmäisestä aineksesta joka ei ole kaappitavara."""
    for a in r.get("ainekset", []):
        if not a.get("kaappitavara"):
            return a["nimi"].lower().split(",")[0].strip()
    return None


def tulosta_ehdotus(valitut, paivat, alkaen=None):
    print()
    print("Ehdotettu viikkoruokalista:")
    print("-" * 70)
    for i, r in enumerate(valitut):
        pvm_str = ""
        if alkaen:
            pvm = alkaen + timedelta(days=i + (0 if len(paivat) == 5 and paivat[0] == "Ma" else 0))
            pvm_str = f"  {pvm.strftime('%d.%m.')}"
        lc = r.get("last_cooked")
        lc_str = f"(viimeksi {lc[:10]})" if lc else "(ei aiemmin listalla)"
        print(f"  {paivat[i]}{pvm_str}  {r['nimi']:40s} {r['max_minuutit']:2d} min  {lc_str}")
    print("-" * 70)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--alkaen", type=str, help="Viikon alkupäivä ISO-muodossa (esim. 2026-04-27)")
    parser.add_argument("--viikonloppu", action="store_true", help="Ehdota myös la-su")
    parser.add_argument("--vahvista", type=str, help="Tallenna last_cooked = annettu pvm")
    parser.add_argument("--arki-max-min", type=int, default=ARKI_MAX_MIN)
    parser.add_argument(
        "--kategoria",
        type=str,
        default="päivällinen",
        help="Suodata reseptit kategorian mukaan. Oletus 'päivällinen'. "
             "Anna 'kaikki' jos haluat huomioida kaikki kategoriat (välipala, iltapala jne.).",
    )
    args = parser.parse_args()

    globals()["ARKI_MAX_MIN"] = args.arki_max_min

    data = lataa()
    reseptit = data["reseptit"]

    # Kategoriasuodatus — estää että esim. popcornit/kaakao tarjotaan päivälliseksi
    # vain siksi että niiden last_cooked on null (= korkein prioriteetti algoritmissa).
    if args.kategoria != "kaikki":
        ennen = len(reseptit)
        reseptit = [r for r in reseptit if r.get("kategoria") == args.kategoria]
        if not reseptit:
            sys.exit(
                f"Virhe: kategorialla '{args.kategoria}' ei löytynyt yhtään reseptiä "
                f"(reseptit yhteensä {ennen}). Tarkista reseptit.json:n enkoodaus — "
                f"jos kategoriat näkyvät muodossa 'pÃ¤ivÃ¤llinen', tiedosto on "
                f"mojibake-vikainen ja pitää korjata UTF-8:ksi."
            )

    # arki
    arki_pool = suodata(reseptit, viikonloppu=False)
    arki_valinta = valitse(arki_pool, 5)

    alkaen = None
    if args.alkaen:
        try:
            alkaen = date.fromisoformat(args.alkaen)
        except ValueError:
            sys.exit(f"Virheellinen pvm: {args.alkaen}. Odotettu YYYY-MM-DD.")

    tulosta_ehdotus(arki_valinta, PAIVAT_ARKI, alkaen=alkaen)

    vk_valinta = []
    if args.viikonloppu:
        vältä = [r["id"] for r in arki_valinta]
        vk_pool = suodata(reseptit, viikonloppu=True)
        vk_valinta = valitse(vk_pool, 2, vältä_ideja=vältä)
        alkaen_vk = alkaen + timedelta(days=5) if alkaen else None
        tulosta_ehdotus(vk_valinta, PAIVAT_VIIKONLOPPU, alkaen=alkaen_vk)

    if args.vahvista:
        try:
            pvm = date.fromisoformat(args.vahvista)
        except ValueError:
            sys.exit(f"Virheellinen pvm: {args.vahvista}.")
        paivitetyt = []
        for r in arki_valinta + vk_valinta:
            r["last_cooked"] = pvm.isoformat()
            paivitetyt.append(r["id"])
        tallenna(data)
        print()
        print(f"Tallennettu: last_cooked = {pvm} reseptille: {', '.join(paivitetyt)}")

    # oikoreitti ostoslistan tekoon
    idt = [r["id"] for r in arki_valinta + vk_valinta]
    print()
    print("Ostoslistan komento:")
    print(f"  python3 ostoslista.py {' '.join(idt)}")


if __name__ == "__main__":
    main()
