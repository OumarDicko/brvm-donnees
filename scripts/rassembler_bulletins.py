"""Rassemble les bulletins officiels de la cote en un dossier unique, un fichier par séance : BOC_AAAAMMJJ.pdf,
avec un manifeste (empreinte SHA-256, taille, origine) pour que chaque ligne de la base soit vérifiable.

Usage : python rassembler_bulletins.py dossier_sortie [brvm_reports.zip]
  - si le zip de Hugging Face n'est pas donné, il est téléchargé (1,5 Go) ;
  - les bulletins listés dans liste_pdf_abidjan.txt sont téléchargés depuis Abidjan.net.
Besoin : Python 3 seul (urllib, zipfile, hashlib).
"""
import sys, os, re, zipfile, hashlib, csv, urllib.request

HF = "https://huggingface.co/datasets/lamekemal/brvm-reports-pdfs/resolve/main/brvm_reports.zip"

def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def telecharger(url, dest):
    with urllib.request.urlopen(url, timeout=120) as r, open(dest, 'wb') as f:
        while True:
            b = r.read(1 << 20)
            if not b: break
            f.write(b)

def main():
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    zp = sys.argv[2] if len(sys.argv) > 2 else os.path.join(out, 'brvm_reports.zip')
    if not os.path.exists(zp):
        print('téléchargement de l\'archive Hugging Face (1,5 Go)...', flush=True); telecharger(HF, zp)
    rows = []
    z = zipfile.ZipFile(zp)
    versions = {}
    for n in sorted(z.namelist()):
        m = re.match(r'(?i)boc_(\d{8})(_\d)?\.pdf$', n)
        if m: versions.setdefault(m.group(1), []).append(n)
    print(f'{len(versions)} séances dans l\'archive', flush=True)
    for i, (d, noms) in enumerate(sorted(versions.items())):
        for k, n in enumerate(noms):          # la dernière version garde le nom simple, les autres sont suffixées
            nom = f'BOC_{d}.pdf' if k == len(noms) - 1 else f'BOC_{d}_v{k+1}.pdf'
            p = os.path.join(out, nom); open(p, 'wb').write(z.read(n))
            rows.append([nom, sha(p), os.path.getsize(p), f'{HF} :: {n}'])
        if i % 300 == 0: print(f'  {i}/{len(versions)}  {d}', flush=True)
    liste = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'liste_pdf_abidjan.txt')
    urls = [u.strip() for u in open(liste) if u.strip()] if os.path.exists(liste) else []
    print(f'{len(urls)} bulletins à prendre sur Abidjan.net', flush=True)
    for i, u in enumerate(urls):
        d = re.search(r'(\d{8})', u).group(1); p = os.path.join(out, f'BOC_{d}.pdf')
        if os.path.exists(p): continue
        try: telecharger(u, p); rows.append([os.path.basename(p), sha(p), os.path.getsize(p), u])
        except Exception as e: print('  échec', u, e)
        if i % 25 == 0: print(f'  {i}/{len(urls)}', flush=True)
    with open(os.path.join(out, 'MANIFESTE.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['fichier', 'sha256', 'taille_octets', 'origine']); w.writerows(sorted(rows))
    print(f'terminé : {len(rows)} fichiers, manifeste écrit', flush=True)

if __name__ == '__main__':
    main()
