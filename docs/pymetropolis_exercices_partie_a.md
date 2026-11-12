# Exercices — comprendre l'architecture pymetropolis (Partie A)

> Complète `pymetropolis_step_matrices_od.md` (Partie A, sections A1 à A9). Même esprit que
> `exercices/` : on vérifie par exécution, pas par lecture passive. Pas de corrigé fourni pour les
> questions d'interprétation — mais chaque "exemple de sortie attendue" ci-dessous a été **exécuté
> réellement sur LUTIStras** (2026-08-11, checkout `pymetropolis` `v0.11.0-9-gb4bba97`), donc ce
> sont de vrais repères, pas des valeurs devinées.

## Environnement

```bash
ssh lutistras
cd ~/stage
uv run --project pymetropolis python3
```
Code source à lire : `~/stage/pymetropolis/src/pymetropolis/`. Un dossier
`~/stage/exercices_pymetropolis/` a déjà été créé pour les fichiers de test (voir A6).

Rendu : un fichier texte par exercice dans ce même dossier (réponses écrites + commandes
utilisées).

---

## A1 — Step

**Objectif** : comprendre `input_files` / `output_files` / `priority`.

**Action** : ouvre `metro_pipeline/steps.py`, puis `metro_demand/routing/routing_cli.py` et
`metro_network/road_network/routing.py`.

**Exemple de sortie attendue (vérifié)** :
```
TripsCarFreeFlowTravelTimesStep (routing_cli.py:135)
  input_files  = {od_pairs: TripsRoadNodesFile, edges: RoadEdgesCleanFile,
                  edges_fftt: RoadEdgesFreeFlowTravelTimeFile}
  output_files = {fftt: TripsCarFreeFlowTravelTimesFile}
  priority     = non déclaré -> valeur par défaut (steps.py:48)

AllRoadDistancesStep (road_network/routing.py:7)
  input_files  = {clean_edges: RoadEdgesCleanFile}
  output_files = {all_distances: AllRoadDistancesFile}
  priority     = 0   (déclaré explicitement)
```

**Question à répondre par écrit** : `steps.py` définit `priority: ClassVar[int] = 1` par défaut,
et une méthode `is_primary()`. Trouve sa docstring exacte (`steps.py`, méthode `is_primary`) et
reformule avec tes mots : que se passe-t-il pour `AllRoadDistancesStep` si tu lances
`pymetropolis config.toml` **sans** `--step` ? Vérifie ta réponse en cherchant comment
`primary_input_files` est utilisé dans `metro_pipeline/pipeline.py`.

---

## A2 — MetroFile

**Objectif** : distinguer `MetroDataFrameFile` de `MetroGeoDataFrameFile`.

**Action** : `grep -n "class.*MetroDataFrameFile\|class.*MetroGeoDataFrameFile"
metro_pipeline/file.py`.

**Exemple de sortie attendue (vérifié)** :
```
TripsCarFreeFlowTravelTimesFile (MetroDataFrameFile) — routing/files.py:350
  colonnes : trip_id (ID, unique), free_flow_travel_time (DURATION, nullable),
             free_flow_route (LIST_OF_IDS, nullable), ...

ZonesFile (MetroGeoDataFrameFile) — zones/file.py:4
  colonnes : zone_id (ID, unique), name (STRING, optional), original_id (ID, optional)
  (+ geometry, implicite au type MetroGeoDataFrameFile, pas listée dans schema)
```

**Question à répondre par écrit** : pourquoi `geometry` n'apparaît-elle pas dans la liste
`schema` de `ZonesFile`, alors qu'elle existe bien dans le parquet produit (vérifiable via
l'Ex. A6) ? Regarde comment `MetroGeoDataFrameFile.validate()` traite la colonne `geometry` par
rapport à `MetroDataFrameFile.validate()`.

---

## A3 — Parameters / TOML

**Objectif** : vérifier la correspondance clé TOML ↔ classe `Parameter`, y compris les cas non
triviaux.

**Exemple de sortie attendue (vérifié, 3 clés réelles)** :
```
"simulation.learning_factor"
  -> FloatParameter, default=0.0 (metro_simulation/parameters/step.py:73)

"mode_choice.model"
  -> EnumParameter(values=["Logit","DrawnLogit","DrawnNestedLogit","Deterministic"],
                    default="Deterministic")  (metro_simulation/demand/agents.py:18)

"road_network.default_speed_limit.rural"
  -> PIÈGE : ce grep exact ne retourne RIEN. La vraie clé déclarée est
     "road_network.default_speed_limit" (CustomParameter, road_network/postprocess.py:81),
     qui capture toute la table TOML [road_network.default_speed_limit] d'un coup (un dict
     Python, avec "urban"/"rural" comme sous-clés à l'intérieur) — pas un Parameter par
     sous-clé.
```

**Question à répondre par écrit** : dans `config-bassin-de.toml`, retrouve la section
`[road_network.default_speed_limit.rural]`. Le fait que `default_speed_limit` soit un
`CustomParameter` unique plutôt que des `FloatParameter` séparés par type de route change quoi
pour la validation (un seul `validator_description` custom vs. la validation typée habituelle) ?
Choisis ensuite 2 clés supplémentaires toi-même (différentes de ces 3) et vérifie-les par `grep`.

---

## A4 — Chaîne d'enregistrement

**Objectif** : sentir que l'enregistrement d'un Step est mécanique, pas magique.

**Exemple de sortie attendue (vérifié, chaîne complète pour `TripsBicycleCostStep`)** :
```
1. metro_demand/routing/routing_cli.py       — définition de la classe
2. metro_demand/routing/__init__.py:20,41    — exportée dans ROUTING_STEPS
3. metro_demand/__init__.py:5,23             — "from .routing import ROUTING_STEPS"
                                                puis "+ ROUTING_STEPS" dans la liste finale
4. schema.py:4,20                            — "from .metro_demand import STEPS as
                                                METRO_DEMAND_STEPS" puis "+ METRO_DEMAND_STEPS"
```

**Question à répondre par écrit** : refais cette même chasse toi-même, à la main (sans copier la
chaîne ci-dessus), pour un Step que tu choisis dans un module que tu n'as pas encore ouvert (par
exemple dans `metro_calibration/` ou `metro_spatial/`). Est-ce que la chaîne a toujours
exactement 4 maillons, ou en as-tu trouvé une avec un niveau d'imbrication différent ?

---

## A5 — routing_cli.py

**Objectif** : comprendre `prepare_routing()`/`run_routing()`.

**Exemple de sortie attendue (vérifié)** :
```
routing_cli.py:170  trip_routing(..., with_routes=True)
routing_cli.py:214  "algorithm": "TCH" if with_routes else "Best"
routing_cli.py:215  "output_route": with_routes
```
Et en bonus (trouvé en creusant `simulation.routing_algorithm` pour A3/A9) :
`metro_simulation/parameters/step.py` déclare un troisième algorithme possible,
`EnumParameter("simulation.routing_algorithm", values=["Best", "Intersect", "TCH"], ...)`
— `"Intersect"` n'apparaît jamais dans `routing_cli.py`, seulement dans les paramètres de
simulation.

**Précision vérifiée côté Rust** (`Metropolis-Core/metropolis-core/src/network/road_network/parameters.rs:85-140`,
enum `AlgorithmType`) : ce ne sont pas 3 algorithmes indépendants au même niveau. `Best` choisit
automatiquement entre les deux autres selon le cas. `Tch` = Time-dependent Contraction
Hierarchies (préprocessing long, requêtes rapides). `Intersect` = **many-to-many TCH**
(préprocessing le plus long, requêtes les plus rapides, optimal quand origines/destinations sont
un petit sous-ensemble de tous les nœuds, interrogé plusieurs fois) — donc `Intersect` est une
variante de TCH spécialisée many-to-many, pas un algorithme d'une autre famille.

**Question à répondre par écrit** :
- pourquoi `"TCH"` seulement quand `with_routes=True` ? (indice : reconstruire un itinéraire
  complet coûte plus cher qu'une simple valeur de temps de trajet — vérifie si TCH est un
  algorithme de préprocessing/index vs. Best un calcul direct, en cherchant "TCH" dans le
  `README` ou la doc de `Metropolis-Core` si besoin).
- où (dans quel module, pas forcément `routing_cli.py`) le mode `"Intersect"` est-il
  probablement utilisé, vu que c'est un paramètre de simulation (`metro_simulation/`) et non de
  routing pré-simulation ? Ça rejoint directement la Partie C4 du document principal (matrice OD
  congestionnée).

---

## A6 — Zones, exécution réelle

**Objectif** : vérifier `ZonesFile`/`CustomZonesStep` en conditions réelles.

**Ce qui s'est réellement passé en testant** (garde cette séquence, elle contient un vrai piège) :

1. Config de test avec `zones.custom_zones =
   "./bassin/data/bassin_mobilite_ge_transfrontalier_simulation_area.geojson"` (985 communes,
   colonnes `insee`/`name`/`geometry` — cf. `exercices/theme5_cartographie.md` Ex00).
2. `pymetropolis --step CustomZonesStep config.toml` → **échoue** :
   ```
   WARNING | Missing required column `zone_id`
   MetropyError: GeoDataFrame is not valid
   ```
   Le geojson a une colonne `insee`, pas `zone_id` — `CustomZonesStep` ne fait aucun mapping
   automatique, il exige le nom exact `zone_id`.
3. Fix réel : renommer la colonne (`gdf.rename(columns={"insee": "zone_id"})`) et réécrire le
   fichier avant de le donner en entrée.
4. Deuxième run → succès :
   ```
   n zones: 985
   colonnes: ['zone_id', 'name', 'geometry']
   ```

**Action** : reproduis cette séquence toi-même (le fichier renommé n'existe plus, il faut le
refaire) :
```bash
uv run --project pymetropolis python3 -c "
import geopandas as gpd
gdf = gpd.read_file('bassin/data/bassin_mobilite_ge_transfrontalier_simulation_area.geojson')
gdf = gdf.rename(columns={'insee': 'zone_id'})
gdf.to_file('exercices_pymetropolis/zones_fixed.geojson', driver='GeoJSON')
"
```
puis un TOML minimal (`main_directory` + `[zones] custom_zones = "..."`) et
`pymetropolis --step CustomZonesStep <ton_toml>`.

**Question à répondre par écrit** : pourquoi `CustomZonesStep.run()` ne tente-t-il pas de
détecter automatiquement une colonne candidate (`insee`, `id`, ...) plutôt que d'exiger
`zone_id` exactement ? Est-ce cohérent avec le principe "explicite plutôt qu'implicite" que tu as
déjà vu ailleurs dans le code (A3) ?

---

## A7 — identify_nodes()

**Objectif** : comprendre la géométrie de l'approximation nœud-le-plus-proche.

**Action** : lis `identify_nodes()` dans `metro_demand/routing/od_pairs.py` (lignes 48-82) en
entier.

**Question à répondre par écrit** :
- pourquoi comparer `source_dist` vs `target_dist` (lignes 62-63, 70-73) plutôt que prendre
  directement le nœud retourné par `sjoin_nearest` ?
- `node_dist_on_edge = sqrt(node_dist**2 - edge_dist**2)` (ligne 76-78) : à partir d'un schéma
  fait main (point hors de l'arête, projeté dessus), identifie quel triangle rectangle justifie
  cette formule, et quels sont ses 3 côtés.
- cette méthode donne-t-elle un vrai médoïde du réseau (le nœud minimisant la distance moyenne à
  tous les autres), ou une approximation géométrique locale ? Justifie à partir du code lu.

---

## A8 — compute_all_pairs_dijkstra

**Objectif** : comprendre le format d'entrée/sortie avant de l'utiliser sur le vrai réseau.

**Exemple de sortie attendue (vérifié, graphe jouet à 5 nœuds)** :
```python
edges = pl.DataFrame({
    "source": [1,2,3,1,4], "target": [2,3,4,4,5], "weight": [1.0,2.0,1.0,10.0,3.0],
})
df = compute_all_pairs_dijkstra(edges)
```
```
shape: (15, 3)
┌───────────┬────────────────┬────────┐
│ origin_id ┆ destination_id ┆ weight │
│ 1         ┆ 1              ┆ 0.0    │
│ 1         ┆ 2              ┆ 1.0    │
│ 1         ┆ 3              ┆ 3.0    │
│ 1         ┆ 4              ┆ 4.0    │   <- via 1->2->3->4 (poids 4), pas 1->4 direct (poids 10)
│ 1         ┆ 5              ┆ 7.0    │
...
```

**Question à répondre par écrit** : sur 5 nœuds, il y a 25 paires (origine, destination)
possibles (en comptant les paires (i, i)), mais le résultat n'a que 15 lignes. Pourquoi ? (indice :
regarde `G.add_weighted_edges_from` et la direction des arêtes — c'est un `DiGraph`). Refais le
test avec un graphe où toutes les paires sont mutuellement atteignables et vérifie que tu obtiens
bien 25 lignes.

---

## A9 — Fichiers congestionnés

**Objectif** : vérifier empiriquement le schéma des fichiers de temps de trajet congestionnés.

**Exemple de sortie attendue (vérifié, sur une vraie sortie de simulation,
`bassin2021/output/run/output/net_cond_next_exp_edge_ttfs.parquet`)** :
```
schema: {vehicle_id: String, edge_id: String, departure_time: Float64, travel_time: Float64}
n rows: 18 522 732
n edges distincts: 95 478
breakpoints par edge_id : min=194, max=194, moyenne=194.0   <- uniforme sur TOUTES les arêtes
departure_time (première valeur) = 10800.0  = 03:00:00 en secondes (cohérent avec
  period = ["03:00:00", "27:00:00"] du config)
```

**Point à noter (écart avec ce qu'on pourrait attendre)** : `departure_time`/`travel_time` sont
des `Float64` (secondes), pas des `Duration` polars comme le sont d'autres colonnes temporelles du
projet (ex. `TripsCarFreeFlowTravelTimesFile.free_flow_travel_time` est bien en `DURATION`, cf.
A2) — à garder en tête si tu écris du code qui mélange les deux fichiers.

**Question à répondre par écrit** : la période simulée fait 24h avec `recording_interval = 900`
(15 min), soit 96 intervalles — mais on trouve 194 breakpoints par arête, uniforme partout. 194 ≠
96. Cherche dans `metro_simulation/` (paramètres ou code de sortie) un autre paramètre qui
pourrait gouverner le nombre de breakpoints d'une fonction de temps de trajet attendu (indice :
`nb_iterations = 100` apparaît aussi dans `[simulation]` — teste l'hypothèse d'un lien avec les
itérations plutôt qu'avec l'enregistrement, et vérifie si `194` a un lien arithmétique avec un
mélange des deux). Pas de réponse garantie ici — si tu ne trouves rien de concluant dans le code
Python, documente l'hypothèse la plus plausible et pourquoi tu ne peux pas la confirmer sans lire
le moteur Rust (`Metropolis-Core/`).

---

## Grille d'auto-correction

- [ ] A1 : comportement de `AllRoadDistancesStep` sans `--step` déduit de la docstring de
      `is_primary()`, pas juste recopié.
- [ ] A2 : différence de traitement de `geometry` entre les deux classes de `validate()`
      identifiée dans le code, pas devinée.
- [ ] A3 : piège `default_speed_limit` compris (une seule clé TOML = plusieurs sous-valeurs), 2
      clés supplémentaires vérifiées par toi-même.
- [ ] A4 : chaîne à 4 maillons refaite sur un Step différent, écart éventuel noté.
- [ ] A5 : hypothèse sur `"Intersect"` formulée avec un module cible plausible.
- [ ] A6 : séquence rejouée en entier (échec puis fix), pas seulement lue.
- [ ] A7 : triangle rectangle identifié explicitement (les 3 côtés nommés), réponse médoïde vs
      approximation justifiée par le code.
- [ ] A8 : test avec graphe totalement connecté refait, 25 lignes obtenues et expliquées.
- [ ] A9 : au moins une piste concrète explorée dans `metro_simulation/` pour expliquer 194,
      même si la conclusion est "pas trouvé dans le code Python".
