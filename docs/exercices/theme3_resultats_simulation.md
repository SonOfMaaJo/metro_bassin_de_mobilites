# Thème 3 — Résultats de simulation pymetropolis

> Voir [README](README.md) pour l'environnement de travail.

> **Attention, piège d'échelle inverse de celui du Thème 2.** Les fichiers de ce thème
> (`bassin/output_de/results/`, `bassin/output_de/run/output/`) sont des sorties **pymetropolis**,
> pas eqasim-france. Ici `simulation_ratio = 0.2` s'applique réellement (`config/config-bassin-de.toml`,
> ligne 13) : la population simulée dans le simulateur de trafic (agents, trajets routés) est un
> échantillon à 20 % de la population synthétique complète du Thème 2. Si tu compares un total de
> ce thème à un total du Thème 2, il faut diviser (ou multiplier) par `0.2` quelque part — sinon tu
> compares deux échelles différentes sans t'en rendre compte. Vérifie toujours dans quel dossier tu
> es avant de lancer un calcul : `output_de/` (résultats agrégés, légers) vs `run/output/` (sorties
> brutes du moteur de simulation, beaucoup plus volumineuses — jusqu'à 650 Mo pour un seul fichier).

## Ex00 — Répartition modale (`trip_results.parquet`)

**Objectif** : recalculer en Python une statistique déjà publiée sous forme de graphique par
pymetropolis, pour vérifier qu'on sait retrouver un chiffre de rapport à partir du fichier source.

**Contraintes** :
- Fichier : `bassin/output_de/results/trip_results.parquet` (~41 Mo, `pl.read_parquet` direct OK).
- Le graphique déjà produit est `bassin/output_de/results/graphs/trip_mode_shares.png` — ne le
  regarde qu'*après* avoir fait ton propre calcul, pour comparer, pas pour copier les chiffres dedans.
- Piège : la colonne s'appelle `mode`, pas `transport_mode` ni `mode_id` — commence par
  `.collect_schema()` avant de deviner un nom de colonne.
- Le pourcentage doit être calculé sur le nombre de **trajets** (lignes), pas sur une somme d'une
  autre colonne.

**Recherche imposée sourcée** : le fichier `bassin/output_de/results/aggregate_results.json`
contient déjà une clé `mode_shares.trip_count` — pas pour copier la réponse, mais pour vérifier
après coup que ton calcul manuel tombe sur les mêmes valeurs à l'arrondi près (c'est le principe
même de l'exercice : est-ce que tu sais retrouver, depuis les données brutes, un chiffre qu'un
rapport annonce sans détailler le calcul ?).

**Exemple de sortie attendue** (calculée sur `trip_results.parquet`, 878 366 lignes) :
```
mode             n        pct
car_driver       574312   65.38
walking          195720   22.28
public_transit   57970     6.60
car_passenger    31463     3.58
bicycle          18901     2.15
```

**Rendu** : `exercices/theme3/ex00_mode_share.py` + les 5 pourcentages en commentaire de fin de script.

---

## Ex01 — Indicateurs macro (`aggregate_results.json`)

**Objectif** : lire un JSON simple et identifier les indicateurs qu'il contient au-delà de la
répartition modale — en particulier une notion qu'on n'a pas encore rencontrée dans les thèmes
précédents : le **PCE** (Passenger Car Equivalent).

**Contraintes** :
- `json.load` standard, pas de parsing manuel.
- Le fichier contient deux blocs : `mode_shares` (avec deux sous-clés, `trip_count` et
  `trip_euclidean_distance` — remarque qu'elles ne donnent *pas* les mêmes pourcentages pour un
  même mode : pourquoi ?) et `vehicle_kilometers` (avec `total`, `total_weighted_by_pce`, et
  `by_mode`).
- Piège : `vehicle_kilometers.by_mode` ne contient que 2 clés (`car_driver`, `car_passenger`), pas
  les 5 modes de l'Ex00 — pourquoi la marche et les transports en commun n'y figurent-ils pas ?

**Recherche imposée sourcée** : cherche la définition du *Passenger Car Equivalent* (PCE) utilisé
en modélisation de trafic routier (par ex. dans la documentation d'un logiciel de simulation de
trafic ou un cours de génie des transports) — quel est le PCE typiquement utilisé pour une voiture
seule vs un poids lourd, et pourquoi ce facteur sert-il à pondérer les kilomètres parcourus plutôt
que de les compter tels quels ?

**Exemple de sortie attendue** (valeurs réelles du fichier) :
```json
{
  "mode_shares": {
    "trip_count": {"car_driver": 0.6538, "walking": 0.2228, "public_transit": 0.0660,
                    "car_passenger": 0.0358, "bicycle": 0.0215},
    "trip_euclidean_distance": {"car_driver": 0.6933, "car_passenger": 0.2077,
                                 "public_transit": 0.0775, "walking": 0.0146, "bicycle": 0.0069}
  },
  "vehicle_kilometers": {
    "by_mode": {"car_driver": 21892388.8, "car_passenger": 6553863.1},
    "total": 28446251.9,
    "total_weighted_by_pce": 21892388.8
  }
}
```
Remarque que `total_weighted_by_pce` est ici strictement égal à `by_mode.car_driver` — à toi de
trouver pourquoi (indice : combien de véhicules-km génère un `car_passenger`, qui ne conduit pas ?).

**Rendu** : `exercices/theme3/ex01_indicateurs_macro.py` + réponse écrite (2-3 phrases) sur le PCE
et sur l'écart entre `trip_count` et `trip_euclidean_distance` comme pondération.

---

## Ex02 — Reconstituer un itinéraire (`route_results.parquet`)

**Objectif** : manipuler un gros fichier (420 Mo, 37,4 millions de lignes) sans le charger
entièrement en mémoire, et reconstituer la séquence d'arêtes empruntées par un trajet donné.

**Contraintes bloquantes** :
- **Interdiction d'utiliser `pl.read_parquet` directement sur ce fichier** — utilise
  `pl.scan_parquet(...)` et un `.filter()` sur `trip_id` *avant* `.collect()`. Charger le fichier
  entier en mémoire sur une machine standard peut échouer ou ralentir fortement toutes les autres
  commandes sur la machine partagée.
- Le fichier est au grain **arête** (une ligne par tronçon `edge_id` traversé), pas au grain trajet
  — un même `trip_id` apparaît sur plusieurs dizaines de lignes consécutives.
- Piège : les lignes ne sont pas forcément déjà triées par `entry_time` dans le fichier — trie
  explicitement avant d'afficher l'itinéraire, sinon l'ordre des arêtes est incorrect.

**Recherche imposée sourcée** : dans la documentation de pymetropolis (ou son README /
docs interne, à chercher dans le dépôt cloné `pymetropolis/`), retrouve ce que représente une
colonne `edge_id` par rapport au réseau OSM importé — à quelle étape du pipeline (quel `Step`) ce
réseau d'arêtes est-il construit à partir du `.osm.pbf` ?

**Exemple de sortie attendue** (trajet réel `trip_id = "1003-2"`, 91 arêtes) :
```
schema: {trip_id: str, edge_id: str, entry_time: duration[us], exit_time: duration[us], travel_time: duration[us]}

premières arêtes de l'itinéraire (triées par entry_time) :
edge_id=476827  entry=16h26m46s  exit=16h27m04s  travel_time=17.83s
edge_id=311147  entry=16h27m04s  exit=16h27m27s  travel_time=23.37s
edge_id=311150  entry=16h27m27s  exit=16h27m30s  travel_time=2.77s
...
dernière arête :
edge_id=353408  entry=16h51m33s  exit=16h52m12s  travel_time=38.65s

nb total d'arêtes du trajet : 91
durée totale du trajet (dernier exit - premier entry) : ~25 min 26s
```

**Rendu** : `exercices/theme3/ex02_route_reconstruction.py`, paramétrable par `trip_id` (le
`trip_id` de l'exemple ne doit pas être en dur dans le script — passe-le en argument ou tire-en un
au hasard avec `.sample()`).

---

## Ex03 — Convergence de la simulation

**Objectif** : vérifier que la simulation a effectivement convergé (les temps de trajet se
stabilisent au fil des itérations) plutôt que de faire confiance aveuglément aux PNG déjà produits.

**Contraintes** :
- Deux fichiers `iteration_results.parquet` existent, avec des schémas **différents** malgré le
  même nom — ce n'est pas un doublon :
  - `bassin/output_de/results/iteration_results.parquet` (32 colonnes, une ligne par itération,
    déjà agrégé au niveau du run) ;
  - `bassin/output_de/run/output/iteration_results.parquet` (une ligne par itération aussi, mais
    ~140 colonnes détaillées, sortie brute du moteur).
  Précise dans ton script lequel des deux tu utilises et pourquoi.
- 100 itérations au total dans les deux fichiers.
- Piège : certaines colonnes utiles pour la convergence sont de type `Duration`, pas `Float64` —
  `matplotlib` ne sait pas tracer un `Duration` polars directement, il faut le convertir
  explicitement (par ex. `.dt.total_seconds()`).
- Compare ta courbe à `bassin/output_de/results/graphs/convergence_simulated_road_travel_times.png`
  et `convergence_mean_surplus.png` — mêmes tendances attendues, pas nécessairement les mêmes
  unités d'axe.

**Recherche imposée sourcée** : cherche ce qu'est le concept d'*expected utility* / *surplus*
(`mean_surplus` dans le fichier) dans le contexte d'un modèle de choix discret à la Logit utilisé
en simulation de mobilité (par ex. simulateurs MATSim/pymetropolis ou un cours de modélisation du
choix) — pourquoi une valeur de surplus qui se stabilise (plutôt que d'augmenter ou de diverger)
est-elle le signe recherché de convergence ?

**Exemple de sortie attendue** (valeurs réelles de `results/iteration_results.parquet`) :
```
itération 1 :   mean_surplus = -4.9926   std_surplus = 15.0035
itération 5 :   mean_surplus = -5.4691   std_surplus = 15.5396
itération 96 :  mean_surplus = -5.1778   std_surplus = 15.1888
itération 100 : mean_surplus = -5.1740   std_surplus = 15.1846

variation absolue mean_surplus entre itération 96 et 100 : 0.0038 (converge, quasi plat)
variation entre itération 1 et 5 (phase de rodage) : 0.4765 (bien plus grande)
```
La courbe doit visuellement se stabiliser (aplatissement) après les toutes premières itérations.

**Rendu** : `exercices/theme3/ex03_convergence.py`, produisant un PNG
`exercices/theme3/convergence_mean_surplus.png` (courbe itération en abscisse, `mean_surplus` en
ordonnée), à comparer manuellement (pas dans le script) au PNG déjà fourni par pymetropolis.

---

## Ex04 — Congestion horaire d'une arête (`net_cond_next_exp_edge_ttfs.parquet`)

**Objectif** : montrer que le temps de parcours d'une même arête du réseau varie selon l'heure de
départ (congestion), en repérant une arête réellement congestionnée plutôt qu'une arête libre en
permanence.

**Contraintes bloquantes** :
- Fichier : `bassin/output_de/run/output/net_cond_next_exp_edge_ttfs.parquet` (~44 Mo, 45,5 millions
  de lignes, colonnes `vehicle_id, edge_id, departure_time, travel_time`). `departure_time` est en
  **secondes depuis minuit** (float), pas un type `Duration` ni une heure — à convertir toi-même
  (`h = s // 3600`).
- **Piège volontaire** : si tu choisis une arête au hasard (ou juste la première du fichier), il y
  a de bonnes chances qu'elle ne soit jamais congestionnée (`travel_time` quasi constant toute la
  journée, écart de quelques centièmes de seconde — c'est le cas de la majorité des arêtes du
  réseau, en particulier hors zone urbaine dense). Il faut *chercher* une arête dont le
  `travel_time` varie fortement selon l'heure (par ex. en calculant `max - min` par `edge_id` et en
  triant), sinon ta courbe/conclusion est plate et sans intérêt.
- `departure_time` va jusqu'à 97200 (= 27h) : pymetropolis modélise une journée en heures étendues
  au-delà de minuit pour les trajets tardifs qui débordent sur le petit matin — n'essaie pas de
  "corriger" ces valeurs, c'est voulu.

**Recherche imposée sourcée** : cherche ce qu'est une fonction de congestion / *volume-delay
function* (VDF) type BPR (*Bureau of Public Roads*) utilisée en affectation de trafic routier —
quelle est la forme générale de la relation entre le ratio flux/capacité d'une arête et son temps
de parcours, et à quoi correspond le plateau à `travel_time` minimal observé en heures creuses ?

**Exemple de sortie attendue** (arête réelle `edge_id = "518887"`, 97 pas de temps distincts) :
```
travel_time min = 3.72s   (heures creuses, ex. 03h00)
travel_time max = 194.33s (pointe du matin, 07h45)
travel_time moyen sur la journée = 16.86s

→ ratio pointe/creux ≈ 52x sur cette arête précise
```

**Rendu** : `exercices/theme3/ex04_congestion_horaire.py`, produisant un PNG (heure en abscisse,
`travel_time` en ordonnée) pour l'arête choisie + une phrase expliquant comment tu as sélectionné
une arête pertinente (pas juste "la première du fichier").

---

## Grille d'auto-correction — Thème 3

- [ ] Ex00 : les 5 pourcentages de mode share retrouvés correspondent (à l'arrondi près) à
      `aggregate_results.json → mode_shares.trip_count`, calculés sans les recopier depuis ce JSON.
- [ ] Ex01 : explication correcte de pourquoi `total_weighted_by_pce == vehicle_kilometers.by_mode.car_driver`
      (un passager ne pilote pas de véhicule supplémentaire) et définition du PCE sourcée.
- [ ] Ex02 : script fonctionne avec `pl.scan_parquet` + `.filter()` avant `.collect()` (pas de
      `pl.read_parquet` brut sur `route_results.parquet`), paramétrable par `trip_id`, arêtes
      correctement triées par `entry_time`.
- [ ] Ex03 : bon fichier `iteration_results.parquet` identifié et justifié (celui de `results/` pour
      une vue synthétique), courbe produite avec conversion explicite `Duration → secondes` si
      nécessaire, conclusion de convergence cohérente avec les chiffres (écart itération 96→100
      très inférieur à l'écart itération 1→5).
- [ ] Ex04 : arête sélectionnée par un critère explicite de variance (pas au hasard/première ligne),
      conversion correcte secondes → heures, pic de congestion identifié à une heure de pointe
      plausible (matin ou soir), lien fait avec la notion de VDF/BPR sourcée.
