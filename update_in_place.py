#!/usr/bin/env python3
"""
Päivitä index.html ja tapahtumat.html paikan päällä.

GitHub Actions ajaa tätä päivittäin. Käyttää julkaise.py:n funktioita.

Päivitykset:
- Aikaleima → tämä päivä
- Reseptit recipes-data-lohkoon
- Päiväkodin valikko (Aromi-API) → daycare-menu-lohko
- Tampereen tapahtumat (Bubster-API) → events-data-lohko (tapahtumat.html:ssä)
- Vk 1 (edellinen viikko) -päivälliset TOTEUMASTA — last_cooked-päivämäärät jotka
  osuvat viime viikon (ma–su) väliin.
- Vk 2 (kuluva viikko) -päivälliset TOTEUMASTA — last_cooked tällä viikolla
  jo kokatuille; tulevat päivät jäävät tyhjiksi (käyttäjä lisää tai vahvistaa).
- Vk 3 (ensi viikko) ja Vk 4 (+2 vk) -päivälliset EHDOTUKSET (algoritmi)
"""
import sys
from datetime import date, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import julkaise as J  # type: ignore

INDEX_PATH = SCRIPT_DIR / "index.html"
TAPAHTUMAT_PATH = SCRIPT_DIR / "tapahtumat.html"
RESEPTIT_PATH = SCRIPT_DIR / "reseptit.json"
HISTORIA_PATH = SCRIPT_DIR / "historia.json"


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
        if HISTORIA_PATH.exists():
            html = J.injektoi_tilaushistoria(html, HISTORIA_PATH)
            print(f"✓ Tilaushistoria upotettu: {HISTORIA_PATH.name}")
        valikko = J.hae_paivakodin_valikko(paivia=14)
        if valikko:
            html = J.injektoi_paivakoti(html, valikko)
            print(f"✓ Päiväkodin valikko: {len(valikko['paivat'])} päivää")

        # Päivitä julkaise.py:n RESEPTIT_PATH viittaamaan tähän kansioon
        J.RESEPTIT_PATH = RESEPTIT_PATH

        # Laske ankkuripäivämäärät neljälle viikolle (siirto -1 / 0 / +1 / +2)
        # Python: weekday() 0=Ma, 6=Su
        kuluvan_viikon_ma = date.today() - timedelta(days=date.today().weekday())
        edellisen_viikon_ma = kuluvan_viikon_ma - timedelta(days=7)
        ensi_viikon_ma     = kuluvan_viikon_ma + timedelta(days=7)
        viikon_paasta_ma   = kuluvan_viikon_ma + timedelta(days=14)

        # Vk 1 = EDELLINEN VIIKKO (toteuma) — last_cooked osuu viime viikkoon
        html, w1_nimet = J.injektoi_viikon_toteuma(html, "w1", edellisen_viikon_ma)
        if w1_nimet:
            print(f"✓ w1 (edellinen vk) toteuma: {', '.join(w1_nimet)}")
        else:
            print("  w1 (edellinen vk) toteuma tyhjä — ei vahvistettuja reseptejä")

        # Vk 2 = KULUVA VIIKKO (toteuma + suunnitelma) — last_cooked tällä viikolla
        html, w2_nimet = J.injektoi_viikon_toteuma(html, "w2", kuluvan_viikon_ma)
        if w2_nimet:
            print(f"✓ w2 (kuluva vk) toteuma: {', '.join(w2_nimet)}")
        else:
            print("  w2 (kuluva vk) toteuma tyhjä")

        # Vk 3 ja Vk 4 = EHDOTUKSET (algoritmi). Annetaan viikkojen ankkuripäivät
        # jotta planned-overridet (reseptit.json:n 'planned'-kenttä) saadaan kohdistettua
        # oikeisiin päivämääriin.
        html, vk_nimet = J.injektoi_viikkojen_paivalliset(
            html,
            ("w3", "w4"),
            viikon_alkupvmt={"w3": ensi_viikon_ma, "w4": viikon_paasta_ma},
        )
        for vk, nimet in vk_nimet.items():
            if nimet:
                rooli = "ensi vk" if vk == "w3" else "+2 vk"
                print(f"✓ {vk} ({rooli}) ehdotukset: {', '.join(nimet)}")

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
