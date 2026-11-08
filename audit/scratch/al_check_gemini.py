import json, sys, importlib.util
import pandas as pd
R='/Users/aahmad/Working/datathon/code/Datathon2k26'
spec=importlib.util.spec_from_file_location('b', R+'/scripts/build_gemini_from_granite.py'); b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
g=json.load(open(R+'/audit/scratch/al_granite_origin.json'))
gem=json.load(open(R+'/results/gemini_explanations_top100.json'))
df=pd.read_csv(R+'/results/scores_2026.csv'); sc={str(r['cve_id']):r.to_dict() for _,r in df.iterrows()}
fields=['gemini_technical_summary','gemini_executive_summary','gemini_triage_playbook','granite_technical_rationale']
match=0; diffs=[]
for k,v in g.items():
    s=b.synthesize(k,v,sc.get(k)); e=gem[k]
    ok=all(s[f]==e.get(f) for f in fields)
    match+=ok
    if not ok: diffs.append((k,[f for f in fields if s[f]!=e.get(f)]))
print('rows',len(g),'exact match',match); print(diffs[:3])
print('extra keys in file vs script', set(gem[next(iter(gem))])-set(s))
