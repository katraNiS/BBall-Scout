# Defensive Matching — Impact Report

- Rows: **8382** | features: **23**
- Pre-tracking (<2016) share of dataset: **57.7%** — ένα αμερόληπτο query πρέπει να πλησιάζει αυτό το ποσοστό
- Max deflections: **5.89**/gm (NBA record ≈ 5.9· τιμές >6.5 σημαίνουν totals-scaled corruption)

## 1. Era balance ανά query type

Ποσοστό pre-2016 παικτών στα top-25.

| Query | Features | pre-tracking | Απόκλιση από baseline |
|---|---|---|---|
| 3-and-D wing | tracking-only | 44.0% | -13.7% |
| perimeter stopper | tracking-only | 44.0% | -13.7% |
| hustle big | tracking-only | 76.0% | +18.3% |
| 3-and-D (def_rating) | full-coverage | 48.0% | -9.7% |
| stopper (def_rating) | full-coverage | 72.0% | +14.3% |
| rim protector | full-coverage | 84.0% | +26.3% |
| elite team defender | full-coverage | 48.0% | -9.7% |
| elite shooter | offense (control) | 4.0% | -53.7% |
| lead playmaker | offense (control) | 64.0% | +6.3% |
| post scorer | offense (control) | 76.0% | +18.3% |

- Defensive queries με **deflections**: μέσο pre-tracking share **54.7%** _(ήταν 0.0% πριν το masking)_
- Defensive queries με **def_rating**: μέσο pre-tracking share **63.0%**

> Το `deflections` υπάρχει μόνο από το 2016-17. Πριν το availability-aware
> masking, κάθε imputed row καθόταν σε σταθερή απόσταση τιμωρίας και το era
> share κατέρρεε στο 0%. Τώρα το distance υπολογίζεται μόνο στις διαστάσεις
> με πραγματικά δεδομένα, και το score shrink-άρει προς το population prior
> ανάλογα με το coverage — ώστε τα ελλιπή rows να μην εκτοπίζουν όσα έχουν
> πλήρη δεδομένα.

### Confidence discount (`CONFIDENCE_ALPHA`)

`sim = sim_pop + coverage^α × (sim_masked − sim_pop)`

Ευαισθησία του era balance στο α, για το query «perimeter stopper»:

| α | pre-tracking | #1 result | coverage του #1 |
|---|---|---|---|
| 0.0 | 80.0% | Hersey Hawkins (1997-98) | 0.67 |
| 0.5 | 56.0% | Alex Caruso (2023-24) | 1.00 |
| 1.0  ← ενεργό | 44.0% | Alex Caruso (2023-24) | 1.00 |
| 1.5 | 28.0% | Alex Caruso (2023-24) | 1.00 |
| 3.0 | 0.0% | Alex Caruso (2023-24) | 1.00 |

> α=0 είναι σκέτο masking: υπερδιορθώνει, και rows με ελλιπή δεδομένα
> εκτοπίζουν παίκτες με πλήρη. α≥1.5 επαναφέρει τον αποκλεισμό.

## 2. Corrupt-season contamination (2015-16)

High-deflections query → **0/10** αποτελέσματα από το 2015-16 (πριν το fix: 5/10, με Curry/Harden/Butler ως «elite stoppers»).

| # | Player | Season | Pos | Similarity |
|---|---|---|---|---|
| 1 | Herbert Jones | 2024-25 | F | 0.6944 |
| 2 | Kelly Oubre Jr. | 2024-25 | G-F | 0.6425 |
| 3 | Robert Covington | 2016-17 | F | 0.5973 |
| 4 | Fred VanVleet | 2019-20 | G | 0.5821 |
| 5 | Jrue Holiday | 2019-20 | G | 0.5324 |
| 6 | Dejounte Murray | 2021-22 | G | 0.4789 |
| 7 | Paul George | 2024-25 | F | 0.4750 |
| 8 | John Wall | 2016-17 | G | 0.4473 |
| 9 | Ricky Rubio | 2016-17 | G | 0.4423 |
| 10 | Draymond Green | 2016-17 | F | 0.4407 |

## 3. Ξεχωρίζει το `def_rating` πραγματικούς αμυντικούς;

League mean def_rating: **106.1** (χαμηλό = καλύτερο)

| Query def_rating | Mean def_rating των top-25 | Διαφορά |
|---|---|---|
| 98 | 98.3 | -7.9 |
| 102 | 102.1 | -4.1 |
| 106 | 106.0 | -0.1 |
| 110 | 110.0 | +3.9 |

> Μονοτονική σχέση = το feature είναι πραγματικά διακριτικό, όχι noise.

