# Best lineage

| gen | operation | model | features | cap | top243 | top500 | AP |
|---:|---|---|---|---:|---:|---:|---:|
| 0 | init | logistic | signals,assigner24 | 50 | 13.5 | 17.5 | 0.06059371584007521 |
| 1 | copy+mutate | logistic | signals,assigner24 | 50 | 14.5 | 17.5 | 0.05400690949467874 |
| 5 | crossover+mutate | extra_trees | assigner24,signals | None | 14.5 | 18.5 | 0.05593788937021285 |
| 6 | crossover | extra_trees | assigner,assigner24,signals,text_tfidf | 75 | 14.5 | 18.5 | 0.08216212300786463 |
| 7 | crossover+mutate | extra_trees | assigner24,signals,text_tfidf | 75 | 15.5 | 18.5 | 0.09489431568260216 |
| 8 | crossover | extra_trees | assigner,assigner24,signals,text_tfidf | 50 | 15.0 | 19.0 | 0.09635546835265775 |
| 9 | copy+mutate | extra_trees | signals,assigner24 | 50 | 15.0 | 19.0 | 0.08015984991366883 |
| 10 | crossover | extra_trees | assigner24,signals | 50 | 14.5 | 19.0 | 0.05598808219138726 |
| 11 | copy+mutate | extra_trees | assigner24,signals | 50 | 14.5 | 19.0 | 0.05598808219138726 |
| 12 | crossover+mutate | extra_trees | assigner24,signals | 50 | 14.5 | 19.0 | 0.08232370939977787 |
| 13 | copy+mutate | extra_trees | assigner24,signals | 50 | 14.5 | 19.0 | 0.05598808219138726 |
| 14 | copy+mutate | extra_trees | signals,assigner,text_tfidf,assigner24 | 50 | 16.0 | 19.0 | 0.08565689199735085 |
| 17 | crossover+mutate | gam | assigner24,signals,text_tfidf | 50 | 18.0 | 18.5 | 0.12345709707655714 |
| 24 | crossover+mutate | gam | signals,assigner24,temporal,text_tfidf | 50 | 17.5 | 18.0 | 0.1395458728828725 |
| 25 | crossover | gam | assigner24,signals,temporal,text_tfidf | 50 | 18.0 | 18.5 | 0.13829223507746305 |
| 27 | copy+mutate | gam | assigner24,signals,temporal,text_tfidf | None | 18.0 | 19.5 | 0.13891548492458952 |
| 36 | crossover | gam | assigner24,signals,temporal | None | 18.0 | 19.5 | 0.13213215404570622 |
| 37 | crossover | gam | assigner24,signals,temporal | 75 | 18.0 | 20.0 | 0.1323221673844398 |
