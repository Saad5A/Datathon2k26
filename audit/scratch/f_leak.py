"""Follow-up audit: solo AUC of the two new leakage-table rows on the 2025 test pool (= fold-1 test rows).
txt: auditor's masked TF-IDF+LR (p3_rederive.text, fit on fold-1 train with labels capped 2024-12-31).
asg_rate_24m: auditor's own 24-month window (p3_pool.parquet asg24_rate, KEV CVEs published 2021+, i.e. D1) plus the all-KEV variant."""
import sys, numpy as np
S = "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch/"
sys.path.insert(0, S)
import p3_rederive as P
from mymetrics import auc
tr, te, ytr = P.fold("fold1")
assert len(te) == 35280 and te.y.sum() == 52
_, st = P.text(tr, te, ytr, 0)
_, st1 = P.text(tr, te, ytr, 3)
y = te.y.to_numpy()
print("txt_masked_tfidf", round(auc(y, st), 6), "seed-independent:", np.allclose(st, st1))
print("asg_rate_24m (D1, 2021+ KEV CVEs)", round(auc(y, te.asg24_rate.to_numpy()), 6))
print("asg_rate_24m variant, all KEV additions", round(auc(y, te.asg24_rate_all.to_numpy()), 6))
