# pymetropolis — Ajouter un Step "matrices OD" (Partie C, D + indices de codage)

> Extrait de `pymetropolis_step_matrices_od.md`, complété par des indices pratiques pour coder,
> basés sur les patterns déjà vérifiés en Partie A (checkout `v0.11.0-9-gb4bba97`, LUTIStras).

---

## Partie C — Plan d'insertion du nouveau Step

### C1. Zones en entrée
Rien à coder : configurer `[zones] custom_zones = "chemin/vers/le/geojson"` dans le TOML de run
(le geojson des 985 communes du Thème 5 convient). `CustomZonesStep` produit `ZonesFile`.

### C2. Nouveau Step "zone → nœud routier"
Nouveau fichier, ex. `metro_demand/routing/od_zones.py` (à côté de `od_pairs.py`, même famille) :

- Nouveau `MetroFile` (ex. `ZonesRoadNodeFile`, `zone_id` + `road_node`), à ajouter dans
  `metro_demand/routing/files.py`.
- Nouveau `Step` (ex. `ZonesRoadNodesStep`, sous-classe `GeoStep` comme dans `od_pairs.py`) qui lit
  `ZonesFile`, calcule un point représentatif par zone (`geometry.representative_point()` plutôt
  que `centroid` — le centroïde peut tomber hors polygone pour une commune concave), puis appelle
  `identify_nodes()` (déjà importée depuis `od_pairs.py`) pour obtenir le nœud routier le plus
  proche.
- Différence assumée avec le médoïde du script original : approximation géométrique (rapide,
  cohérente avec le reste du pipeline) plutôt que médoïde réseau (plus exact mais coûteux en
  `O(n²)` par zone) — à documenter comme choix, pas comme oubli.

### C3. Variante free-flow — deux options, à trancher selon la volumétrie
Avec 985 zones, la matrice complète fait ~970 000 paires (985²), sans compter les zones qui ne se
routent pas vers elles-mêmes.

- **Option A (recommandée pour démarrer, zéro nouveau code de routing)** : construire les paires
  zone × zone comme des "trips" virtuels (`trip_id` = paire, `origin_node`/`destination_node` =
  nœuds de C2), puis réutiliser `trip_routing()` de `routing_cli.py` **sans modification**. C'est
  déjà éprouvé sur des centaines de milliers de vrais trajets dans le pipeline existant.
- **Option B (plus rapide si Option A est trop lente)** : adapter `AllRoadDistancesStep` (A8) —
  `compute_all_pairs_dijkstra` avec un poids `free_flow_travel_time`, en restreignant les sources à
  la liste des nœuds de zones plutôt que tous les nœuds du réseau (`nx.multi_source_dijkstra` par
  nœud source, pas vraiment all-pairs). Réutilise `metro_common/routing.py` mais nécessite une
  petite variante de `compute_all_pairs_dijkstra`.

Commencer par l'option A, mesurer, ne passer à B que si nécessaire.

### C4. Variante congestionnée — code réellement nouveau
Aucun gabarit direct (cf. Partie B). À écrire dans le même fichier que le futur Step, en
s'inspirant de `prepare_routing()`/`run_routing()` existants :

1. Lire `MetroNextExpectedTravelTimeFunctionsFile` (A9), filtrer sur le `vehicle_id` voiture,
   écrire un `edge_ttfs.parquet` dans le répertoire temporaire (comme le faisait
   `prepare_routing()` du script original).
2. `parameters.json` : `algorithm = "Intersect"`, pas de `departure_time` fixe par requête,
   `input_files` incluant `edge_ttfs`.
3. Lire `profile_results.parquet` en sortie (pas `ea_results.parquet`) — **vérifier le schéma exact
   de ce fichier en lançant une fois le binaire `routing_cli` en mode `"Intersect"` sur un petit
   cas de test avant d'écrire le code d'agrégation** ; le script original suggère plusieurs lignes
   par `query_id` (des breakpoints temporels), à confirmer empiriquement plutôt qu'assumé.
4. Agrégation en polars, group_by `query_id` (= paire de zones) :
   - **médiane** : `pl.col("travel_time").median()`.
   - **logsum** : pas de définition existante dans pymetropolis à reprendre (aucune occurrence de
     "logsum" dans le code source) — formule standard de choix discret à documenter soi-même dans
     le code, ex. `-1/mu * ln( mean_t(exp(-mu * travel_time_t)) )` avec `mu` un nouveau
     `FloatParameter` ; cohérent avec le concept de `surplus`/"expected utility" déjà utilisé dans
     `MetroIterationResultsFile` (Thème 3) — à choisir en accord avec la convention de signe déjà
     en place dans le reste du projet.

### C5. Nouveaux paramètres
Dans le nouveau module, en classe :
```python
aggregation = EnumParameter(
    "od_matrix_travel_times.aggregation",
    values=["median", "logsum"],
    default="median",
    description="Méthode d'agrégation des temps de trajet congestionnés par paire OD.",
)
```
(+ un `FloatParameter` pour `mu` si l'option logsum est retenue).

### C6. Nouveaux fichiers de sortie
Deux `MetroFile` (ex. `ZoneODFreeFlowTravelTimesFile`, `ZoneODCongestedTravelTimesFile`), schéma
`(origin_zone_id, destination_zone_id, travel_time, [aggregation_method])`, sur le modèle de
`RoadODMatrixFile` (`metro_demand/od_matrix/file.py`) — attention, **ce module `od_matrix/` existant
n'est pas le bon endroit** : il sert à générer des trajets *depuis* une matrice OD (sens inverse,
`generate_trips_from_od_matrix`), pas à calculer des temps de trajet.

### C7. Enregistrement
Deux options :
- Ajouter les nouvelles classes dans `metro_demand/routing/files.py`/`routing_cli.py` (ou
  `od_zones.py`) et les lister dans `ROUTING_FILES`/`ROUTING_STEPS`
  (`metro_demand/routing/__init__.py`) — le plus simple, cohérent avec A4/A5.
- Ou créer un sous-package dédié `metro_demand/od_travel_times/` (suivant exactement le pattern de
  `metro_demand/od_matrix/`) puis l'importer dans `metro_demand/__init__.py`. Préférable si le
  périmètre grossit (plusieurs Steps, fichiers, paramètres) — sinon, la première option suffit.

Dans les deux cas : **pas besoin de toucher `schema.py`, `cli.py`, `pipeline.py`** (A4).

---

## Partie D — Ordre de travail conseillé

1. Lire Partie A dans l'ordre (A1 → A9) directement dans le code sur LUTIStras, pas seulement ce
   résumé — chaque section pointe un fichier précis à ouvrir. **Fait.**
2. Configurer `zones.custom_zones` sur un TOML de test, lancer `CustomZonesStep` seul, vérifier
   `ZonesFile` en sortie (985 zones attendues sur le geojson du bassin). **Fait (A6).**
3. Écrire et tester isolément le Step C2 (zone → nœud routier) — petit, facile à vérifier
   visuellement (comparer quelques nœuds obtenus à une carte).
4. Variante free-flow (C3, option A) : construire les paires zone×zone comme "trips" virtuels,
   appeler `trip_routing()` sans modification, mesurer le temps d'exécution sur les 985 zones avant
   de décider si l'option B est nécessaire.
5. Sanity-check du free-flow : comparer quelques valeurs à `route_free_flow_travel_time` déjà connu
   dans `trip_results.parquet` (Thème 3) pour des trajets réels proches des mêmes zones.
6. Variante congestionnée (C4) : d'abord un test manuel du binaire `routing_cli` en `"Intersect"`
   sur un tout petit cas (2-3 zones) pour confirmer le schéma réel de `profile_results.parquet`
   avant d'écrire le code de production.
7. Implémenter l'agrégation médiane puis logsum (C4.4), en documentant la formule choisie dans une
   docstring du Step.
8. Déclarer les nouveaux paramètres (C5), fichiers (C6), et les enregistrer (C7).
9. Lancer le pipeline complet sur le TOML de test, vérifier qu'aucun avertissement de clé de config
   inutilisée n'apparaît (`MetroPipeline.check_unused_keys`, A4) — signe que le paramètre est bien
   branché.

---

## Indices pratiques pour coder (étape 3 — C2, prochaine étape concrète)

Ces indices partent de ce qui a déjà été vérifié dans le vrai code pendant la Partie A — pas de
suppositions.

### Où regarder avant d'écrire une ligne

```bash
ssh lutistras
cd ~/stage/pymetropolis/src/pymetropolis
cat metro_demand/routing/od_pairs.py   # gabarit direct pour C2 : lit un GeoDataFrame, appelle
                                        # identify_nodes(), écrit un MetroFile
```
`od_pairs.py` fait déjà presque exactement ce que C2 demande, mais pour des trips (points issus de
la population) au lieu de zones (polygones). Le travail de C2 = adapter ce même pattern, avec une
étape en plus au début (polygone → point représentatif) avant d'appeler `identify_nodes()`.

### Squelette à suivre (mêmes conventions que A1/A2/A4)

1. **`MetroFile`** (dans `metro_demand/routing/files.py`, à côté de `TripsRoadNodesFile`) :
   ```python
   class ZonesRoadNodeFile(MetroDataFrameFile):
       path = "demand/routing/zones_road_node.parquet"
       description = "Road network node representative of each zone."
       schema = [
           Column("zone_id", MetroDataType.ID, unique=True, nullable=False),
           Column("road_node", MetroDataType.ID, nullable=True),
       ]
   ```
   (Reprends le style exact de `TripsRoadNodesFile` pour la description et les colonnes optionnelles
   de distance si tu veux les garder pour du debug — pas obligatoire pour le MVP.)

2. **`Step`** (dans `od_zones.py`, nouveau fichier) :
   ```python
   class ZonesRoadNodesStep(GeoStep):
       input_files = {"zones": ZonesFile}
       output_files = {"zones_road_node": ZonesRoadNodeFile}

       def run(self):
           zones = self.input["zones"].read()
           edges = ...  # RoadEdgesCleanFile, comme dans od_pairs.py
           zones["geometry"] = zones.geometry.representative_point()
           result = identify_nodes(zones, edges, id_col="zone_id")
           self.output["zones_road_node"].write(result)
   ```
   Vérifie dans `od_pairs.py` la signature exacte de `identify_nodes()` (nom des colonnes en entrée
   attendu, nom de l'argument `id_col` ou équivalent) avant de copier-coller — le but n'est pas de
   deviner la signature mais de la lire.

3. **Enregistrement** (rappel A4, chaîne à 4 maillons) :
   - `metro_demand/routing/__init__.py` : ajoute `ZonesRoadNodesStep`/`ZonesRoadNodeFile` aux listes
     `ROUTING_STEPS`/`ROUTING_FILES`.
   - Les 2 maillons suivants (`metro_demand/__init__.py`, `schema.py`) n'ont **rien à changer** —
     ils agrègent déjà tout `ROUTING_STEPS`/`ROUTING_FILES` automatiquement (c'est tout l'intérêt de
     la chaîne déclarative vue en A4).

4. **Test isolé** (avant d'aller plus loin) :
   ```bash
   uv run --project pymetropolis pymetropolis --step ZonesRoadNodesStep config-test.toml
   uv run --project pymetropolis python3 -c "
   import polars as pl
   df = pl.read_parquet('bassin/output_de/demand/routing/zones_road_node.parquet')
   print(df.shape, df.null_count())
   print(df.head(10))
   "
   ```
   Vérifie en particulier : combien de `road_node` sont `null` (zones trop loin de tout nœud
   routier ?), et que le nombre de lignes = 985 (une par zone).

### Pièges à anticiper (déduits de ce qu'on a déjà vu en Partie A)

- **`centroid` vs `representative_point()`** : ne pas se tromper, c'est explicitement documenté en
  C2 — une commune en forme de croissant (concave) peut avoir un centroïde géométrique hors de son
  propre polygone. `representative_point()` garantit un point à l'intérieur.
- **`zone_id` doit être présent** : rappel du piège A6 — si jamais tu régénères le geojson de zones
  autrement, vérifie que la colonne s'appelle bien `zone_id` avant de lancer quoi que ce soit,
  sinon `MetropyError: GeoDataFrame is not valid` comme en A6.
- **CRS** : `identify_nodes()`/`sjoin_nearest` sont sensibles au système de coordonnées — vérifie
  que `zones` et `edges` sont dans le même CRS avant l'appel (comme fait `to_crs()` dans
  `identify_iris`/`identify_insee`, vu dans la discussion sur les zones).
- **`profile_results.parquet` (C4, étape 6)** : ne pas écrire le code d'agrégation avant d'avoir
  vraiment vu le fichier une fois — le document le dit explicitement, et c'est cohérent avec toute
  la méthode de la Partie A ("on vérifie par exécution, pas par lecture passive").

### Comment avancer concrètement à partir de maintenant

1. Ouvrir `od_pairs.py` en entier sur LUTIStras et noter la signature exacte de `identify_nodes()`.
2. Écrire `ZonesRoadNodeFile` (5 min, copier le style de `TripsRoadNodesFile`).
3. Écrire `ZonesRoadNodesStep` en copiant la structure de `od_pairs.py`, en ajoutant seulement la
   ligne `representative_point()`.
4. Enregistrer dans `ROUTING_STEPS`/`ROUTING_FILES`.
5. Lancer `--step ZonesRoadNodesStep` sur le TOML de test déjà utilisé en A6, vérifier le parquet.
6. Une fois ça marche : passer à C3 (option A, réutiliser `trip_routing()` sans y toucher).
