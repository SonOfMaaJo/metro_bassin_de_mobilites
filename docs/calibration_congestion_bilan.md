---
title: "Calibration des capacités routières : bilan détaillé"
subtitle: "Pipeline, historique et problèmes en cours"
date: \today
lang: fr
geometry: margin=2.5cm
fontsize: 11pt
colorlinks: true
---

# 1. Objectif

Le simulateur (Metropolis-Core) a besoin, pour chaque type de route (`edge_type` : motorway, trunk,
primary, secondary, tertiary, leurs variantes `_link`, plus `living_street`, `unclassified`,
`residential`, soit 13 catégories), d'une **capacité** en véhicules par heure. C'est cette capacité
qui détermine à partir de quand une route sature et produit de la congestion (modèle de goulot
d'étranglement, seuil dur : en dessous de la capacité, zéro congestion ; au-dessus, une file
d'attente se forme).

Les capacités par défaut ne sont pas calibrées pour notre réseau transfrontalier. L'objectif est de
les ajuster pour que le temps passé en congestion, dans nos simulations, corresponde à ce
qu'observe réellement TomTom sur le terrain. C'est la calibration dite "congestionnée" (la
calibration "free-flow" est déjà gérée nativement par pymetropolis, ce n'est pas le sujet ici).

Contrainte de départ : **ne pas modifier le code de pymetropolis**. Toute la calibration est donc un
pipeline de scripts externes, dans `~/stage/calibration_congestion/`, qui pilotent pymetropolis en
sous-processus et retraitent ses fichiers de sortie.

# 2. Le pipeline, étape par étape

## a) Collecte TomTom (`collect_tomtom_congested.py`)

On tire des paires origine-destination aléatoires sur le réseau et on interroge l'API TomTom pour
chacune, à une heure de départ aléatoire dans la journée (pour couvrir la variation de congestion au
fil de la journée). TomTom renvoie deux temps de trajet : `tt_no_traffic` (temps sans trafic) et
`tt_traffic` (temps réel observé). Le pilote actuel porte sur environ 2 500 requêtes, dimensionné
pour valider le pipeline avant d'investir plus de quota.

## b) Map-matching (`map_match_congested.py`)

Chaque trajet TomTom est une géométrie brute (une polyligne GPS), pas une suite d'arêtes du réseau.
Le map-matching la projette sur le graphe routier du bassin pour obtenir la vraie suite d'arêtes
empruntées (`path`, une liste d'`edge_id`). On filtre les trajets mal matchés (écart de longueur
entre la géométrie TomTom et le chemin retrouvé au-delà de 0,5 %).

## c) Réévaluation de la congestion simulée (`simulate_route_congestion.py`)

C'est l'étape la plus spécifique du pipeline. Plutôt que d'essayer de faire correspondre les trajets
TomTom à de vrais déplacements simulés (quasiment impossible, et sujet à la limitation qu'aucun mode
"camion" n'existe dans pymetropolis), on reprend le chemin map-matché de chaque route TomTom et on
le rejoue contre les fonctions de temps de trajet produites par la dernière simulation
(`net_cond_sim_edge_ttfs.parquet`, qui donne le temps de traversée de chaque arête en fonction de
l'heure).

On parcourt les arêtes du chemin dans l'ordre, en partant de l'heure de départ observée par TomTom,
en cumulant le temps réel de traversée à chaque arête (interpolé sur les points de la fonction
horaire) moins le temps free-flow de cette arête. On agrège cet écart par catégorie de route.
Résultat : pour chaque route TomTom, un vecteur de 13 valeurs (le temps de congestion simulé
imputable à chaque catégorie sur ce trajet). C'est la matrice `X`.

## d) Régression et mise à jour des capacités (`regress_and_update_capacities.py`)

On calcule `y = tt_traffic - tt_no_traffic` (la congestion réellement observée par TomTom) et on la
régresse sur `X` : *y ~ somme(delta_j * x_j)*, une régression Ridge sans intercept (`alpha=100`), qui tire les
coefficients *delta_j* mal déterminés vers 1 plutôt que de les laisser partir n'importe où.

Un *delta_j* proche de 1 veut dire que la capacité actuelle de cette catégorie est correcte. Un *delta_j*
différent de 1 indique un ajustement à faire : *nouvelle_capacité = ancienne_capacité / delta_j*.

Plusieurs garde-fous protègent cette mise à jour :

- **clamp** : *delta_j* appliqué borné à `[0,5 ; 2,0]` par itération, pour éviter un saut brutal.
- **relaxation EMA** (facteur 0,3) : le *delta_j* réellement appliqué combine le nouveau et l'ancien,
  pour lisser les oscillations d'une itération à l'autre.
- **`--min-observations`** : si une catégorie a moins de 20 observations, elle n'est pas mise à jour.
- **`--min-signal`** (garde-fou ajouté récemment) : si le temps de congestion simulé moyen pour cette
  catégorie (quand il est non nul) est trop proche de zéro, elle n'est pas mise à jour non plus.
  Détail au point 3.

## e) L'orchestrateur (`calibrate_congestion.py`)

Boucle : lancer pymetropolis (incrémental, seule la partie capacités puis simulation puis résultats
est rejouée), réévaluer la congestion simulée, régresser et mettre à jour les capacités dans la
config. Arrêt si *max|delta_j - 1| < 0,05* (calculé sur le *delta_j* brut, avant clamp et relaxation : à
l'équilibre, même l'estimation brute doit approcher 1) ou si le nombre maximal d'itérations (15) est
atteint.

# 3. Problème déjà rencontré et résolu : `living_street`, `secondary_link`, `tertiary_link`

Lors d'un premier essai (5 itérations), ces trois catégories divergeaient violemment (capacités
partant vers des valeurs aberrantes). Diagnostic : ce n'était pas un problème de mauvais
conditionnement (Ridge gère déjà ça), mais un problème de données. La congestion simulée sur ces
catégories restait quasiment nulle à chaque itération : temps de congestion moyen non-nul de 0,06s
pour `living_street`, 0,0002s pour `secondary_link`, 0,0000s pour `tertiary_link`, contre au moins
0,4s pour les 10 autres catégories. La demande simulée n'approche jamais la capacité de ces routes
secondaires dans la plage testée, donc leur capacité ne crée jamais de congestion mesurable. La
régression essayait alors d'expliquer un résidu TomTom à peu près constant avec un `x` toujours
proche de zéro, ce qui pousse le *delta* estimé vers des valeurs extrêmes à chaque itération.

Solution : le garde-fou `--min-signal` (seuil 0,2s), qui gèle ces catégories plutôt que de laisser
la régression extrapoler sur un signal plat. Après remise à zéro des capacités à leur valeur de
production et relance d'un run de 15 itérations, ce garde-fou fonctionne comme prévu :
`living_street`, `residential`, `unclassified` et `tertiary_link` restent gelées sur toutes les
itérations observées jusqu'ici.

# 4. Problèmes actuels (run en cours, 13 itérations sur 15 terminées)

## a) Le critère de convergence ne progresse pas clairement

*max|delta-1|* (la métrique brute utilisée pour l'arrêt) oscille sans tendance nette au fil des
itérations :

```
27,8 / 4,2 / 6,5 / 63,8 / 13,3 / 7,2 / 5,3 / 7,6 / 7,9 / 22,4 / 6,3 / 2,4 / 2,3
```

Les deux dernières valeurs sont les plus basses observées, mais restent très loin du seuil d'arrêt
(0,05). Sauf amélioration nette sur les 2 dernières itérations, le run va s'arrêter par épuisement
du nombre maximal d'itérations, pas par convergence réelle.

## b) `trunk` diverge de façon continue

Le *delta* appliqué à `trunk` reste systématiquement inférieur à 1 depuis la deuxième itération (0,99 /
0,84 / 0,79 / 0,70 / 0,64 / 0,60 / 0,57 / 0,55 / 0,53 / 0,52 / 0,52), ce qui fait grimper sa capacité
en continu : 2 000 → 127 942 en 13 itérations, et 247 648 après la dernière mise à jour. C'est
environ 124 fois la capacité de base, sans signe de stabilisation.

## c) Cause identifiée : colinéarité structurelle entre catégories

En creusant l'hypothèse d'un manque de données, il s'avère que le problème n'est pas un manque
d'observations : chaque catégorie compte entre 119 et 1 546 observations, largement au-dessus du
seuil de 20. Le vrai problème est que les trajets TomTom traversent presque toujours plusieurs
grandes catégories en même temps :

- `motorway` et `motorway_link` apparaissent ensemble sur 91 % et 90 % des trajets respectivement,
  avec une corrélation de co-occurrence de 0,96.
- `trunk` et `trunk_link` : 83 % et 69 % des trajets, corrélation 0,67.

Autrement dit, la régression n'a presque aucune variation indépendante pour distinguer si c'est la
capacité de `trunk` qui explique le résidu observé ou celle de `trunk_link` : ces deux variables
bougent quasiment toujours ensemble dans les données. Ridge (`alpha=100`) atténue cette instabilité
mais ne l'élimine pas complètement, d'où les compensations d'une itération à l'autre qu'on observe
sur `trunk`/`trunk_link` et sur `primary`/`secondary`.

# 5. État du run et pistes pour la suite

Le run tourne depuis le 2 septembre 2026, environ 13 itérations en 2h55 chacune en moyenne, fin
attendue dans les prochaines heures (2 itérations restantes). Il va très probablement s'arrêter sans
converger au sens strict.

Pistes non encore mises en œuvre pour la suite :

1. Augmenter `--ridge-alpha` spécifiquement pour amortir davantage les paires corrélées.
2. Fusionner les paires très corrélées (`motorway` + `motorway_link`, `trunk` + `trunk_link`) en un
   seul paramètre chacune, ce qui supprime directement la colinéarité au lieu de la subir avec de la
   régularisation.
3. Élargir la collecte TomTom pour obtenir davantage de trajets courts qui empruntent une seule
   catégorie de route (plutôt que des trajets longs qui les traversent toutes), ce qui donnerait à
   la régression de la variation réellement indépendante à exploiter.
