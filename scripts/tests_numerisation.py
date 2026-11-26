"""Tests de cohérence de la base numérisée des BOC (ne corrige rien, liste les anomalies)."""
import pandas as pd,numpy as np
B=pd.read_csv("final_boc/boc_actions.csv",parse_dates=["date"],low_memory=False).sort_values(["symbole","date"]).reset_index(drop=True)
for c in ['precedent','ouverture','cloture','moyen','var_jour','volume','valeur','reference','bas','haut','dividende','rendement','per','var_annee']:
    B[c]=pd.to_numeric(B[c],errors='coerce')
out={}
def note(nom,m,cols=['date','symbole','statut','format','source']):
    x=B[m]; out[nom]=x; print(f'\n### {nom} : {m.sum()} lignes'); 
    if m.sum(): print('  par année',x.date.dt.year.value_counts().sort_index().to_dict()); print('  par format',x.format.value_counts().to_dict(),'| source',x.source.value_counts().to_dict())
cote=B.statut.eq('coté')
# 1 statut manquant
note('statut absent',B.statut.isna())
# 2 coté sans clôture / sans ouverture / sans volume
note('coté sans clôture',cote&B.cloture.isna())
note('coté sans ouverture',cote&B.ouverture.isna())
note('coté sans volume',cote&(B.volume.isna()|(B.volume==0)))
# 3 NC/SP avec clôture
note('NC ou SP avec clôture',B.statut.isin(['NC','SP'])&B.cloture.notna())
# 4 ordre de grandeur : prix < 1 FCFA (séparateur de milliers mal lu)
note('prix < 5 FCFA (hors ETIT)',(B.symbole!='ETIT')&((B.precedent<5)|(B.cloture<5)|(B.reference<5)))
# 5 valeur/volume hors de la fourchette du jour
pm=B.valeur/B.volume; lo=B[['ouverture','cloture']].min(axis=1)*0.92; hi=B[['ouverture','cloture']].max(axis=1)*1.08
note('valeur/volume incohérent avec les cours',cote&B.volume.gt(0)&B.valeur.gt(0)&~pm.between(lo,hi))
# 6 variation du jour incohérente
vj=(B.cloture/B.precedent-1)*100
note('variation du jour incohérente (> 0,1 pt)',cote&B.var_jour.notna()&((vj-B.var_jour).abs()>0.1))
# 7 clôture hors limites ±7,5 % (à confirmer : ex-dividende et fractionnement exclus plus tard)
note('clôture hors ±7,5 % du précédent',cote&((B.cloture/B.precedent-1).abs()>0.0755))
# 8 bas/haut ≠ ±7,5 % de la référence
r=B.dropna(subset=['bas','haut','reference'])
m=pd.Series(False,index=B.index); m.loc[r.index]=((r.bas/r.reference-0.925).abs()>0.003)|((r.haut/r.reference-1.075).abs()>0.003)
note('limites bas/haut ≠ ±7,5 % de la référence',m)
# 9 référence ≠ clôture (cotée) hors marque de détachement
note('référence ≠ clôture sans marque',cote&B.reference.notna()&B.cloture.notna()&((B.reference-B.cloture).abs()>0.5)&B.marques.fillna('').eq('')&B.marque_ref.isna())
# 10 précédent ≠ dernier cours de la séance précédente (séances consécutives)
B['dern']=B.cloture.fillna(B.precedent); B['pd_']=B.groupby('symbole').dern.shift(); B['pref']=B.groupby('symbole').reference.shift()
note('précédent ≠ cours/référence de la veille',B.pd_.notna()&B.precedent.notna()&((B.precedent-B.pd_).abs()>0.5)&((B.precedent-B.pref).abs()>0.5))
# 11 nombre de titres par séance anormal
n=B.groupby('date').symbole.transform('size'); med=B.groupby(B.date.dt.year).symbole.transform(lambda s: 0)
cnt=B.groupby('date').size(); print('\n### séances avec moins de 35 titres :',cnt[cnt<35].to_dict())
# 12 dividende ou date de dividende manquants
note('dividende sans date ou date sans dividende',B.dividende.notna()!=B.date_dividende.notna())
pd.concat({k:v[['date','symbole','statut','format','source','precedent','ouverture','cloture','reference','volume','valeur','var_jour','brut']] for k,v in out.items()}).to_csv('/tmp/anomalies.csv')
