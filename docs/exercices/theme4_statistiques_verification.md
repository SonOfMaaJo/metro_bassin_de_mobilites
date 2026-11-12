# Thème 4 — Statistiques de vérification / cohérence

> Voir [README](README.md) pour l'environnement de travail.

> **Rappel d'échelle** (comme au Thème 3) : tous les fichiers de ce thème sont issus de
> `bassin/output_de/`, à l'échelle simulée `simulation_ratio = 0.2`. Le chiffre `31 621` cité
> ci-dessous est l'estimation à échelle réelle (issue de la Tâche #9, calculée sur la population
> synthétique complète du Thème 2) — pour le comparer à un comptage fait sur ce thème, il faut le
> multiplier par `0.2`, pas l'inverse.

## Ex00 — Recompter les trajets frontaliers à zone nulle

**Objectif** : reproduire, à partir des fichiers bruts, un chiffre déjà établi lors d'une
vérification antérieure du projet (Tâche #9), et comprendre pourquoi compter des *trajets* n'est
pas la même chose que compter des *personnes*.

**Contraintes** :
- Deux fichiers à joindre sur `trip_id` : `bassin/output_de/demand/population/trips.parquet`
  (contient `destination_purpose_group`, pas de zone) et
  `bassin/output_de/demand/population/trips_zones.parquet` (contient les zones, pas le motif du
  trajet) — **piège** : aucun des deux fichiers seul ne suffit, il faut un `.join(on="trip_id")`.
- La colonne de motif s'appelle `destination_purpose_group` (valeurs : `work`, `home`, `education`,
  `shop`, `leisure`, `other`) — pas `purpose` tout court, contrairement à `trip_results.parquet` du
  Thème 3.
- Utilise `destination_zone5` (le niveau de zone le plus fin, code commune) pour repérer les zones
  nulles — pas `destination_zone1` (bien plus grossier, région).

**Recherche imposée sourcée** : néant pour cet exercice (reproduction directe d'un calcul déjà
documenté dans les notes de la Tâche #9 du projet) — mais formule ta propre explication écrite (pas
copiée) de pourquoi une commune allemande génère une zone nulle à ce stade du pipeline (repense au
Thème 2 : `FrenchTripsZonesStep` ne connaît que les zones françaises).

**Exemple de sortie attendue** (calculé sur les fichiers réels) :
```
total trajets work (échelle simulée) : 154586
trajets work à destination_zone5 nulle : 6713
comparaison : 31621 x 0.2 = 6324.2   →   écart observé : +6.1%

en comptant les PERSONNES distinctes plutôt que les trajets :
personnes distinctes parmi ces trajets à zone nulle : 4231
(6713 trajets / 4231 personnes ≈ 1.59 trajet par personne concernée — cohérent avec le fait
qu'un frontalier fait un aller ET un retour, voire plus avec des détours domicile-travail)
```

**Rendu** : `exercices/theme4/ex00_recompte_zone_nulle.py` + les 4 chiffres ci-dessus + 2-3 phrases
d'explication de l'écart trajets/personnes.

---

## Ex01 — Le +6 % est-il du bruit d'échantillonnage ?

**Objectif** : au lieu de se contenter de constater un écart de +6 %, quantifier s'il est
compatible avec le bruit attendu d'un tirage aléatoire à 20 %, ou s'il révèle autre chose.

**Contraintes** :
- Modélise le sous-échantillonnage à `simulation_ratio = 0.2` comme un tirage binomial : si la
  population réelle contient `K = 31621` trajets frontaliers work, et que chaque trajet a une
  probabilité `p = 0.2` d'être tiré dans l'échantillon simulé indépendamment des autres, le nombre
  de trajets tirés suit une loi `Binomiale(K, p)`.
- Calcule l'espérance (`K·p`) et l'écart-type (`√(K·p·(1-p))`) de cette loi, puis le **z-score** de
  la valeur observée (`(observé - espérance) / écart-type`).
- Piège : ne confonds pas écart-type de la loi binomiale (dépend de `K`, pas de l'échantillon
  observé) et écart-type empirique d'une série de mesures — ici il n'y a qu'une seule mesure (une
  seule simulation), donc c'est bien la formule binomiale théorique qu'il faut utiliser, pas
  `numpy.std` sur une liste.

**Recherche imposée sourcée** : cherche la règle empirique sur le z-score en statistique
(pourquoi `|z| > 3` ou `|z| > 5` est généralement considéré comme largement incompatible avec une
simple fluctuation aléatoire, dans le contexte d'un test d'hypothèse sur une proportion/loi
binomiale) — une source de cours de stats ou de méthodo quantitative suffit.

**Exemple de sortie attendue** (calcul réel) :
```
K = 31621, p = 0.2
espérance = K x p = 6324.2
ecart-type = sqrt(K x p x (1-p)) = 71.13
observé = 6713
z-score = (6713 - 6324.2) / 71.13 ≈ 5.47
```
Un `z` de cet ordre est loin des fluctuations typiques d'un tirage aléatoire pur (`|z| > 3` est déjà
rare) — **conclusion attendue : l'écart de +6 % n'est probablement pas que du bruit
d'échantillonnage**, il y a une explication plus structurelle à chercher (par exemple : une
différence de méthode ou de date entre le chiffre `31 621` et la population réellement simulée,
cf. Thème 2). Le but de l'exercice n'est pas de trouver *laquelle* avec certitude, mais de savoir
distinguer un écart "dans le bruit" d'un écart qui ne l'est pas.

**Rendu** : `exercices/theme4/ex01_intervalle_confiance.py` + le z-score + 2-3 phrases de
conclusion (bruit ou pas bruit, et pourquoi).

---

## Ex02 — Deux méthodes de comptage, même fichier

**Objectif** : vérifier si compter par "zone de destination nulle" (Ex00) donne le même résultat
qu'une jointure spatiale directe sur les polygones des communes allemandes (comme au Thème 2,
Ex04) — cette fois sur les données de ce thème (échelle simulée), pas sur la sortie eqasim-france
brute.

**Contraintes** :
- Géométries des trajets : `bassin/output_de/demand/population/trip_destinations.geo.parquet`
  (une géométrie point par `trip_id`, CRS déjà en `EPSG:2154`).
- Polygones allemands : `eqasim-france-data/german/german_gemeinden_8kreise.geojson` (à reprojeter
  dans le même CRS avant la jointure — même piège qu'au Thème 2).
- Restreins-toi aux `trip_id` déjà identifiés en Ex00 (motif `work`, `destination_zone5` nulle)
  avant de faire la jointure spatiale — sinon tu jointes inutilement 878 366 lignes.

**Recherche imposée sourcée** : aucune nouvelle recherche externe requise ici — relis plutôt ta
propre explication du Thème 2 Ex04 (§ sur le géocodage centroïde) pour comprendre pourquoi, à ce
stade avancé du pipeline (après `FrenchTripsZonesStep`), les deux méthodes peuvent converger
totalement alors qu'elles ne coïncidaient pas exactement plus en amont dans le pipeline.

**Exemple de sortie attendue** (calcul réel, sur les 6713 trajets d'Ex00) :
```
méthode A (destination_zone5 nulle)        : 6713
méthode B (jointure spatiale dans un polygone allemand) : 6713
écart : 0 (0.00%)
```
**Résultat notable** : contrairement au Thème 2 (Ex04), où la jointure spatiale sur la sortie brute
eqasim-france laissait 11 points non matchés (hors de tout polygone Gemeinde), ici l'écart est
**exactement nul**. Explique en une phrase pourquoi ce résultat est plausible à ce stade (indice :
`FrenchTripsZonesStep` n'attribue une zone nulle que si le point tombe hors de la zone de
simulation française ; combiné au fait que les seuls points hors zone française dans ce jeu de
données *sont*, par construction du patch, en Allemagne).

**Rendu** : `exercices/theme4/ex02_comparaison_methodes.py` + les 3 chiffres + l'explication.

---

## Ex03 — Retrouver une statistique du rapport pymetropolis

**Objectif** : partir d'un chiffre affiché dans `report.html` (le rapport HTML auto-généré par
pymetropolis) et le recalculer depuis les fichiers parquet bruts — vérifie que tu sais remonter
d'un résumé à sa donnée source, et que tu sais repérer quand deux chiffres *censés* représenter la
même chose ne coïncident pas exactement (et pourquoi).

**Contraintes** :
- `report.html` est un fichier HTML généré automatiquement (`bassin/output_de/run/output/`, section
  "Last Iteration" → tableau "Road-trips level") — ouvre-le dans un navigateur ou parse-le en
  Python (`re` suffit pour extraire le texte, pas besoin de `BeautifulSoup`).
- Piège : le rapport contient plusieurs tableaux qui se ressemblent (Alternative-level,
  Road-trips level, Virtual-trip level) — vérifie bien dans quelle section se trouve la statistique
  que tu choisis avant de la recalculer.
- Recalcule ta statistique à partir de `bassin/output_de/results/trip_results.parquet`
  (colonnes `is_road`, `route_length`, `nb_edges`, `travel_time` — filtre `is_road == True` pour
  ne garder que les trajets routiers).

**Recherche imposée sourcée** : néant — l'exercice porte sur la lecture croisée de deux sorties du
même outil, pas sur une recherche externe.

**Exemple de sortie attendue** (statistique choisie : longueur moyenne des trajets routiers) :
```
depuis trip_results.parquet (is_road == True) :
  n trajets routiers = 571803
  route_length moyen = 9949.67 m  (~9.95 km)
  nb_edges moyen = 64.03

à comparer à la section "Road-trips level" de report.html :
  # Trips = 580676   (≠ 571803 !)
```
**Remarque attendue** : les deux comptages de "trajets routiers" ne coïncident pas exactement
(571 803 vs 580 676, écart d'environ 1,5 %). C'est le résultat normal de l'exercice, pas une
erreur de ta part — les deux fichiers ne comptent pas exactement la même chose (`trip_results.parquet`
donne les trajets *réalisés* dans la dernière itération simulée, alors que le tableau du rapport
peut inclure des alternatives ou un grain de comptage légèrement différent au niveau agent). Le but
est de documenter précisément *quel* chiffre tu as recalculé, *lequel* du rapport tu compares, et
de formuler une hypothèse sur l'origine de l'écart plutôt que de forcer les deux chiffres à
coïncider.

**Rendu** : `exercices/theme4/ex03_traceabilite_rapport.py` + la statistique choisie, sa valeur
recalculée, la valeur du rapport, et ton hypothèse sur l'écart (même s'il est nul pour la
statistique que tu as choisie — dans ce cas, dis pourquoi elle coïncide exactement).

---

## Grille d'auto-correction — Thème 4

- [ ] Ex00 : jointure `trips.parquet` × `trips_zones.parquet` sur `trip_id` correcte, comptage sur
      `destination_zone5` (pas un autre niveau), écart avec `31621 x 0.2` retrouvé (~+6%),
      distinction trajets/personnes expliquée avec le bon ratio (~1.59).
- [ ] Ex01 : formule binomiale correcte (espérance `K·p`, écart-type `√(K·p·(1-p))`), z-score
      calculé (~5.5), conclusion cohérente (écart trop grand pour être expliqué par le seul bruit
      d'échantillonnage — pas de conclusion du type "c'est juste du bruit").
- [ ] Ex02 : jointure spatiale restreinte aux bons `trip_id` (pas toute la table), CRS aligné avant
      jointure, écart de 0% retrouvé et expliqué (pas juste constaté).
- [ ] Ex03 : bonne section du rapport identifiée sans ambiguïté, recalcul depuis
      `trip_results.parquet` avec le bon filtre `is_road`, écart entre les deux sources documenté
      et une hypothèse formulée (que l'écart soit nul ou non pour la statistique choisie).
