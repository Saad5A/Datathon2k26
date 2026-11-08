#!/usr/bin/env python3
"""Fail if a document contains a number not supported by a VERIFIED claim in results/claims.json.
Usage: python tools/check_claims.py WRITEUP.md DEVPOST.md ...
Allowed without a claim: years 1990-2030, integers 0-10, and numbers listed in tools/claims_exempt.txt (one per line).
A number matches a claim if, at the number's printed precision, it equals the claim value, the value*100 (fractions), or value/1000, value/1e6."""
import json, re, sys, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
claims = {}
for f in sorted((root/'results').glob('claims*.json')):
    claims.update({f'{f.stem}:{k}': v for k, v in json.loads(f.read_text(encoding='utf-8')).items()})
vals = [float(c['value']) for c in claims.values() if c.get('status') == 'verified' and isinstance(c.get('value'), (int, float))]
ex = root/'tools'/'claims_exempt.txt'
exempt = {l.strip() for l in ex.read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')} if ex.exists() else set()
pat = re.compile(r'(?<![\w.])(\d[\d,]*(?:\.\d+)?)(\s?%|[kKmM]\b)?')
def ok(tok, suf):
    raw = tok.replace(',', '')
    if raw in exempt or tok in exempt: return True
    x = float(raw); dec = len(raw.split('.')[1]) if '.' in raw else 0
    if '.' not in raw and (x <= 10 or 1990 <= x <= 2030): return True
    mult = {'k': 1e3, 'K': 1e3, 'm': 1e6, 'M': 1e6}.get((suf or '').strip(), 1)
    x *= mult
    pct = (suf or '').strip() == '%'
    for v in vals:
        cands = [v, v*100, v/1000, v/1e6]
        if pct: cands = [v*100, v]
        for c in cands:
            if round(c, dec) == round(x, dec) or (dec == 0 and abs(c - x) < 0.5 + 1e-9 and abs(c) >= 1): return True
    return False
bad = 0
for f in sys.argv[1:]:
    p = pathlib.Path(f)
    if not p.exists(): print(f'SKIP (missing): {f}'); continue
    for i, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
        if line.lstrip().startswith(('#', '|---')) and not re.search(r'\d', line): continue
        for m in pat.finditer(line):
            if not ok(m.group(1), m.group(2)):
                bad += 1; print(f'{f}:{i}: unsupported number "{m.group(0).strip()}" -> {line.strip()[:110]}')
print(f'{bad} unsupported number(s)'); sys.exit(1 if bad else 0)
