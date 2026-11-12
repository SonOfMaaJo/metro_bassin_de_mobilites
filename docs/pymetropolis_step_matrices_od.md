# Ajouter un Step "matrices OD" à pymetropolis (v0.11.0)

But : calculer, pour chaque paire de zones (communes du bassin), un temps de trajet en voiture en
deux variantes — **free-flow** et **congestionné** (agrégé par médiane ou par logsum). Ce document
scanne le code source réel de `~/stage/pymetropolis` sur LUTIStras (tag `v0.11.0-9-gb4bba97`, install
du 2026-08-11) pour (A) donner un ordre de lecture qui fait comprendre l'architecture avant de coder,
puis (B) une correspondance à jour avec `compute_travel_times.py`, puis (C) un plan d'insertion concret.

> Une analyse similaire avait été faite plus tôt dans le projet contre une version antérieure de
> pymetropolis (avant la réinstallation en v0.11.0) — plusieurs choses ont changé depuis (plus de
> `road_network/penalties.py` séparé, module `zones/` désormais présent) : ce document remplace
> cette ancienne analyse, ne pas la réutiliser telle quelle.

---

## 0. Rappel du script `compute_travel_times.py`

Script autonome (`scripts/compute_travel_times.py` en local, copie envoyée à l'équipe) qui, pour
un jeu de zones (`communes.parquet`) :

1. `read_trips()` — produit cartésien de toutes les paires zone × zone.
2. `read_edges()` — lit les arêtes du réseau routier, calcule `travel_time = length / (speed/3.6)`
   plus pénalités additive/multiplicative.
3. `find_origin_destination_node()` — pour chaque zone, trouve le nœud **médoïde** du réseau
   routier (nœud qui minimise la somme des distances à tous les autres nœuds de la même zone), via
   `scipy.spatial.distance_matrix`.
4. `add_od_to_trips()` — joint les paires zone×zone aux nœuds médoïdes, déduplique, retire les
   boucles.
5. `prepare_routing()` / `run_routing()` — écrit `queries.parquet` + `edges.parquet` (+
   `edge_ttfs.parquet` si `EDGE_TTFS` est défini) + `parameters.json`, puis appelle le binaire
   `routing_cli`. Deux modes : `departure_time` fixe → algorithme `"Best"`/`"TCH"` (statique) ;
   `departure_time=None` → algorithme `"Intersect"` (profil temporel, congestionné).
6. `load_results()` / `merge()` — lit `ea_results.parquet` (mode statique) ou
   `profile_results.parquet` (mode profil) et reconstitue la matrice.

C'est le plan de référence ; la question de fond est : qu'est-ce que pymetropolis fait déjà de
tout ça, et qu'est-ce qu'il reste à écrire.

---

## Partie A — Comprendre l'architecture pymetropolis (à faire dans cet ordre)

### A1. Le concept de `Step`
Fichier : `src/pymetropolis/metro_pipeline/steps.py`

- Une `Step` déclare `input_files: dict[str, MetroFile]`, `output_files: dict[str, MetroFile]`,
  `priority: int`, et une méthode `run()`.
- Les paramètres de config sont des attributs de classe (`BoolParameter`, `EnumParameter`, etc.,
  voir A3) — au `__init__`, chaque paramètre est résolu depuis le `Config` et posé comme attribut
  d'instance (`self.mon_param`).
- `run()` lit via `self.input["clef"].read()` et écrit via `self.output["clef"].write(df)`.
- `priority == 0` = Step "non primaire", exécuté seulement si un autre Step primaire a besoin de
  sa sortie (cf. `AllRoadDistancesStep`, `RoadODMatrixStep`, tous deux à `priority = 0` — bon
  précédent pour un Step de matrice OD, qui n'est utile qu'à la demande).

### A2. Le concept de `MetroFile`
Fichier : `src/pymetropolis/metro_pipeline/file.py`

- `MetroDataFrameFile` (parquet polars) et `MetroGeoDataFrameFile` (geoparquet) déclarent un
  `path` relatif à `main_directory` et un `schema: list[Column]` (typé via `MetroDataType`,
  avec `nullable`/`optional`/`unique`). Le schéma sert à la fois de documentation générée et de
  validation à l'écriture.

### A3. Les `Parameter` et la config TOML
Fichiers : `metro_pipeline/parameters.py`, `metro_pipeline/config.py`

- Classes dispo : `BoolParameter`, `IntParameter`, `FloatParameter`, `EnumParameter`,
  `PathParameter`, `ExecPathParameter`, `ListParameter`, `DurationParameter`, etc.
- Une clé du type `"od_matrix_travel_times.aggregation"` correspond à
  `config["od_matrix_travel_times"]["aggregation"]` dans le TOML.
- `EnumParameter(values=[...], default=...)` est exactement ce qu'il faut pour le choix
  médiane/logsum (cf. Partie C).

### A4. L'enregistrement des Steps — entièrement déclaratif, à connaître avant de coder
Chaîne d'agrégation (vérifiée) :

```
metro_demand/routing/__init__.py       -> ROUTING_FILES, ROUTING_STEPS
metro_demand/__init__.py               -> FILES/STEPS = ZONES_* + OD_MATRIX_* + ... + ROUTING_*
schema.py (racine)                     -> STEPS = METRO_SPATIAL_STEPS + METRO_NETWORK_STEPS
                                                  + METRO_DEMAND_STEPS + ...
cli.py                                 -> from .schema import STEPS ; MetroPipeline(config, STEPS, ...)
```

**Point important** (vérifié dans `metro_pipeline/pipeline.py`, `MetroPipeline.__init__`) : l'ordre
d'exécution n'est **pas** déclaré manuellement. `MetroPipeline` construit un graphe de dépendances
en croisant les `input_files`/`output_files` de chaque Step avec les classes `MetroFile` produites
par les autres — ajouter un Step revient donc juste à : écrire la classe, l'ajouter à la liste
`_STEPS` du sous-module concerné, et référencer les bonnes classes `MetroFile` en entrée/sortie. Pas
besoin de toucher `schema.py`, `cli.py` ni `pipeline.py`.

### A5. Le pattern de routing existant
Fichier : `metro_demand/routing/routing_cli.py` (229 lignes) — lire en entier, c'est le cœur.

- `RoutingCLIStep(Step)` : classe abstraite, un seul paramètre (`metropolis_core.routing_exec_path`).
- `trip_routing(trips, edges, routing_exec, with_routes)` → `prepare_routing()` (écrit
  `queries.parquet`/`edges.parquet`/`parameters.json` dans un `tempfile.TemporaryDirectory()`) →
  `run_routing()` (`subprocess.run([routing_exec, parameters_filename])`) → relit
  `ea_results.parquet`. **Correspond exactement** à `prepare_routing`/`run_routing`/`load_results`
  du script, en plus concis.
- `TripsCarFreeFlowTravelTimesStep` (le meilleur gabarit) : lit `RoadEdgesCleanFile` +
  `RoadEdgesFreeFlowTravelTimeFile`, construit les poids d'arêtes, appelle `trip_routing()`, écrit
  `TripsCarFreeFlowTravelTimesFile`.
- **Ce que ce fichier ne fait pas** : `prepare_routing()` n'écrit jamais de `edge_ttfs.parquet` et
  n'utilise jamais l'algorithme `"Intersect"` — le mode congestionné/profil temporel du script
  original n'a **aucun équivalent actuel**.

### A6. Le concept de zones — existe déjà, contrairement à l'ancienne analyse
Fichiers : `metro_demand/zones/file.py`, `metro_demand/zones/custom.py`

- `ZonesFile` (`zone_id`, `name` optionnel, `geometry`) est un `MetroGeoDataFrameFile` déjà défini.
- `CustomZonesStep` le remplit directement depuis un fichier géospatial fourni par
  l'utilisateur (`zones.custom_zones` dans le TOML, ex. le même geojson des 985 communes déjà
  utilisé au Thème 5 : `bassin_mobilite_ge_transfrontalier_simulation_area.geojson`).
- **Conséquence** : `read_trips()`/la lecture de `communes.parquet` du script original n'a plus
  besoin d'être réécrite — il suffit de pointer `zones.custom_zones` vers le bon geojson, et
  `ZonesFile` est prêt à l'emploi.

### A7. Comment une paire de coordonnées devient un nœud du réseau routier
Fichier : `metro_demand/routing/od_pairs.py`

- `identify_nodes(edges, nodes_gdf)` : jointure spatiale `sjoin_nearest` vers l'arête la plus
  proche, puis choix du nœud source/target le plus proche (pas un médoïde réseau — une approximation
  géométrique locale, plus rapide).
- `RoadODNodesFromCoordinatesStep` applique ça aux `TripsOriginsFile`/`TripsDestinationsFile`
  (coordonnées ponctuelles de vrais trajets) → écrit `TripsRoadNodesFile`.
- Il n'existe **aucun Step qui fait ça à partir d'un centroïde de zone** — c'est la seule vraie
  brique manquante côté "zone → nœud réseau", mais elle est beaucoup plus simple à écrire que le
  médoïde du script original, en réutilisant `identify_nodes()` tel quel.

### A8. Le calcul all-pairs déjà existant — bon gabarit pour la variante free-flow
Fichiers : `metro_common/routing.py`, `metro_network/road_network/routing.py`

- `compute_all_pairs_dijkstra(edges)` (networkx, `nx.all_pairs_dijkstra_path_length`) calcule en
  une seule passe la distance de plus court chemin entre **tous** les nœuds du réseau.
- `AllRoadDistancesStep` l'utilise avec `weight = length`. **Il suffit de faire le même Step avec
  `weight = free_flow_travel_time`** pour obtenir une matrice de temps de trajet libre entre tous
  les nœuds — mais calculer *tous* les nœuds×nœuds est inutilement gros ; on veut seulement les
  nœuds correspondant aux ~985 zones (cf. Partie C).

### A9. Les temps de trajet congestionnés existent déjà en sortie de simulation
Fichier : `metro_simulation/run/files.py`

- `MetroNextExpectedTravelTimeFunctionsFile` → `run/output/net_cond_next_exp_edge_ttfs.parquet`,
  schéma `(vehicle_id, edge_id, departure_time, travel_time)` — **exactement** le format que le
  script original lisait sous `EDGE_TTFS`. Rien à écrire pour produire ce fichier, il sort déjà de
  la simulation Metropolis-Core ; le travail restant est de le **consommer** en entrée d'un routing
  en mode profil (cf. A5, aucun Step ne le fait aujourd'hui).

---

## Partie B — Correspondance à jour avec `compute_travel_times.py`

| Fonction du script | Équivalent pymetropolis v0.11.0 | Statut |
|---|---|---|
| `read_trips()` (zones + produit cartésien) | `ZonesFile` / `CustomZonesStep` (A6) pour les zones ; le produit cartésien reste à écrire | Zones : réutilisable telles quelles. Produit cartésien : à écrire (petit) |
| `read_edges()` (fftt + pénalités) | `RoadEdgesCleanFile` + `RoadEdgesFreeFlowTravelTimeFile` (déjà agrégées par `TripsCarFreeFlowTravelTimesStep`, A5) | Réutilisable tel quel |
| `find_origin_destination_node()` (médoïde) | rien d'équivalent ; `identify_nodes()` (A7) fait une approximation géométrique plus simple (nœud le plus proche du centroïde) | À écrire, mais court (réutilise `identify_nodes`) |
| `prepare_routing()`/`run_routing()` mode statique | `trip_routing()`/`prepare_routing()`/`run_routing()` dans `routing_cli.py` (A5) | Réutilisable tel quel pour le free-flow |
| `prepare_routing()` mode profil (`edge_ttfs`, `"Intersect"`) | **aucun équivalent** (A5, A9) | À écrire entièrement |
| `load_results()` mode profil (`profile_results.parquet`) | **aucun équivalent** | À écrire entièrement |
| Agrégation médiane/logsum | **aucun équivalent** (`grep -i logsum` : zéro résultat dans tout le code source) | Concept entièrement nouveau à définir |

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
   résumé — chaque section pointe un fichier précis à ouvrir.
2. Configurer `zones.custom_zones` sur un TOML de test, lancer `CustomZonesStep` seul, vérifier
   `ZonesFile` en sortie (985 zones attendues sur le geojson du bassin).
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
   docstring du Step (`_md_doc()` en généralisera la doc automatiquement, cf. A1/A2).
8. Déclarer les nouveaux paramètres (C5), fichiers (C6), et les enregistrer (C7).
9. Lancer le pipeline complet sur le TOML de test, vérifier qu'aucun avertissement de clé de config
   inutilisée n'apparaît (`MetroPipeline.check_unused_keys`, A4) — signe que le paramètre est bien
   branché.
