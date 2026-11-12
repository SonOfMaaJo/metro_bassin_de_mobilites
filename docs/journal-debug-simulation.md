# Journal de débogage — Simulation Metropolis, bassin Grand Est (Bas-Rhin + Moselle)

Ce fichier retrace, dans l'ordre chronologique, les erreurs rencontrées lors des runs de
simulation sur le serveur Proxmox (`root@192.168.1.5`), leur diagnostic, et les correctifs
appliqués. À compléter au fur et à mesure.

**Config utilisée :** `/root/stage_simulation/config-bassin.toml` (serveur) /
`config-bassin.toml` (copie locale de référence)
**Code applicatif :** `/root/stage_simulation/pymetropolis` (orchestration Python) et
`/root/stage_simulation/Metropolis-Core` (moteur Rust, routing_cli / metropolis_cli)
**Sortie pipeline :** `/root/stage_simulation/bassin/output`

---

## 1. Panic `byte array offset overflow` sur `TripsPedestrianDistancesStep`

**Erreur brute :**
```
thread 'main' panicked at .../arrow-array-59.1.0/src/builder/generic_bytes_builder.rs:87:57:
byte array offset overflow
```

**Diagnostic :**
- `[pedestrian_routing] output_path = true` → pour chaque trajet, la liste des `edge_id` du
  chemin piéton est stockée dans la colonne `route`.
- `[pedestrian_network] reindex = false` → les `edge_id` du réseau piéton restent au format OSM
  d'origine défini dans `osm.py` : chaîne de caractères type `"123456r-2"` (id de way OSM, +"r" si
  sens inverse, +"-idx" si segment scindé), pas un entier.
- Côté Rust (`Metropolis-Core/tch/src/io/arrow.rs`, `IdBuilder`), un id non castable en `u64`/`i64`
  fait basculer le builder en `StringBuilder` (`IdArray::Arbitrary`). La colonne `route` devient un
  `List<Utf8>`.
- Tous les résultats de routing du bassin (potentiellement des millions de trajets sur Bas-Rhin +
  Moselle) sont accumulés dans **un seul** `RecordBatch` avant écriture Parquet. Le `StringBuilder`
  Arrow utilise des offsets `i32` (limite ~2,1 Go cumulés) → dépassement sur un territoire de cette
  taille.

**Décision :** ne garder pour l'instant que la distance des trajets piétons (pas le détail du
chemin), la modification du moteur de routing (batching, ids numériques, etc.) étant hors périmètre
immédiat.

**Correctif appliqué :**
```toml
[pedestrian_routing]
output_path = false   # était `true`
```
Fichier modifié : `config-bassin.toml` (ligne ~210), sur le serveur et en local.

---

## 2. `MetropyError: Cannot save DataFrame TripsPedestrianDistancesFile / DataFrame is not valid`

Conséquence directe du correctif précédent.

**Diagnostic :**
- `TripsPedestrianDistancesStep.run()` (`pymetropolis/.../routing/routing_cli.py`) ne produit plus
  que les colonnes `trip_id` et `pedestrian_distance` quand `output_path=False`.
- Le schéma `TripsPedestrianDistancesFile` (`pymetropolis/.../routing/files.py`) déclarait la
  colonne `pedestrian_path` comme `nullable=True` mais **pas** `optional=True` → validation
  (`Column.validate_df`) exige que la colonne soit présente, donc échec.
- Bug latent de `pymetropolis` (le paramètre `output_path` n'avait jamais été testé avec le schéma
  de validation à jour).

**Correctif appliqué** (fichier `pymetropolis/src/pymetropolis/metro_demand/routing/files.py`,
classe `TripsPedestrianDistancesFile`) :
```python
Column(
    "pedestrian_path",
    MetroDataType.LIST_OF_IDS,
    description="Shortest path of the trip on the pedestrian network, as a list of ids.",
    nullable=True,
    optional=True,   # <- ajouté
),
```
✅ Vérifié présent sur le serveur.

---

## 3. OOM (Out Of Memory) — premier essai de correctif sur `TripsPedestrianDistancesStep`

Avant de comprendre le vrai problème (overflow, section 1), une première tentative avec
`reindex=true` seul (sans changer `output_path`) a provoqué un **OOM kill** :

```
Out of memory: Killed process (routing_cli) total-vm:27606152kB, anon-rss:13877764kB
```
sur une VM avec seulement 15 Gio de RAM (confirmé via `dmesg` + `free -h`).

**Cause :** avec `output_path=true`, `routing_cli` garde en mémoire les chemins complets
(liste d'`edge_id`) de **tous** les trajets du bassin en une seule fois avant d'écrire le Parquet
— pas de traitement par lots dans `trip_routing()` (`routing_cli.py`).

**Résolu indirectement** par le passage à `output_path=false` (section 1) : on ne stocke plus les
chemins, donc l'empreinte mémoire redevient gérable.

**Point de vigilance pour la suite :** si on a un jour besoin des chemins piétons détaillés, il
faudra soit augmenter la RAM de la VM, soit découper `trip_routing()` en lots dans
`routing_cli.py` (modification du moteur, pas encore faite).

---

## 4. Panic `byte array offset overflow` sur `TripsCarFreeFlowTravelTimesStep`

Même symptôme que la section 1, mais cette fois sur le réseau **routier**, sans échappatoire
simple :

**Diagnostic :**
- `TripsCarFreeFlowTravelTimesStep.run()` (`routing_cli.py`) appelle `trip_routing(..., with_routes=True)`
  **en dur** (pas de paramètre de config équivalent à `pedestrian_routing.output_path`).
- La colonne `free_flow_route` est en plus **utilisée** pour calculer `free_flow_distance` (somme
  des longueurs des edges du chemin) → impossible de simplement désactiver le stockage du chemin
  ici.
- `[road_network] reindex = false` → même problème qu'en section 1 : `edge_id` du réseau routier au
  format string OSM (`road_network/osm.py`), donc `StringBuilder` côté Rust, donc overflow sur un
  territoire de cette taille.

**Correctif appliqué :**
```toml
[road_network]
reindex = true   # était `false`
```
Fichier modifié : `config-bassin.toml` (ligne ~65), sur le serveur et en local.

⚠️ Ce changement rejoue `PostprocessRoadNetworkStep` et toute la chaîne en aval (capacités,
pénalités, préprocessing TCH voiture, etc.) — traitement plus long que les correctifs précédents.

---

## 5. `SchemaError` — jointure `edge_id: u64` vs `edge_id: str` sur `RoadEdgesVariablesStep`

Conséquence du passage à `road_network.reindex = true`.

**Diagnostic :**
- `UrbanEdgesStep` (`road_network/urban.py`) calcule le flag "urbain" à partir de
  `RoadEdgesRawFile` (edges bruts, **avant** postprocessing) → produit `RoadEdgesUrbanFlagFile`
  avec des `edge_id` au format OSM string d'origine.
- `PostprocessRoadNetworkStep` (`postprocess.py`) utilise déjà ce fichier correctement (jointure
  faite **avant** le `reindex()` interne à l'étape, donc ids cohérents des deux côtés).
- Mais `RoadEdgesVariablesStep` (`variables.py`) relit **séparément** `RoadEdgesUrbanFlagFile`
  (toujours en string) et le joint à `RoadEdgesCleanFile` — qui, elle, est déjà reindexée en `u64`
  depuis le changement de la section 4. D'où le mismatch de type sur la jointure `edge_id`.
- Bug de conception dans `pymetropolis` : `RoadEdgesUrbanFlagFile` n'a jamais été pensé pour
  survivre à un `reindex=true` des edges. `capacities.py` et `penalties.py` ont le même schéma de
  jointure fragile, mais ne sont pas déclenchés avec la config actuelle (pas de split urbain/rural
  dans `[road_network.capacities]` ni `[road_network.penalties]` pour l'instant — **à surveiller si
  ça change un jour**).

**Correctif appliqué (3 fichiers, `pymetropolis/src/pymetropolis/metro_network/road_network/`) :**

1. **`files.py`** — colonne `urban` ajoutée au schéma de `RoadEdgesCleanFile` :
   ```python
   Column(
       "urban",
       MetroDataType.BOOL,
       description="Whether the edge is fully contained within the urban areas.",
       nullable=False,
       optional=True,
   ),
   ```

2. **`postprocess.py`** — le flag `urban` est fusionné sur `gdf` juste après le chargement de
   `urban_flags`, donc **avant** `remove_duplicates` / `select_connected` / `reindex()` (les ids
   sont encore au format brut à ce moment, cohérents avec `urban_flags`) :
   ```python
   if urban_flags is not None:
       gdf = gdf.merge(urban_flags.to_pandas()[["edge_id", "urban"]], on="edge_id", how="left")
       gdf["urban"] = gdf["urban"].fillna(False)
   ```

3. **`variables.py`** — suppression de la jointure devenue incohérente sur
   `RoadEdgesUrbanFlagFile` ; la colonne `urban` est lue directement depuis `RoadEdgesCleanFile`
   (elle y est déjà, donc plus besoin de la relire séparément) :
   - Retrait de `"urban": InputFile(RoadEdgesUrbanFlagFile, optional=True)` de `input_files`.
   - Retrait du bloc `if self.input["urban"].exists(): ... df = df.join(urban_flags, on="edge_id")`.
   - Retrait des imports devenus inutiles (`RoadEdgesUrbanFlagFile`, `InputFile`).

✅ Déployé sur le serveur + copie locale synchronisée. Compilation Python (`py_compile`) vérifiée
des deux côtés.

---

## 6. `ERROR: coeficients ... not available in the edges' variables: {'urban'}`

**Diagnostic (piège du cache du pipeline) :**
- Le pipeline (`metro_pipeline/pipeline.py`, `Step.update_required()`) décide de rejouer une étape
  en comparant les **mtimes des fichiers d'E/S** et un **hash de config** — il ne regarde jamais le
  contenu du code source Python.
- Après le déploiement du correctif de la section 5, `RoadEdgesVariablesStep` a bien été rejoué,
  mais son entrée `RoadEdgesCleanFile` (`edges_clean.geo.parquet`) datait de **01:27**, soit
  **avant** le déploiement du patch (01:40) → `PostprocessRoadNetworkStep` n'avait pas été
  considéré "outdated" (aucun paramètre de config lié n'avait changé) et n'a donc pas régénéré ce
  fichier avec la colonne `urban`.
- Résultat : `edges_variables.parquet` ne contenait toujours pas de colonne `urban`, d'où l'échec
  de `EdgePenaltiesFromCoefficientsStep` qui cherche `urban` (référencée dans
  `bassin/data/edges_penalty_coefficients.csv`, cf. interaction `traffic_signals` × `urban`) parmi
  les colonnes disponibles.

**Correctif appliqué :** suppression manuelle du fichier de sortie périmé pour forcer sa
régénération (le pipeline détecte alors `metro_file_clean_edges` manquant → `update_required() ==
True` → cascade automatique sur les étapes en aval via leur propre détection de mtime) :
```bash
rm /root/stage_simulation/bassin/output/network/road_network/edges_clean.geo.parquet
```

**⚠️ Règle générale à retenir :** toute modification du code Python de `pymetropolis` (contrairement
à un changement de paramètre TOML) n'est **pas** détectée automatiquement par le pipeline. Il faut
supprimer manuellement le(s) fichier(s) de sortie de l'étape concernée (ou son
`update_files/<Step>.json`) pour forcer sa ré-exécution après un patch de code.

---

## 7. `SchemaError` — jointure `edge_id: str` vs `edge_id: u64` sur `WriteMetroEdgesStep`

Nouvelle conséquence du passage à `road_network.reindex = true` (section 4), même famille de bug
que la section 5, mais dans `metro_simulation/supply/edges.py`.

**Erreur brute :**
```
MetropyError: Failed to execute step `WriteMetroEdgesStep`
        0: SchemaError: datatypes of join keys don't match - `edge_id`: str on left does not match
`edge_id`: u64 on right (and no other type was available to cast to)
```

**Diagnostic :**
- `WriteMetroEdgesStep.run()` caste explicitement `edge_id`/`source`/`target` en `String` sur `df`
  (dérivé de `RoadEdgesCleanFile`) dès le début, pour gérer les cas d'edges parallèles / voies HOV
  (id du type `"123-dummy"`, `"123-hov"`, etc., qui ne peuvent pas être des entiers).
- `df` est ensuite joint à `primary_flags` (`RoadEdgesPrimaryFlagFile`), produit par
  `PrimaryEdgesStep` (`metro_demand/routing/road_split.py`) directement à partir de
  `RoadEdgesCleanFile`, **sans caster `edge_id` en string** — cette table hérite donc du type `u64`
  depuis le passage à `reindex = true`.
- Résultat : jointure `df (str) ⋈ primary_flags (u64)` → mismatch de type.
- Plus loin dans le même fichier, les jointures avec `capacities` et `penalties` faisaient déjà ce
  cast défensif (`original_id=pl.col("edge_id").cast(pl.String)`) — seule la jointure
  `primary_flags` avait été oubliée. Ça ne posait pas de problème avant le passage à
  `reindex=true` (tout était uniformément string à l'époque).
- Vérification faite du deuxième consommateur de `RoadEdgesPrimaryFlagFile`
  (`CarAccessEgressStep`, même fichier `road_split.py`) : celui-ci joint `primary_flags` avec
  `RoadEdgesCleanFile` (les deux en `u64`, cohérents) → **pas de bug ici**, rien à corriger.

**Correctif appliqué** (fichier `pymetropolis/src/pymetropolis/metro_simulation/supply/edges.py`,
`WriteMetroEdgesStep.run()`) :
```python
if self.input["primary_flags"].exists():
    primary_flags = self.input["primary_flags"].read().with_columns(
        pl.col("edge_id").cast(pl.String)
    )
    df = df.join(primary_flags.filter("primary"), on="edge_id", how="semi")
```
(ajout du `.with_columns(pl.col("edge_id").cast(pl.String))`, même pattern que `capacities`/`penalties`)

✅ Déployé sur le serveur + copie locale synchronisée. Compilation Python (`py_compile`) vérifiée
des deux côtés. Pas de fichier de sortie périmé à supprimer : l'étape plantait avant d'écrire
`run/input/edges.parquet`, donc rien à invalider.

---

## 8. OOM sur `RunSimulationStep` (`metropolis_cli`) — manque de RAM, pas de disque

**Contexte :** en préparant `RunSimulationStep`, écarté d'abord une fausse piste "espace disque"
(voir aussi le nettoyage `/var/cache/apt` ci-dessous, utile mais pas la cause principale) : le
vrai problème est la **RAM**.

**Diagnostic (`dmesg -T`) :**
```
oom-kill: ... task=metropolis_cli ... total-vm:36877176kB, anon-rss:14585700kB ...
oom-kill: ... task=metropolis_cli ... total-vm:46420856kB, anon-rss:14552364kB ...
```
- L'hôte Proxmox n'a que **15.75 Go de RAM physique** (`MemTotal` dans `/proc/meminfo`).
- `metropolis_cli` (le moteur de simulation, pas `routing_cli`) est tué deux fois de suite juste
  au-dessus de 14.5 Go de RSS.
- Deux VMs tournent en parallèle sur le même hôte et réservent de la RAM : `100
  (nixos-25.05-template)` → 2048 Mo, `200 (debianS)` → 4096 Mo (6 Go au total indisponibles pour
  la simulation).
- Nettoyage fait en parallèle (sans lien direct avec la RAM, mais utile) : `apt-get clean` a
  libéré ~13 Go d'espace disque (`/var/cache/apt`), portant l'espace libre de 13 Go à 25 Go — ça
  concerne l'espace disque de `RunSimulationStep`, pas sa consommation mémoire.

**Pistes envisagées pour la RAM :**
1. Arrêter temporairement les VMs 100 et 200 pendant le run (libère 6 Go) — pas fait, demande une
   confirmation de l'utilisateur au préalable (ce sont peut-être des VMs utilisées par d'autres).
2. **Réduire réellement le nombre d'agents simulés**, via `[synthetic_population] fraction`
   (`population/eqasim.py`, `ReadEqasimPopulationStep` : `df.sample(fraction=...)`) — c'est le
   levier qui a un effet direct sur la RAM de `metropolis_cli`, contrairement à `simulation_ratio`
   seul (voir point d'attention ci-dessous).
3. Augmentation de RAM physique : question matérielle, hors de portée à distance.

**⚠️ Point d'attention important — `simulation_ratio` ≠ échantillonnage :**
`simulation_ratio` (`metro_simulation/common.py`, `StepWithSimulationRatio`) est un facteur de
**remise à l'échelle** des capacités routières et des résultats agrégés — sa docstring précise
explicitement qu'il **n'affecte pas** la taille de la matrice OD ni de la population synthétique en
entrée. Le réduire seul ne change donc **pas** le nombre d'agents traités par `metropolis_cli`, et
n'a **aucun effet sur la RAM**. Il doit être utilisé **en complément** de `fraction`, avec la même
valeur (ex. `fraction = 0.5` + `simulation_ratio = 0.5`), pour que les capacités/résultats restent
correctement calibrés une fois la population sous-échantillonnée.

**Correctif envisagé (config uniquement, pas encore appliqué) :**
```toml
[synthetic_population]
fraction = 0.5          # à ajuster selon la RAM disponible

simulation_ratio = 0.5  # même valeur que `fraction`
```

**Fichiers à supprimer pour forcer la ré-exécution : aucun.** `fraction` et `simulation_ratio`
sont des `Parameter` déclarés dans le framework `pymetropolis` (comme `road_network.reindex`),
donc ils participent au `config_hash()` de chaque étape concernée. Contrairement à un patch de
code Python (cf. section 6), un changement de valeur TOML est détecté automatiquement par
`Step.update_required()` : `ReadEqasimPopulationStep` sera vu comme périmé et toute la chaîne en
aval (démographie → routing → edges → `RunSimulationStep`) sera rejouée automatiquement, sans
suppression manuelle de fichier.

---

## 9. Restriction de l'emprise géographique aux 817 communes du bassin de mobilité

**Objectif :** le run travaillait sur les 2 départements complets (Bas-Rhin + Moselle,
~10 970 km²), alors que le périmètre réel est le "bassin de mobilité" défini dans
`BASSIN_MOBILITE_GE_SGP2026.xlsx` (817 communes, colonne `COMMUNE` = code INSEE, `DEPT` = 57/67).
Réduire l'emprise réduit mécaniquement la taille du réseau et de la demande, donc la RAM
nécessaire pour `RunSimulationStep` — complémentaire (et plus fiable) que le levier
`fraction`/`simulation_ratio` de la section 8.

**Démarche :**
1. Lecture du xlsx (`openpyxl`) → 817 codes INSEE uniques, tous dans les départements 57/58/67.
2. Vérification que le `.osm.pbf` existant (`bassin_mobilites_grand_est.osm.pbf`, 133 Mo) contient
   bien le tag `ref:INSEE` sur les relations `admin_level=8` (communes) — confirmé via `pyosmium`
   (1255 communes présentes dans l'extrait départemental d'origine).
3. Script `extract_communes.py` (déployé sur le serveur, copie locale dans
   `/home/sonOfMaaJo/metropolis/`) : filtre les relations `admin_level=8` par `ref:INSEE` (plus
   fiable qu'un filtre par `name`, qui aurait posé des problèmes d'accents/casse avec les noms en
   capitales du xlsx) → **817/817 communes trouvées**, union des polygones reprojetée en
   `EPSG:2154`, écrite dans `bassin/data/simulation_area_communes.geojson` (7614 km², contre
   ~10 970 km² pour les 2 départements).
4. Script `build_extract_polygon.py` : bufferise ce polygone de **10 km** (marge de sécurité pour
   ne pas couper le réseau routier pile à la frontière communale, cohérent avec le buffer de 8 km
   déjà utilisé par `[osm_road_import] simulation_area_buffer`) et le reprojette en `EPSG:4326`
   pour `osmium extract`.
5. Installation de `osmium-tool` (paquet Debian standard, `apt-get install osmium-tool`) —
   absent du système, nécessaire pour découper proprement le `.osm.pbf` (gestion correcte des
   ways/relations coupés par la frontière via la stratégie `smart`).
6. Découpage : `osmium extract -p extract_polygon_buffered.geojson -s smart -o
   bassin_mobilite_ge_sgp2026.osm.pbf bassin_mobilites_grand_est.osm.pbf` → nouveau fichier de
   **99.6 Mo** (contre 133 Mo), validé avec `osmium fileinfo`.

**Correctif appliqué (`config-bassin.toml`, serveur + local) :**
```toml
osm_file = "./bassin/data/bassin_mobilite_ge_sgp2026.osm.pbf"   # était bassin_mobilites_grand_est.osm.pbf

[simulation_area]
# SimulationAreaFromPolygonsStep au lieu de SimulationAreaFromOSMStep : union des polygones
# des 817 communes (déjà calculée), au lieu d'un filtre par nom de département.
polygon_file = "bassin/data/simulation_area_communes.geojson"
# (osm_admin_level / osm_name retirés)
```

**Fichiers à supprimer pour forcer la ré-exécution : aucun**, même logique que la section 8 —
`osm_file` et `simulation_area.polygon_file` sont des `Parameter` suivis par `config_hash()`. Ce
changement étant fondamental (il touche l'entrée de tout le pipeline), il est normal que la quasi
totalité des étapes soit rejouée au prochain lancement.

**Fichiers créés :**
- `bassin/data/bassin_mobilite_ge_sgp2026.osm.pbf` (nouveau fichier OSM restreint)
- `bassin/data/simulation_area_communes.geojson` (polygone de la zone d'étude, 817 communes)
- `bassin/data/extract_polygon_buffered.geojson` (polygone bufferisé, utilisé seulement pour le
  découpage, pas référencé dans la config)
- `bassin/data/bassin_mobilite_insee_codes.txt` (liste des 817 codes INSEE)
- `extract_communes.py`, `build_extract_polygon.py` (scripts de préparation, à la racine du
  projet sur le serveur et en local — pas dans `pymetropolis/`, ce sont des utilitaires de
  préparation de données, pas du code du pipeline)

---

## 10. Script d'automatisation `build_communes_osm.sh`

Généralisation des sections 3 et 9 : au lieu de scripts Python ad-hoc à relancer manuellement, un
script shell unique et interactif qui fusionne N `.osm.pbf` puis les restreint aux communes d'un
CSV (même format que `BASSIN_MOBILITE_GE_SGP2026.xlsx`), avec vérification/installation des
dépendances.

**Fichier :** `build_communes_osm.sh` (racine du projet, serveur + local).

**Usage :**
```bash
# Interactif (pose les questions si des arguments manquent) :
./build_communes_osm.sh

# Non-interactif :
./build_communes_osm.sh --csv communes.csv --pbf a.osm.pbf b.osm.pbf --output bassin.osm.pbf -y
```
Options : `--insee-column` (défaut `COMMUNE`), `--buffer` (défaut 10000 m), `--crs` (défaut
`EPSG:2154`), `--strategy` (défaut `smart`, passé à `osmium extract`), `-y/--yes`.

**Ce que fait le script :**
1. **Dépendances** : vérifie `python3` et `osmium` (CLI, paquet `osmium-tool`) ; installe ce
   dernier automatiquement si absent (détecte `apt`/`dnf`/`yum`/`pacman`/`brew`). Pour les modules
   Python (`osmium`, `geopandas`), vérifie d'abord le `python3` système ; s'ils manquent, crée un
   environnement virtuel dédié et persistant (`./.build_communes_osm_venv`, réutilisé aux
   exécutions suivantes) plutôt que d'essayer un `pip install` global — nécessaire sur les
   systèmes Debian/Ubuntu récents où le python système est "externally-managed" (PEP 668) et
   refuse les installations globales.
2. **Fusion** : si plusieurs `.osm.pbf` sont fournis, `osmium merge` les combine (déduplique les
   objets communs aux fichiers qui se chevauchent) ; si `merge` échoue faute de tri, retente après
   un `osmium sort` sur chaque fichier. Si un seul fichier est fourni, aucune fusion.
3. **Ciblage des communes** : lit le CSV, en tire l'ensemble des codes INSEE (colonne
   configurable), filtre les relations `admin_level=8` du (des) fichier(s) OSM par `ref:INSEE`,
   fait l'union des polygones trouvés, l'écrit en GeoJSON (reprojeté selon `--crs`) — directement
   réutilisable comme `[simulation_area] polygon_file` dans `pymetropolis`. Les codes non trouvés
   sont listés dans un fichier `<sortie>_missing_communes.txt` à côté du résultat, sans faire
   échouer le script (juste un avertissement).
4. **Découpe** : bufferise ce polygone (marge de sécurité pour ne pas couper le réseau routier à
   la frontière) puis `osmium extract -s smart` produit le `.osm.pbf` final.

**Tests effectués (sur le serveur, avant livraison) :**
- 1 fichier en entrée (le `.osm.pbf` Bas-Rhin+Moselle existant) → 817/817 communes trouvées,
  résultat cohérent avec le découpage manuel de la section 9 (~96 Mo).
- 2ᵉ exécution → environnement virtuel bien réutilisé (pas de réinstallation), plus rapide.
- 2 fichiers en entrée qui se chevauchent partiellement (test synthétique, deux extraits par
  bounding-box) → fusion `osmium merge` réussie, et les communes hors des deux emprises de test
  ont bien été signalées comme manquantes (54 dans ce test) sans faire planter le script — confirme
  que la détection/rapport des communes manquantes fonctionne.
- Fichiers de test nettoyés après coup (`/tmp/test_bassin*`, `/tmp/part_*`).

**Fichier CSV de référence créé :** `BASSIN_MOBILITE_GE_SGP2026.csv` (conversion directe du xlsx
fourni, mêmes colonnes), pour servir d'exemple/donnée de test au script.

---

## 11. `build_communes_osm.sh` — prise en charge des communes transfrontalières (Allemagne)

**Contexte :** l'étude va inclure des communes allemandes limitrophes (personnes résidant/
travaillant côté allemand). Le script de la section 10 ne matchait les communes que par le tag
OSM `ref:INSEE`, propre à la France — une commune allemande ajoutée au CSV aurait été silencieusement
ignorée (ni trouvée, ni signalée comme erreur bloquante, juste absente du résultat).

**Diagnostic :** les communes allemandes (`admin_level=8` également) portent leur code officiel
sous un tag différent : `de:amtlicher_gemeindeschluessel` (AGS, 8 chiffres), pas `ref:INSEE`
(5 chiffres). Un code INSEE et un code AGS peuvent cohabiter dans la même colonne CSV sans
ambiguïté : ce sont deux formats de longueur différente.

**Correctif appliqué** (`build_communes_osm.sh`, fonction `extract_target_area`, code Python embarqué) :
1. `normalize_code()` : normalise chaque code selon sa longueur — ≤ 5 chiffres → INSEE, zero-paddé
   à 5 (gère aussi les codes non numériques type Corse `2A004`, laissés tels quels en majuscules) ;
   ≤ 8 chiffres → AGS allemand, zero-paddé à 8.
2. Le filtre `admin_level=8` teste maintenant trois tags dans l'ordre `ref:INSEE` →
   `de:amtlicher_gemeindeschluessel` → `ref` (repli générique), et retient le premier qui matche un
   code du CSV.
3. Documentation mise à jour dans l'en-tête du script (`--insee-column` renommé implicitement en
   "colonne code commune INSEE et/ou AGS") : pour ajouter des communes allemandes, il suffit
   d'ajouter leurs codes AGS dans la même colonne du CSV et de fournir en `--pbf` un extrait OSM
   couvrant aussi le côté allemand (ex. extrait Geofabrik "Baden-Württemberg" ou
   "Rheinland-Pfalz" en plus de l'extrait français, fusionnés automatiquement par le script).

**Vérification effectuée (2026-07-12) :**
- Rechargement de `build_communes_osm.sh` (local + serveur), `bash -n` OK des deux côtés, `diff`
  confirmant les deux copies identiques.
- `--help` vérifié sur le serveur (nouvelle section transfrontalière bien affichée).
- Test synthétique bout-en-bout sur le serveur (`/tmp/test_de_match`, nettoyé après coup) : fichier
  `.osm.pbf` construit à la main (`osmium cat` depuis un XML minimal) contenant une seule relation
  `admin_level=8` taguée `de:amtlicher_gemeindeschluessel=08221000` (pas de `ref:INSEE`), avec un
  CSV contenant ce même code dans la colonne `COMMUNE`. Exécution complète du script
  (`./build_communes_osm.sh --csv ... --pbf ... --output ... -y`) : commune trouvée (1/1) via le tag
  allemand, polygone extrait, `.osm.pbf` de sortie produit sans erreur.

**⚠️ Limite non levée :** le tag `de:amtlicher_gemeindeschluessel` est la convention OSM standard
documentée pour l'Allemagne, mais n'a été testé que sur des données synthétiques — pas encore
validé sur un véritable extrait OSM allemand (ex. Geofabrik). À reconfirmer avec un vrai fichier le
jour où l'utilisateur ajoutera des communes allemandes réelles au CSV.

**Fichiers modifiés :** `build_communes_osm.sh` (serveur + local, identiques).

---

## 12. Renommage du script + clarification sur `main_directory`

**Renommage :** `build_bassin_osm.sh` → `build_communes_osm.sh` (nom demandé, plus générique — le
script sert à n'importe quel ensemble de communes, pas seulement le bassin GE). Toutes les
références internes (messages de log, usage, dossier du venv) renommées en cohérence. Le venv déjà
installé sur le serveur a été **renommé** (`.build_bassin_osm_venv` → `.build_communes_osm_venv`)
plutôt que recréé, pour ne pas réinstaller `osmium`/`geopandas` inutilement. Vérifié par un run
complet post-renommage (817/817 communes, 7614.0 km², cohérent avec la section 9).

**Clarification `main_directory` :** question posée sur le lien entre le dossier de sortie du
script et `main_directory` de `config-bassin.toml` (`./bassin/output`). Réponse retenue : **aucun
lien automatique**, par choix — `main_directory` est le dossier de travail interne du pipeline
`pymetropolis` (régénéré/écrit par les `Step` à chaque run), alors que les fichiers produits par
`build_communes_osm.sh` (`.osm.pbf` restreint, `simulation_area.geojson`) sont des **données
d'entrée** du pipeline (référencées par `osm_file` / `simulation_area.polygon_file`), stockées dans
`bassin/data/` à côté du CSV et des GTFS. Les mélanger avec `bassin/output` risquerait qu'un
nettoyage/une régénération du dossier de sortie du pipeline supprime des données d'entrée. Le
`--output` du script reste donc un chemin choisi manuellement, indépendant de `main_directory`.

---

## 13. Simplification du CSV d'entrée à 2 colonnes (code + nom)

**Constat :** le format `BASSIN_MOBILITE_GE_SGP2026.xlsx` d'origine (`REGION, DEPT, CANTVILLE,
COMMUNE, NCC`) porte 3 colonnes inutiles pour l'usage du script — seul le code commune
(`COMMUNE`) est effectivement utilisé pour le filtrage OSM ; `NCC` (nom) n'est même pas exploité
par le script (le nom affiché dans les résultats vient du tag OSM `name`, pas du CSV).

**Décision :** documenter/adopter un format simplifié à 2 colonnes : le code commune (INSEE ou
AGS, colonne configurable via `--insee-column`, défaut `COMMUNE`) et le nom de la commune (colonne
`NCC` par défaut, gardée uniquement pour la lisibilité humaine du CSV — utile pour repérer une
commune allemande ajoutée à la main, par exemple). Aucune colonne n'est requise en plus : le
script (fonction `extract_target_area`, lecture via `csv.DictReader`) n'a jamais lu que la colonne
de code, donc les colonnes surnuméraires du fichier d'origine étaient déjà ignorées sans effort —
la seule vraie nouveauté est de **documenter** ce format minimal et de fournir un CSV d'exemple à 2
colonnes, pour ne plus donner l'impression que `REGION`/`DEPT`/`CANTVILLE` sont nécessaires.

**Modifications :**
- `build_communes_osm.sh` : en-tête réécrit pour décrire le format 2-colonnes comme format de
  référence (l'ancien format à 5 colonnes reste accepté, toute colonne en trop étant ignorée).
  Ligne `usage()` (`sed -n '2,38p'`) réajustée pour l'en-tête agrandi.
- `BASSIN_MOBILITE_GE_SGP2026.csv` régénéré depuis le xlsx d'origine avec seulement les colonnes
  `COMMUNE, NCC` (817 lignes, sert de CSV d'exemple/test).

**Vérification :** `bash -n` OK, `--help` inspecté (nouvelle description affichée correctement),
run complet sur le serveur avec le CSV simplifié + le `.osm.pbf` restreint existant →
**817/817 communes trouvées, 7614.0 km²**, identique aux résultats précédents (section 9, section
12) : le changement est purement documentaire, aucune régression.

**Fichiers modifiés :** `build_communes_osm.sh`, `BASSIN_MOBILITE_GE_SGP2026.csv` (serveur + local,
identiques).

---

## 14. `InvalidOperationError` — `union`/`concat` `edge_id: str` vs `edge_id: u64` sur `RouteResultsStep`

Nouvelle conséquence, de la même famille que les sections 5 et 7, du passage à
`road_network.reindex = true` (section 4) — cette fois sur la reconstruction des trajets complets
(partie primaire + accès/égression) pour les résultats détaillés.

**Erreur brute :**
```
MetropyError: Failed to execute step `RouteResultsStep`
        0: InvalidOperationError: 'union'/'concat' inputs should all have the same schema,got
Schema { fields: {"trip_id": String, "edge_id": String, "entry_time": Duration('μs'), "exit_time": Duration('μs'),
"travel_time": Duration('μs')}, metadata: () } and
Schema { fields: {"trip_id": String, "edge_id": UInt64, "entry_time": Duration('μs'), "exit_time": Duration('μs'),
"travel_time": Duration('μs')}, metadata: () }

Resolved plan until failure:

        ---> FAILED HERE RESOLVING THIS_NODE <---
SELECT [col("trip_id"), col("edge_id"), col("entry_time"), col("exit_time"), col("travel_time")]
   WITH_COLUMNS:
   [[(col("exit_time")) - (col("travel_time"))].alias("entry_time")]
     WITH_COLUMNS:
     [[(col("primary_end")) + (col("travel_time").cum_sum().over([col("trip_id")]))].alias("exit_time")]
      INNER JOIN:
      LEFT PLAN ON: [col("trip_id")]
        INNER JOIN:
        LEFT PLAN ON: [col("edge_id")]
          SELECT [col("trip_id"), col("egress_path").alias("edge_id")]
            EXPLODE [egress_path], empty_as_null: false, keep_nulls: false
              Parquet SCAN [bassin/output/demand/population/primary_car_trips_access_egress.parquet]
              PROJECT */9 COLUMNS
              ESTIMATED ROWS: 887883
        RIGHT PLAN ON: [col("edge_id")]
          SELECT [col("edge_id"), col("free_flow_travel_time").alias("travel_time")]
            Parquet SCAN [bassin/output/network/road_network/edges_free_flow_travel_time.parquet]
            PROJECT */2 COLUMNS
            ESTIMATED ROWS: 202650
        END INNER JOIN
      RIGHT PLAN ON: [col("trip_id")]
        DF ["trip_id", "primary_end"]; PROJECT */2 COLUMNS
      END INNER JOIN
```

**Diagnostic** (`pymetropolis/.../metro_results/demand/postprocess.py`, `RouteResultsStep.run()`) :
- `lf`, dérivé de `MetroRouteResultsFile` (sortie brute de `metropolis_cli`), a un `edge_id` de type
  **String** — cohérent avec `WriteMetroEdgesStep` qui caste explicitement `edge_id` en string
  avant l'écriture du réseau envoyé au moteur Rust (cf. section 7 : nécessaire pour gérer les
  edges parallèles / voies HOV, id du type `"123-dummy"`).
- `access_edges`, `egress_edges` et `secondary_routes` sont construits en joignant les colonnes
  `access_path`/`egress_path` de `PrimaryCarTripsAccessEgressFile` avec `edges_fftt`
  (`RoadEdgesFreeFlowTravelTimeFile`) — cette dernière est en `u64` depuis le passage à
  `reindex = true` (section 4), donc le résultat de ces 3 blocs hérite du type `u64`.
- `pl.concat((lf, access_edges, egress_edges), how="vertical")` (puis `pl.concat((lf,
  secondary_routes), ...)`) échoue car Polars exige des schémas identiques pour un concat vertical.

**Correctif appliqué** (fichier `pymetropolis/src/pymetropolis/metro_results/demand/postprocess.py`,
`RouteResultsStep.run()`, même pattern que les sections 5 et 7 : caster vers `String` le côté qui
vient du réseau routier "brut", pour rejoindre le typage du moteur de simulation) : dans les 3
`.select("trip_id", "edge_id", "entry_time", "exit_time", "travel_time")` finaux de
`access_edges`, `egress_edges` et `secondary_routes`, remplacement de `"edge_id"` par
`pl.col("edge_id").cast(pl.String)`.

✅ Déployé sur le serveur + copie locale synchronisée. Compilation Python (`py_compile`) vérifiée
des deux côtés. **Aucun fichier de sortie périmé à supprimer** : `results/route_results.parquet`
n'existait pas encore sur le serveur (le step plantait avant d'atteindre le `write()` final).

**Fichiers modifiés :** `pymetropolis/.../metro_results/demand/postprocess.py`.

---

## 15. Pipeline complet exécuté avec succès (2026-07-13, ~22:11)

Après le correctif de la section 14, le pipeline est allé jusqu'au bout sur l'emprise des 817
communes du bassin de mobilité.

**Vérification faite :**
- Plus aucun processus `metropolis_cli`/`routing_cli`/pipeline en cours sur le serveur.
- Tous les fichiers de sortie attendus sont présents dans `bassin/output/results/` :
  `trip_results.parquet` (46 Mo), `route_results.parquet` (493 Mo — preuve directe que le
  correctif de la section 14 fonctionne), `activity_results.parquet` (18 Mo),
  `iteration_results.parquet`, `aggregate_results.json`, dossier `graphs/`.
- `aggregate_results.json` cohérent : parts modales plausibles (`car_driver` ≈ 69 % des trajets,
  `walking` ≈ 20 %, `public_transit` ≈ 6 %, `bicycle` ≈ 2 %, `car_passenger` ≈ 3 %) et
  32.9M km-véhicule au total sur le bassin.

**État :** run considéré comme réussi sur la nouvelle emprise restreinte. Aucune anomalie
supplémentaire détectée pour l'instant.

---

## 16. Analyse détaillée des résultats (`nb_iterations = 1`) — traîne de congestion suspecte

**Volumétrie :** 959 014 trajets simulés au total (`trip_results.parquet`). Répartition modale
cohérente avec `aggregate_results.json` : `car_driver` 664 818 (69%, temps moyen 69.1 min,
distance moyenne 8.2 km), `walking` 187 986 (20%, 7.6 min), `public_transit` 56 913 (6%,
28.9 min), `car_passenger` 32 770 (3%, 139.3 min, 42.0 km), `bicycle` 16 527 (2%, 8.7 min).

**⚠️ Anomalie détectée — congestion routière à traîne lourde :**
- Temps de trajet routier moyen = 75.4 min vs free-flow moyen = 12.2 min (ratio ~6.16×), mais la
  **médiane** du ratio congestion individuel n'est que **1.005** (la moitié des trajets routiers ne
  sont quasiment pas ralentis) — la moyenne est tirée par une traîne lourde :
  - ratio > 10× : 9.16% des trajets routiers (61 315)
  - ratio > 50× : 3.03% (20 309)
  - ratio > 100× : 0.63% (4 252)
  - **0.646% (4 327 trajets) mettent plus de 24h à arriver**, plus long que toute la période
    simulée (`[simulation] period = ["03:00:00", "27:00:00"]`).
- Traîne qui **s'aggrave avec l'heure de départ** : ~8-11% de trajets "très congestionnés"
  (ratio > 10×) aux heures de pointe (7h-19h), mais **20-24%** pour les départs après minuit —
  signe d'un embouteillage qui s'accumule sans jamais se résorber sur la période simulée.
- **Cause diagnostiquée :** `config-bassin.toml` avait `[simulation] nb_iterations = 1` — une
  seule itération signifie qu'aucun agent n'ajuste son heure de départ/itinéraire en réaction à la
  congestion réellement observée (choix faits une fois sur la base des temps attendus). Avec
  `spillback = true`, les files d'attente s'accumulent alors sans jamais se stabiliser — artefact
  classique d'un assignment "one-shot" non équilibré, pas un signal de congestion réelle du bassin.

**Recommandation faite :** relancer avec `nb_iterations` > 1 pour laisser le modèle converger.
Aucun fichier à supprimer pour ce changement : `nb_iterations` (`IntParameter`,
`metro_simulation/parameters/step.py:92`) est suivi par `config_hash()`, donc la cascade
(`WriteMetroParametersStep` → `RunSimulationStep` → tous les steps de résultats) est automatique.

---

## 17. Confirmation : `nb_iterations = 100` résout la traîne de congestion

**Run relancé par l'utilisateur** avec `nb_iterations = 100` (terminé le 2026-07-14, ~04:06,
aucun fichier supprimé au préalable — cascade automatique confirmée). `iteration_results.parquet`
contient bien 100 lignes.

**Convergence confirmée :**
| itération | `rmse_simulated_road_travel_times` | `mean_road_trip_travel_time` | `mean_surplus` |
| --- | --- | --- | --- |
| 1 | 2min 49s | 1h 14min 50s | -4.544 |
| 10 | 3.8s | 13min 12s | -5.249 |
| 50 | 1.0s | 12min 26s | -4.882 |
| 100 | 0.75s | 12min 18s | -4.775 |

Le RMSE chute de 2min49s à moins d'1s dès l'itération 20 et reste stable — convergence atteinte.

**Traîne de congestion quasiment disparue :**
| | 1 itération | 100 itérations |
| --- | --- | --- |
| ratio > 10× | 9.16% (61 315) | 0.0001% (1 trajet) |
| ratio > 50× | 3.03% | 0 |
| trajets > 24h | 0.646% (4 327) | 0 |
| temps trajet moyen vs free-flow | 75.4 min vs 12.2 min (×6.16) | 12.9 min vs 12.3 min (×1.05) |

Confirme l'hypothèse de la section 16 : avec `nb_iterations = 1`, l'absence d'adaptation des
agents à la congestion produisait un gridlock artificiel cumulatif. Avec 100 itérations, le réseau
atteint un état stationnaire réaliste (1.28% des trajets routiers avec un ratio > 1.5×, cohérent
avec de la congestion d'heure de pointe plausible).

**État :** résultats du run à 100 itérations considérés comme fiables pour analyse. Aucun fichier
modifié pour cette section (analyse en lecture seule ; scripts d'analyse temporaires supprimés du
serveur après usage).

---

## État à date (2026-07-14, ~06:15)

- [x] Sections 1 à 14 : tous les correctifs de schéma/config appliqués et déployés
      (`pedestrian_routing`, `road_network.reindex`, colonne `urban`, restriction géographique aux
      817 communes, script `build_communes_osm.sh`, cast `edge_id` sur `RouteResultsStep`).
- [x] Run complet terminé avec succès sur l'emprise des 817 communes, `nb_iterations = 1` d'abord
      (section 15), puis analyse détaillée révélant une traîne de congestion suspecte due au
      manque d'itérations (section 16).
- [x] **Run relancé et confirmé avec `nb_iterations = 100`** : convergence atteinte, traîne de
      congestion résorbée, résultats jugés fiables (section 17).
- [ ] **Prochaine étape :** RAS pour l'instant côté fiabilité des résultats. Rester vigilant sur la
      RAM (section 8 : VMs 100/200 concurrentes) si une itération future élargit à nouveau
      l'emprise géographique ou augmente encore `nb_iterations`/la population simulée.

## Fichiers modifiés (récapitulatif)

| Fichier | Nature du changement |
| --- | --- |
| `config-bassin.toml` | `pedestrian_routing.output_path = false`, `road_network.reindex = true`, `pedestrian_network.reindex = true`, `osm_file`/`simulation_area.polygon_file` restreints aux 817 communes |
| `pymetropolis/.../metro_demand/routing/files.py` | `pedestrian_path` → `optional=True` |
| `pymetropolis/.../metro_network/road_network/files.py` | ajout colonne `urban` (optionnelle) à `RoadEdgesCleanFile` |
| `pymetropolis/.../metro_network/road_network/postprocess.py` | persistance du flag `urban` avant reindex |
| `pymetropolis/.../metro_network/road_network/variables.py` | suppression de la jointure obsolète sur `RoadEdgesUrbanFlagFile` |
| `pymetropolis/.../metro_simulation/supply/edges.py` | cast `edge_id` → `String` sur `primary_flags` avant jointure (`WriteMetroEdgesStep`) |
| `pymetropolis/.../metro_results/demand/postprocess.py` | cast `edge_id` → `String` sur `access_edges`/`egress_edges`/`secondary_routes` avant concat (`RouteResultsStep`) |
| `build_communes_osm.sh`, `BASSIN_MOBILITE_GE_SGP2026.csv` | script d'automatisation de restriction géographique (transfrontalier, CSV 2 colonnes) |

Tous ces fichiers ont été modifiés à la fois sur le serveur (`root@192.168.1.5:/root/stage_simulation/...`)
et dans la copie locale de référence (`/home/sonOfMaaJo/metropolis/...`).
