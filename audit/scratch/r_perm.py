"""Label-permutation control for the reverse-time C1 fit: shuffle 2025 train labels, seeds 0-2."""
import sys, numpy as np
sys.argv = ["x"]; sys.path.insert(0, "/Users/aahmad/Working/datathon/code/Datathon2k26/audit/scratch")
import r_run as A
from joblib import Parallel, delayed
def go(k):
    A.ytr = np.random.default_rng(1000 + k).permutation(A.tr.y.to_numpy())
    return float(A.M.auc(A.y, A.c1(k)))
print("permuted-label C1 AUC on 2024:", Parallel(n_jobs=3)(delayed(go)(k) for k in range(3)))
