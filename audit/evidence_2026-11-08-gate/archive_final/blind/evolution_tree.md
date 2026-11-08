# Best lineage

| gen | operation | model | features | cap | top243 | top500 | AP |
|---:|---|---|---|---:|---:|---:|---:|
| 0 | init | catboost | signals,text_tfidf | None | 10.5 | 12.0 | 0.09264437903801004 |
| 1 | crossover | catboost | signals | None | 13.5 | 15.0 | 0.04407337563612244 |
| 2 | crossover | gam | assigner24,signals,temporal,text_tfidf | None | 17.5 | 19.5 | 0.1398626431330616 |
| 8 | crossover | gam | assigner24,signals,temporal,text_tfidf | 100 | 17.5 | 19.0 | 0.13984334859433173 |
| 9 | crossover | gam | signals,temporal,text_tfidf | 100 | 16.5 | 19.0 | 0.12755318082443143 |
| 10 | copy+mutate | gam | signals,temporal,text_tfidf,assigner24 | 100 | 17.5 | 19.0 | 0.13984334859433173 |
| 11 | crossover | gam | assigner24,signals,text_tfidf | 50 | 18.0 | 18.5 | 0.12345709707655714 |
| 12 | copy+mutate | gam | signals,temporal | 50 | 16.0 | 17.5 | 0.10625517745869871 |
| 13 | crossover | gam | signals,temporal | 100 | 16.0 | 18.0 | 0.10652229965809457 |
| 14 | copy+mutate | gam | signals,temporal | 100 | 16.0 | 19.0 | 0.08247607618484945 |
| 15 | crossover+mutate | gam | signals,temporal | 75 | 16.0 | 18.5 | 0.08227718614684618 |
| 16 | crossover+mutate | gam | signals,assigner24,temporal | 75 | 17.5 | 19.5 | 0.11719602205932636 |
| 17 | crossover+mutate | gam | assigner24,signals,temporal,text_tfidf | 75 | 17.5 | 19.0 | 0.13321786059763524 |
| 18 | crossover | gam | assigner24,signals,temporal | 75 | 18.0 | 20.0 | 0.1323221673844398 |
