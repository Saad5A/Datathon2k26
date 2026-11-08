import json, glob, collections
R='/Users/aahmad/Working/datathon/code/Datathon2k26/'
C={}
for f in glob.glob(R+'results/claims*.json'):
    for k,v in json.load(open(f)).items():
        if k in C: print('DUP', k, f)
        C[k]=dict(v, _file=f.split('/')[-1])
st=collections.Counter((v['_file'],v.get('status')) for v in C.values())
for k,v in sorted(st.items()): print(k,v)
bs=json.load(open(R+'results/backtest_summary.json'))
def walk(vals, ids, path):
    if isinstance(ids, dict):
        for k,i in ids.items(): walk(vals.get(k) if isinstance(vals,dict) else None, i, path+'.'+k)
    elif isinstance(ids, list):
        for j,(a,b) in enumerate(zip(vals, ids)): walk(a,b,path+f'[{j}]')
    elif ids is None:
        print('NULL', path, vals)
    else:
        c=C.get(ids)
        if c is None: print('MISSING', path, ids); return
        ok = abs(float(c['value'])-float(vals))<1e-9
        if not ok or c['status']!='verified': print('BAD', path, ids, vals, c['value'], c['status'])
n=0
for fold in ('fold1','fold2'):
    F=bs[fold]
    walk(F, F['claim_ids'], fold)
    for m,v in F.items():
        if isinstance(v,dict) and 'claim_ids' in v:
            walk(v, v['claim_ids'], fold+'.'+m)
            # values without claim_ids key
            for k in v:
                if k not in v['claim_ids'] and k not in ('claim_ids','label'): print('NOID', fold, m, k)
print('done')
