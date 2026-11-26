# Données historiques des sociétés cotées à la BRVM

Quatre bases construites à partir des publications officielles de la Bourse Régionale des Valeurs Mobilières
(BRVM) et des sociétés cotées : les cours de chaque séance, les dividendes, les opérations sur le nombre d'actions
(fractionnements, attributions gratuites) et les états financiers annuels.

Numérisation et vérification : Oumar Dicko.

| Dossier | Contenu | Période |
|---|---|---|
| `prix/` | cours de chaque titre à chaque séance, lus dans les Bulletins Officiels de la Cote (BOC) | 16/09/2013 → 25/11/2026 |
| `dividendes/` | dividendes versés, avec date d'ex-dividende, date de paiement et date de première annonce | 12/04/2013 → 26/10/2026 |
| `fractionnements/` | fractionnements, attributions gratuites et augmentations de capital, avec le facteur d'ajustement | 23/11/2012 → 26/10/2026 |
| `etats_financiers/` | bilan, compte de résultat et tableau des flux de 50 sociétés (dont des sociétés radiées) | exercices 1998 → 2025 |
| `scripts/` | lecture des PDF des bulletins, contrôles, téléchargement | |

Les cours de `prix/` sont **bruts**, tels que publiés. Pour obtenir des cours comparables dans le temps,
on les ajuste avec `dividendes/` et `fractionnements/`.

**Les documents officiels (PDF)** — un bulletin par séance, avis et communiqués de la BRVM — sont sur Hugging Face,
avec la description complète de chaque colonne :

- prix : [OumarDicko/brvm-prix-historiques](https://huggingface.co/datasets/OumarDicko/brvm-prix-historiques) (mis à jour chaque séance)
- dividendes : [OumarDicko/brvm-dividendes](https://huggingface.co/datasets/OumarDicko/brvm-dividendes)
- fractionnements : [OumarDicko/brvm-fractionnements](https://huggingface.co/datasets/OumarDicko/brvm-fractionnements)
- états financiers : [OumarDicko/brvm-financial-statements](https://huggingface.co/datasets/OumarDicko/brvm-financial-statements) (avec le JSON d'origine et des CSV)

Ce dépôt GitHub en est une copie mensuelle, archivée sur Zenodo avec un DOI pour pouvoir être citée.

## Fichiers

| Fichier | Contenu |
|---|---|
| `prix/boc_actions.parquet` | une ligne par titre et par séance : ouverture, clôture, volume, valeur, référence, marques… |
| `prix/manifeste_bulletins.csv` | pour chaque séance : PDF, source, adresse d'origine |
| `prix/corrections.csv` | valeurs corrigées : valeur lue, valeur retenue, raison |
| `dividendes/dividendes.csv` | un dividende par ligne, avec le document qui le prouve |
| `dividendes/manifeste_pdf.csv` | adresse d'origine et empreinte SHA-256 de chaque PDF |
| `fractionnements/ajustements.csv` | une opération par ligne, avec son facteur |
| `fractionnements/manifeste_pdf.csv` | adresse d'origine et empreinte SHA-256 de chaque PDF |
| `etats_financiers/etats_financiers_long.parquet` | une ligne par société, état, exercice et poste (FCFA, en unités) |
| `etats_financiers/bilan.parquet`, `compte_de_resultat.parquet`, `flux_de_tresorerie.parquet` | les mêmes données, une colonne par poste |

## Contrôles

- Prix : le cours précédent d'une séance est égal à la référence de la séance d'avant pour 99,7 % des lignes
  cotées ; le reste correspond aux jours de détachement. Pour chaque bulletin, la date imprimée a été comparée
  à la date attendue. Les erreurs trouvées, y compris celles du bulletin lui-même, sont listées dans
  `prix/corrections.csv`.
- Dividendes : la date d'ex-dividende est lue dans le document cité (« vérifié ») ou déduite (« non vérifié »,
  18 lignes).
- Fractionnements : chaque ligne s'appuie sur les bulletins de la veille et du jour, et sur l'avis de la BRVM
  ou le communiqué.
- États financiers : pour les 1 020 bilans où les deux totaux sont renseignés, total actif = total passif et
  capitaux propres, sans écart. La date de publication des comptes n'est pas dans la base : pour un backtest,
  appliquer un décalage prudent.

Les limites connues (séances sans bulletin, colonne `valeur` non contrôlée…) sont détaillées sur les pages
Hugging Face de chaque base.

## Exemple

```python
import pandas as pd
prix = pd.read_parquet("prix/boc_actions.parquet")
div = pd.read_csv("dividendes/dividendes.csv", parse_dates=["ex"])
aj = pd.read_csv("fractionnements/ajustements.csv", parse_dates=["date_effet"])
ef = pd.read_parquet("etats_financiers/etats_financiers_long.parquet")
sonatel = prix[prix.symbole == "SNTS"][["date", "ouverture", "cloture", "volume"]]
```

## Licence et citation

- Données : [CC-BY-4.0](LICENCE_CC-BY-4.0.txt). Libre réutilisation, à condition de citer la source.
- Scripts : [Apache-2.0](scripts/LICENCE_Apache-2.0.txt).

Pour citer : voir `CITATION.cff` (bouton « Cite this repository » de GitHub) ou le DOI Zenodo.

Sources : publications des sociétés cotées (brvm.org) pour les états financiers ; Bulletins Officiels de la Cote, avis et calendriers de la BRVM (brvm.org, bfin.brvm.org) ; archive des
bulletins 2010-2025 de lamekemal sur Hugging Face (`lamekemal/brvm-reports-pdfs`, licence Apache 2.0) ;
Abidjan.net ; leFaso.net.

---

## English summary

Historical data on the companies listed on the BRVM (Bourse Régionale des Valeurs Mobilières, the regional stock
exchange of the eight WAEMU countries), built from the exchange's official documents:

- `prix/`: daily open, close, volume, turnover and reference price of every listed share, digitised from the
  Official Price Bulletins (BOC), September 2013 to November 2026;
- `dividendes/`: dividends with ex-date, payment date and first announcement date;
- `fractionnements/`: stock splits, bonus issues and rights issues, with adjustment factors;
- `etats_financiers/`: annual balance sheets, income statements and cash-flow statements of 50 companies,
  including delisted ones, fiscal years 1998 to 2025.

Prices are raw (unadjusted). Price, dividend and split rows point to their source document; the PDFs are on Hugging Face (links above).
Data under CC-BY-4.0, scripts under Apache-2.0.
