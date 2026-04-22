[README.txt](https://github.com/user-attachments/files/26953409/README.txt)
Perheen viikkoruokalista — julkaisuvalmis paketti
====================================================

Tämä kansio sisältää staattisen sivuston, jonka voi julkaista ilmaiseksi
GitHub Pagesilla (tai Netlifyllä / Cloudflare Pagesilla).

Tiedostot:
  index.html     — koko ruokalista yhtenä tiedostona (itsenäinen)
  README.txt     — tämä ohje


GitHub Pages -julkaisu, askel askeleelta
----------------------------------------

ENSIMMÄINEN KERTA (n. 5 min):

1) Luo GitHub-tili jos sinulla ei ole: https://github.com/signup
   (Vahvista sähköposti. Ilmainen tili riittää.)

2) Luo uusi repository:
   https://github.com/new
   - Repository name: perheen-ruokalista
   - Description: "Perheen viikkoruokalista"
   - Visibility: Public (vaaditaan ilmaiselle GitHub Pagesille;
     sivulla on jo meta-tagi joka estää Google-indeksoinnin)
   - Älä ruksi "Add a README file" — jätä repo tyhjäksi
   - Klikkaa "Create repository"

3) Lataa index.html reposi:
   Repon sivulla on teksti "uploading an existing file" (linkki).
   Klikkaa sitä tai mene suoraan:
   https://github.com/KÄYTTÄJÄNIMI/perheen-ruokalista/upload/main

   - Raahaa index.html selaimeen (tästä samasta julkaisu/-kansiosta)
   - Alla "Commit changes" -kohdassa voit jättää oletustekstin
   - Klikkaa vihreä "Commit changes" -nappi

4) Aktivoi GitHub Pages:
   - Mene reposi sivulla: Settings (yläpalkki oikealla)
   - Vasemmasta valikosta: Pages
   - "Build and deployment" → Source: "Deploy from a branch"
   - Branch: main  /  / (root)
   - Klikkaa Save
   - Odota 1–2 min. Ylhäälle ilmestyy:
     "Your site is live at https://KÄYTTÄJÄNIMI.github.io/perheen-ruokalista/"

5) Jaa URL Johannalle.


PÄIVITYS (toistuva):

Kun teet muutoksia ruokalistaan Cowork-työkaluilla ja haluat päivittää
julkaistun sivun:

  a) Aja Cowork-kansiossa: python3 julkaise.py
     (päivittää aikaleiman ja luo uuden index.html:n tähän kansioon)

  b) Avaa selaimessa: https://github.com/KÄYTTÄJÄNIMI/perheen-ruokalista

  c) Klikkaa yläriviltä "Add file" → "Upload files" → raahaa uusi
     index.html selaimeen → "Commit changes".
     Tämä korvaa vanhan.

  d) GitHub Pages päivittyy itsestään ~30 s kuluttua. Johanna näkee uuden
     version samasta URLista.


Vaihtoehtoinen päivitystyönkulku (git-komennoilla)
---------------------------------------------------

Koska Cowork-kansion tiedostojärjestelmä ei tue gittiä suoraan,
kloonaa repo johonkin muualle koneellasi:

  # Kerran:
  cd ~/Documents                            # tai C:\Users\Heikki\Documents\
  git clone https://github.com/KÄYTTÄJÄNIMI/perheen-ruokalista.git

  # Jokainen päivitys:
  cp "/polku/Cowork/Heikin Keittiö/julkaisu/index.html" ~/Documents/perheen-ruokalista/
  cd ~/Documents/perheen-ruokalista
  git add index.html
  git commit -m "ruokalistan päivitys"
  git push


Vinkkejä
--------

* Jos haluat custom-domainin (esim. ruokalista.omadomain.fi):
  Settings → Pages → Custom domain. Vaatii DNS-asetuksen domainin puolelta.

* GitHub-tiedostolistassa näkyvä historia (commits) toimii automaattisena
  varmuuskopiona ja näyttää kuka/koska muutti mitä.

* Jos et halua Googlen indeksoivan sivua: index.html:ssä on jo
  <meta name="robots" content="noindex, nofollow">.

* Jos haluat salasanasuojauksen: ilmainen GitHub Pages vaatii public-repon.
  Netlify ja Cloudflare Pages tukevat salasanasuojausta ilmaisversiossa.

Viimeisin julkaisu: 2026-04-22
