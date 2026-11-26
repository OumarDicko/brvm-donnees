"""Numérise le marché des actions des Bulletins Officiels de la Cote (BOC) de la BRVM.

Entrée : l'archive brvm_reports.zip (huggingface.co/datasets/lamekemal/brvm-reports-pdfs).
Sortie : boc_actions.csv, une ligne par titre et par bulletin.

Usage : python numeriser_boc.py brvm_reports.zip [dossier_sortie] [--depuis AAAAMMJJ]   (défaut : 20130916, début de la cotation en continu ; les bulletins plus anciens ont une autre mise en page, non lue)
Besoin : pdftotext (poppler-utils) et pandas.
"""
import re, sys, os, zipfile, subprocess, tempfile
import pandas as pd

MOIS = r"(janv|févr|fevr|mars|avr|mai|juin|juil|août|aout|sept|oct|nov|déc|dec|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
RE_DATE = re.compile(r"^\d{1,2}[- ]" + MOIS + r"\.?[- ]?\d{2}$", re.I)
RE_COMP = re.compile(r"^(1er|2[eè]me|3[eè]me|1st|2nd|3rd)$")
NON_TITRES = {'LAGOS', 'TUNIS', 'BRVM', 'BRVMC', 'FCFA', 'NIGER', 'BENIN', 'TOTAL', 'GHANA', 'TOGO', 'MALI', 'PARIS', 'TOKYO', 'DJIA', 'NIKKEI'}
RE_TICK = re.compile(r"^\s*(?:([A-Z]{2,4})\s+)?([A-Z]{4,5})\s{2,}(.*)$")

def nombre(s, en):
    """en = 'fr' (1 234,56), 'en' (1,234.56) ou 'dot' (1.234.567 ; décembre 2013). True/False acceptés."""
    mode = {True: 'en', False: 'fr'}.get(en, en)
    s = s.replace(' ', ' ').replace(' ', ' ').strip().replace('%', '').strip()
    if mode == 'en': s = s.replace(',', '').replace(' ', '')
    elif mode == 'dot': s = s.replace(' ', '').replace('.', '').replace(',', '.')
    else: s = s.replace(' ', '').replace(',', '.')
    try: return float(s)
    except ValueError: return None

RE_MARQUE = re.compile(r"^\((?:d|v|V|\*+|#|-|Val-T|ex-?c?\)?|Ex-?c?\)?)\)?$", re.I)

def lire_ligne(rest, en, tick):
    """rest = tout ce qui suit le symbole. Retourne un dict de champs, les jetons et leur nature."""
    tok = [t for t in re.split(r"\s{2,}", rest.strip()) if t]
    out = dict(titre=tok[0] if tok else '')
    marques = re.findall(r"\((d|v|V|\*+|#)\)", out['titre']); out['titre'] = re.sub(r"\s*\((d|v|V|\*+|#)\)", "", out['titre']).strip()
    tok = tok[1:]
    while tok and RE_MARQUE.match(tok[0]):                       # (d), (v), (V), (*), (#), (ex- ...
        m = tok[0].strip('()').lower(); tok = tok[1:]
        if m not in ('-', ''): marques.append('d' if m.startswith('ex') else m)
    out['marques'] = ' '.join(marques)
    t2 = []
    for t in tok:                                                # Ex-c / Ex-d collés à un nombre
        m = re.match(r"^(.*?)\s*(Ex-c|Ex-d|Val-T)$", t, re.I)          # aussi « ex-d » en minuscules (BOABF 23/06/2017)
        t2 += [m.group(1), m.group(2)[:1].upper() + m.group(2)[1:].lower() if m.group(2).lower() != 'val-t' else 'Val-T'] if (m and m.group(1)) else [t]
    tok = []
    for t in t2:                                                 # compartiment collé
        m = re.match(r"^(.+?)\s+(1er|2[eè]me|3[eè]me|1st|2nd|3rd)$", t)
        tok += [m.group(1), m.group(2)] if m else [t]
    t3 = []
    for t in tok:                                                # montant du dividende collé à sa date
        m = re.match(r"^([\d\s.,]+?)\s+(\d{1,2}[-\s]\S+[-\s]\d{2,4})$", t)
        t3 += [m.group(1), m.group(2)] if (m and RE_DATE.match(m.group(2))) else [t]
    tok = ['NC' if t == 'NT' else t for t in t3]                 # bulletins en anglais : NT = non traité
    kinds = []
    for t in tok:
        if t in ('NC', 'SP'): kinds.append('X')
        elif t in ('Ex-c', 'Ex-d', 'Val-T'): kinds.append('M')
        elif t in ('-', '–'): kinds.append('E')                 # case vide
        elif '%' in t: kinds.append('P')
        elif RE_DATE.match(t): kinds.append('D')
        elif RE_COMP.match(t): kinds.append('C')
        elif nombre(t, en) is not None: kinds.append('N')
        else: kinds.append('?')
    return out, tok, kinds

def _limites(tok, k, en):
    """Repère le triplet référence / limite basse / limite haute (±7,5 %, arrondi au pas de cotation)."""
    idx = [i for i, x in enumerate(k) if x == 'N']
    for a in range(len(idx) - 2):
        i, j, l = idx[a], idx[a + 1], idx[a + 2]
        if any(k[x] not in 'NM' for x in range(i, l + 1)): continue
        r, b, h = nombre(tok[i], en), nombre(tok[j], en), nombre(tok[l], en)
        if r and b and h and 0.90 <= b / r <= 0.95 and 1.05 <= h / r <= 1.10: return i, j, l
    return None

def _queue(out, tok, k, en, i):
    """Après la limite haute : [dividende date] [compartiment] [rendement] [PER]."""
    if i < len(k) and k[i] == 'N' and i + 1 < len(k) and k[i + 1] == 'D':
        out['dividende'] = nombre(tok[i], en); out['date_dividende'] = tok[i + 1]; i += 2
    elif i < len(k) and k[i] == 'E' and i + 1 < len(k) and k[i + 1] == 'D': out['date_dividende'] = tok[i + 1]; i += 2
    elif i < len(k) and k[i] == 'D': out['date_dividende'] = tok[i]; i += 1
    if i < len(k) and k[i] == 'C': out['compartiment'] = tok[i]; i += 1
    if i < len(k) and k[i] in 'PE':
        out['rendement'] = nombre(tok[i], en) if k[i] == 'P' else None; i += 1
    if i < len(k) and k[i] == 'N': out['per'] = nombre(tok[i], en)
    return out

def format_A(out, tok, k, en):
    # Volume Valeur Précédent Ouv Clôt Moy | Var | VarAn | Référence [Ex-c] Bas Haut | Dividende Date | Comp | Rdt | PER
    lim = _limites(tok, k, en)
    if lim is None: return format_A_v1(out, tok, k, en)
    ir, ib, ih = lim
    out.update(reference=nombre(tok[ir], en), bas=nombre(tok[ib], en), haut=nombre(tok[ih], en))
    for x in range(ir, ih):
        if k[x] == 'M': out['marque_ref'] = tok[x]
    tete = list(range(0, ir))
    if any(k[x] == 'X' for x in tete):                           # titre non coté ou suspendu
        ix = [x for x in tete if k[x] == 'X']
        out['statut'] = tok[ix[0]]
        avant = [nombre(tok[x], en) for x in tete if x < ix[0] and k[x] == 'N']
        if avant: out['precedent'] = avant[-1]
        if len(avant) >= 3: out['volume'], out['valeur'] = avant[0], avant[1]
        var = [x for x in tete if x > ix[-1] and k[x] in 'PNE']
    else:
        nums = [x for x in tete if k[x] == 'N']
        if len(nums) == 5 and not any(k[x] in 'PE' for x in tete):   # référence absente : le « triplet » commence au cours moyen
            v = [nombre(tok[x], en) for x in nums] + [nombre(tok[ir], en)]
            out.update(volume=v[0], valeur=v[1], precedent=v[2], ouverture=v[3], cloture=v[4], moyen=v[5], statut='coté', reference=None)
            return _queue(out, tok, k, en, ih + 1)
        if len(nums) < 6: return format_A_v1(out, tok, k, en)
        v = [nombre(tok[x], en) for x in nums[:6]]
        out.update(volume=v[0], valeur=v[1], precedent=v[2], ouverture=v[3], cloture=v[4], moyen=v[5], statut='coté')
        var = [x for x in tete if x > nums[5] and k[x] in 'PNE']
    vals = [nombre(tok[x], en) if k[x] != 'E' else None for x in var]
    if len(vals) >= 2: out['var_jour'], out['var_annee'] = vals[-2], vals[-1]
    elif len(vals) == 1: out['var_annee'] = vals[0]
    return _queue(out, tok, k, en, ih + 1)

def _decoller(t, lo, hi):
    """« 96 104 1 034 784 235 » = volume 96 104 et valeur 1 034 784 235 : coupe où valeur / volume tombe dans [lo, hi]."""
    g = t.split()
    for c in range(1, len(g)):
        if any(len(x) != 3 for x in g[c + 1:]) or any(len(x) != 3 for x in g[1:c]): continue
        vol, val = float(''.join(g[:c])), float(''.join(g[c:]))
        if vol > 0 and lo <= val / vol <= hi: return vol, val
    return None, None

def format_B(out, tok, k, en):
    # Précédent Ouv Clôt | Var | Volume Valeur | Référence | VarAn | Dividende Date | Rdt | PER
    i = 0; pre = []
    while i < len(k) and k[i] in 'NX': pre.append(tok[i]); i += 1
    if pre: out['precedent'] = nombre(pre[0], en)
    rest = pre[1:]
    if any(p in ('NC', 'SP') for p in rest): out['statut'] = [p for p in rest if p in ('NC', 'SP')][0]
    elif len(rest) >= 2: out.update(ouverture=nombre(rest[0], en), cloture=nombre(rest[1], en), statut='coté')
    if i < len(k) and k[i] in 'PE': out['var_jour'] = nombre(tok[i], en) if k[i] == 'P' else None; i += 1
    mid = []
    while i < len(k) and k[i] in 'NM':
        if k[i] == 'M': out['marque_ref'] = tok[i]
        else: mid.append(i)
        i += 1
    if len(mid) >= 4 and i < len(k) and k[i] == 'D':           # titre récent : pas de variation annuelle, le dividende suit la référence
        out['dividende'] = nombre(tok[mid[3]], en); mid = mid[:3]
    if len(mid) >= 3: out.update(volume=nombre(tok[mid[0]], en), valeur=nombre(tok[mid[1]], en), reference=nombre(tok[mid[2]], en))
    elif len(mid) == 2 and out.get('cloture'):                   # volume et valeur collés
        p = [x for x in (out.get('ouverture'), out.get('cloture')) if x]
        vol, val = _decoller(tok[mid[0]], min(p) * 0.85, max(p) * 1.15)
        if vol: out.update(volume=vol, valeur=val)
        out['reference'] = nombre(tok[mid[1]], en)
    elif len(mid) >= 1: out['reference'] = nombre(tok[mid[-1]], en)
    if i < len(k) and k[i] in 'PE': out['var_annee'] = nombre(tok[i], en) if k[i] == 'P' else None; i += 1
    if i < len(k) and k[i] in 'NE' and i + 1 < len(k) and k[i + 1] == 'D':
        if k[i] == 'N': out['dividende'] = nombre(tok[i], en)
        out['date_dividende'] = tok[i + 1]; i += 2
    elif i < len(k) and k[i] == 'D': out['date_dividende'] = tok[i]; i += 1
    if i < len(k) and k[i] == 'C': i += 1
    reste = [(tok[x], k[x]) for x in range(i, len(k))]
    if len(reste) >= 2:                                          # rendement puis PER
        r0, r1 = reste[0], reste[1]
        if r0[1] in 'PN': v = nombre(r0[0], en); out['rendement'] = v * 100 if (en and r0[1] == 'N' and v is not None and v < 1) else v
        if r1[1] == 'N': out['per'] = nombre(r1[0], en)
    elif len(reste) == 1 and reste[0][1] == 'N': out['per'] = nombre(reste[0][0], en)   # titre sans dividende : seul le PER
    elif len(reste) == 1 and reste[0][1] == 'P': out['rendement'] = nombre(reste[0][0], en)
    return out

def mode_nombres(texte):
    """Séparateurs du bulletin : 'dot' (1.234.567), 'en' (1,234,567 et 4.05 %) ou 'fr' (1 234 567 et 4,05 %)."""
    if len(re.findall(r"\b\d{1,3}\.\d{3}\.\d{3}\b", texte)) >= 5: return 'dot'
    n_en = len(re.findall(r"\b\d{1,3},\d{3}(?:,\d{3})*\b(?!\s?%)", texte)) + len(re.findall(r"\d\.\d{1,2}\s?%", texte))
    n_fr = len(re.findall(r"\d,\d{1,2}\s?%", texte)) + len(re.findall(r"\b\d{1,3} \d{3}\b", texte)) // 5
    return 'en' if n_en > n_fr else 'fr'

def lire_bulletin(texte, date, fichier):
    en = mode_nombres(texte)
    lignes = []
    for l in texte.splitlines():
        if re.search(r"OBLIGATION", l, re.I) and lignes:
            if len(lignes) >= 20: break                               # fin du marché des actions
            lignes = []                                               # section annexe (carnet) avant la cote : on la jette
        m = RE_TICK.match(l)
        if not m: continue
        secteur, sym, rest = m.groups()
        if sym in NON_TITRES: continue
        if "/" in rest: continue          # carnet d'ordres (8350 / 8490) ou annonce datée : jamais dans la cote
        en_l = en
        if en != 'dot':                                       # certains bulletins mélangent les deux conventions
            if re.search(r"\d,\d{1,2}\s?%", rest): en_l = 'fr'
            elif re.search(r"\d\.\d{1,2}\s?%|\b\d{1,3},\d{3}\b", rest): en_l = 'en'
        out, tok, k = lire_ligne(rest, en_l, sym)
        if len(tok) < 3: continue
        j = 0
        while j < len(k) and k[j] in 'NX': j += 1
        run = k[:j]
        fmt = 'A' if (run.count('X') >= 3 or run.count('N') >= 5) else 'B'
        out = (format_A if fmt == 'A' else format_B)(out, tok, k, en_l)
        out.update(date=date, symbole=sym, secteur=secteur or '', format=fmt, fichier=fichier,
                   brut=' | '.join(tok))
        lignes.append(out)
    return lignes

def format_A_v1(out, tok, k, en):
    # Volume Valeur Précédent Ouv Clôt Moy | Var | VarAn | Référence [Ex-c] Bas Haut | Dividende Date | Comp | Rdt | PER
    i = 0; pre = []
    while i < len(k) and k[i] in 'NX': pre.append(tok[i]); i += 1
    if any(p in ('NC', 'SP') for p in pre):
        nums = [p for p in pre if p not in ('NC', 'SP')]
        out['statut'] = [p for p in pre if p in ('NC', 'SP')][0]
        if len(nums) >= 1: out['precedent'] = nombre(nums[-1], en)
        if len(nums) >= 3: out['volume'], out['valeur'] = nombre(nums[0], en), nombre(nums[1], en)
    else:
        n = [nombre(p, en) for p in pre]
        if len(n) >= 6: out.update(volume=n[-6], valeur=n[-5], precedent=n[-4], ouverture=n[-3], cloture=n[-2], moyen=n[-1])
        elif len(n) == 4: out.update(precedent=n[0], ouverture=n[1], cloture=n[2], moyen=n[3])
    pcts = []
    while i < len(k) and k[i] == 'P': pcts.append(nombre(tok[i], en)); i += 1
    if len(pcts) == 2: out['var_jour'], out['var_annee'] = pcts
    elif len(pcts) == 1: out['var_annee'] = pcts[0]
    post = []
    while i < len(k) and k[i] in 'NM':
        if k[i] == 'M': out['marque_ref'] = tok[i]
        else: post.append(nombre(tok[i], en))
        i += 1
    for nom, v in zip(['reference', 'bas', 'haut', 'dividende'], post): out[nom] = v
    if i < len(k) and k[i] == 'D': out['date_dividende'] = tok[i]; i += 1
    if i < len(k) and k[i] == 'C': out['compartiment'] = tok[i]; i += 1
    if i < len(k) and k[i] == 'P': out['rendement'] = nombre(tok[i], en); i += 1
    if i < len(k) and k[i] == 'N': out['per'] = nombre(tok[i], en)
    if 'statut' not in out and 'cloture' in out: out['statut'] = 'coté'
    return out


def main():
    zipf = sys.argv[1]; sortie = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else '.'
    depuis = sys.argv[sys.argv.index('--depuis') + 1] if '--depuis' in sys.argv else '20130916'
    z = zipfile.ZipFile(zipf)
    noms = sorted(n for n in z.namelist() if re.match(r"(?i)boc_\d{8}(_\d)?\.pdf$", n))
    noms = [n for n in noms if re.search(r"(\d{8})", n).group(1) >= depuis]
    # même date en double (fichier _2 = réédition) : on garde la dernière version
    par_date = {}
    for n in noms: par_date[re.search(r"(\d{8})", n).group(1)] = n
    print(f"{len(par_date)} bulletins à lire", flush=True)
    toutes = []
    with tempfile.TemporaryDirectory() as tmp:
        for j, (d, n) in enumerate(sorted(par_date.items())):
            p = os.path.join(tmp, 'b.pdf'); open(p, 'wb').write(z.read(n))
            txt = subprocess.run(['pdftotext', '-layout', p, '-'], capture_output=True, text=True, errors='ignore').stdout
            toutes += lire_bulletin(txt, pd.Timestamp(d).date(), n)
            if j % 200 == 0: print(f"  {j}/{len(par_date)}  {d}  {len(toutes)} lignes", flush=True)
    df = pd.DataFrame(toutes)
    cols = ['date', 'symbole', 'titre', 'secteur', 'statut', 'precedent', 'ouverture', 'cloture', 'moyen', 'var_jour', 'volume', 'valeur',
            'reference', 'marque_ref', 'marques', 'var_annee', 'bas', 'haut', 'dividende', 'date_dividende', 'compartiment', 'rendement', 'per',
            'format', 'fichier', 'brut']
    df = df[[c for c in cols if c in df]].drop_duplicates(['date', 'symbole'])
    os.makedirs(sortie, exist_ok=True)
    df.to_csv(os.path.join(sortie, 'boc_actions.csv'), index=False)
    print(f"écrit : {len(df)} lignes, {df.symbole.nunique()} titres, {df.date.nunique()} séances", flush=True)

if __name__ == '__main__':
    main()
