# Detector variants for small weeds (18 Oct 2026, RTX 5050, eval_manifest_v2)

Sugar beet, 30 images, 93 crop plants, 282 weeds. Same metric as the baseline. All runs include the 'not one plant' rule (masks over 50% of the photo withheld).

```
detector     setting                crop sprayed weed recall  saved crop plants weeds hit  s/img
b0.35_t1     gate_0.35                     70.79        9.03   93.0       45/93     7/282   0.58
b0.35_t1     gate_0.50                     20.52        6.77  97.95        8/93     1/282   0.58
b0.35_t1     gate_0.35+exclusion           50.11        9.03   94.9       38/93     7/282   0.58
b0.35_t1     gate_0.50+exclusion            5.25        6.77  99.32        2/93     1/282   0.58
b0.35_t1     cotton gate_0.35                  -         0.0
b0.20_t1     gate_0.35                     70.79        9.03   93.0       45/93     7/282   1.03
b0.20_t1     gate_0.50                     20.52        6.77  97.95        8/93     1/282   1.03
b0.20_t1     gate_0.35+exclusion           24.65        2.34   97.2       31/93     3/282   1.03
b0.20_t1     gate_0.50+exclusion             0.0        0.35  99.99        0/93     0/282   1.03
b0.20_t1     cotton gate_0.35                  -         0.0
b0.35_t2     gate_0.35                     74.57       10.12   92.4       49/93    10/282   3.76
b0.35_t2     gate_0.50                     22.51        6.77  97.74       11/93     1/282   3.76
b0.35_t2     gate_0.35+exclusion           56.01        3.71  94.31       46/93     9/282   3.76
b0.35_t2     gate_0.50+exclusion            8.39        0.37  99.22        7/93     0/282   3.76
b0.35_t2     cotton gate_0.35                  -         0.0
b0.20_t2     gate_0.35                     74.57       10.12   92.4       49/93    10/282   7.43
b0.20_t2     gate_0.50                     22.51        6.77  97.74       11/93     1/282   7.43
b0.20_t2     gate_0.35+exclusion           28.14        3.07  96.81       40/93     6/282   7.43
b0.20_t2     gate_0.50+exclusion            1.18         0.0  99.86        4/93     0/282   7.43
b0.20_t2     cotton gate_0.35                  -         0.0

```

b = detector score cut-off, t = tiles per side. Result: neither tiling nor a lower cut-off raises weed recall; the detector finds more plants but labels them no better, and extra crop masks remove weed pixels under crop exclusion. Default detector (b0.35, t1) kept; best measured setting so far: gate 0.50 + crop exclusion (5.3% crop pixels sprayed, 6.8% weed recall).
