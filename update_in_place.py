#!/usr/bin/env python3
"""
Päivitä index.html ja tapahtumat.html paikan päällä.

GitHub Actions ajaa tätä päivittäin. Käyttää julkaise.py:n funktioita.

Päivitykset:
- Aikaleima → tämä päivä
- Reseptit recipes-data-lohkoon
- Päiväkodin valikko (Aromi-API) → daycare-menu-lohko
- Tampereen tapahtumat (Bubster-API) → events-data-lohko (tapahtumat.html:ssä)
- Kaikkien 3 viikon päivällisten ehdotukset (ehdotusalgoritmi, ei toistoja)
"""
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import julkaise as J  # type: ignore

INDEX_PATH = SCRIPT_DIR / "index.html"
TAPAHTUMAT_PATH = SCRIPT_DIR / "tapahtumat.html"
RESEPTIT_PATH = SCRIPT_DIR / "reseptit.json"


def main():
    pvm = date.today().isoformat()
    muutoksia = False

    # --- index.html ---
    if INDEX_PATH.exists():
        html = INDEX_PATH.read_text(encoding="utf-8")
        alkuperäinen = html
        html = J.paivita_aikaleima(html, pvm)
        html = J.lisaa_robots(html)
        if RESEPTIT_PATH.exists():
            html = J.injektoi_reseptit(html, RESEPTIT_PATH)
        valikko = J.hae_paivakodin_valikko(paivia=14)
        if valikko:
            html = J.injektoi_paivakoti(html, valikko)
            print(f"✓ Päiväkodin valikko: {len(valikko['paivat'])} päivää")
        # Kaikkien kolmen viikon päivällisehdotukset (rotaation korjaava päivitys)
        # Päivitä julkaise.py:n RESEPTIT_PATH viittaamaan tähän kansioon
        J.RESEPTIT_PATH = RESEPTIT_PATH
        html, vk_nimet = J.injektoi_viikkojen_paivalliset(html, ("w1", "w2", "w3"))
        for vk, nimet in vk_nimet.items():
            if nimet:
                print(f"✓ {vk} ehdotukset: {', '.join(nimet)}")
        if html != alkuperäinen:
            INDEX_PATH.write_text(html, encoding="utf-8")
            muutoksia = True
            print(f"✓ Päivitetty {INDEX_PATH.name}")
        else:
            print(f"  Ei muutoksia: {INDEX_PATH.name}")

    # --- tapahtumat.html ---
    if TAPAHTUMAT_PATH.exists():
        html = TAPAHTUMAT_PATH.read_text(encoding="utf-8")
        alkuperäinen = html
        html = J.paivita_aikaleima(html, pvm)
        html = J.lisaa_robots(html)
        tap = J.hae_tampere_tapahtumat(kuukaudet=3)
        if tap:
            html = J.injektoi_tapahtumat(html, tap)
            print(f"✓ Tampereen tapahtumat: {len(tap['tapahtumat'])} kpl")
        if html != alkuperäinen:
            TAPAHTUMAT_PATH.write_text(html, encoding="utf-8")
            muutoksia = True
            print(f"✓ Päivitetty {TAPAHTUMAT_PATH.name}")
        else:
            print(f"  Ei muutoksia: {TAPAHTUMAT_PATH.name}")

    if muutoksia:
        print("\nMuutoksia tehty — GitHub Actions commitoi ne.")
        sys.exit(0)
    else:
        print("\nEi muutoksia.")
        sys.exit(0)


if __name__ == "__main__":
    main()
