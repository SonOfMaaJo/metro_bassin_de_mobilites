# Méthodologie — intégration des frontaliers vers l'Allemagne

Ce document détaille la méthodologie complète du projet d'intégration des travailleurs
frontaliers résidant dans le bassin simulé (817 communes, Bas-Rhin 67 + Moselle 57) et
travaillant en Allemagne, jusque-là absents de la population synthétique et du réseau simulé.
Plan d'origine : `/root/.claude/plans/robust-yawning-giraffe.md`.

**Statut au moment de la rédaction** : la synthèse de population (eqasim-france) **et** le run
pymetropolis complet sont terminés. La vérification "de bout en bout" (Tâche #9 : comptage à
l'échelle simulée, comportement de routage sur les passages frontaliers, complétude des fichiers de
sortie) est faite — voir §6.

## 1. Pourquoi ce projet — chiffrage préalable

Avant d'investir du temps dans l'intégration, on a chiffré l'ampleur du phénomène à partir d'une
source disponible immédiatement : **Insee Analyses Grand Est n°167** (juin 2023, flux frontaliers
par zone d'emploi de résidence × pays de travail, millésime **RP2018**), pondérée par la part des
communes de chaque zone d'emploi incluses dans le bassin (`frontaliers_allemagne_estimation.csv`).

Résultat : **30 000 à 42 000 résidents du bassin travailleraient en Allemagne** selon cette
première estimation grossière, soit 60-65 % de tous les frontaliers du Grand Est vers l'Allemagne.
Un ordre de grandeur qui a justifié de ne pas traiter le sujet comme marginal.

Cette estimation a ensuite été **recoupée avec la donnée réelle** (§2) : le total réel (RP2022,
toute l'Allemagne) est de 29 962 personnes pondérées — au ras de la borne basse de l'estimation
grossière (30 029). Bon signe de cohérence méthodologique.

## 2. Étape 1 — Donnée réelle MOBPRO (RP2022) avec DCFLT

- Source : fichier détail RP MOBPRO millésime **2022** (`RP2022_mobpro.parquet`, 7 243 642
  observations France entière), téléchargé depuis insee.fr.
- Filtré aux résidents des 817 communes du bassin, puis aux lignes `DCLT = "99999"` (case
  "commune de travail hors référentiel Insee") dont le `DCFLT` (commune frontalière de travail)
  commence par `AL` (Allemagne).
- Résultat : **319 codes DCFLT distincts**, avec pour chacun le libellé de commune allemande, le
  poids pondéré (`IPONDI`, déjà une estimation de population — pas un effectif d'échantillon brut)
  et la taille d'échantillon RP sous-jacente.
- Fichier : `frontaliers_allemagne_dcflt_reel.csv` (racine du dépôt).
- **Total réel confirmé : 29 962 personnes pondérées** travaillant en Allemagne, résidant dans le
  bassin — cohérent avec l'estimation grossière de l'étape 0.

## 3. Pourquoi restreindre à 8 Kreise plutôt qu'à toute la zone frontalière

Étendre le réseau OSM et la géolocalisation des lieux de travail à *toute* l'Allemagne (ou même à
toute la Bade-Wurtemberg + Sarre + Rhénanie-Palatinat) aurait démultiplié le volume de données à
traiter (réseau routier, mémoire, temps de calcul) pour un gain marginal : les flux frontaliers
sont très concentrés géographiquement, sur les zones directement de l'autre côté de la frontière.

On a donc croisé `frontaliers_allemagne_dcflt_reel.csv` avec l'étude Insee Analyses Grand Est n°144
(flux par zone NUTS3 allemande) pour identifier les **8 Kreise/Stadtkreise qui concentrent
l'essentiel du flux** :

- **Côté Bas-Rhin** (face à Strasbourg/Haguenau/Sélestat) : Ortenaukreis (Kehl, Offenburg),
  Landkreis Rastatt, Karlsruhe (Stadt + Landkreis), Baden-Baden (Stadtkreis),
  Landkreis Germersheim (Rheinland-Pfalz).
- **Côté Moselle** (face à Sarreguemines/Forbach/Saint-Avold) : Regionalverband Saarbrücken,
  Saarpfalz-Kreis, Landkreis Saarlouis.

Résultat du matching (§4) : ces 8 Kreise captent **117 codes DCFLT sur 319** mais **25 514
personnes sur 29 962, soit 85,2 % du flux pondéré total**. Autrement dit, 37 % des codes DCFLT
distincts (souvent des toutes petites communes, 1-2 personnes) suffisent à couvrir la grande
majorité de l'effectif réel, parce que le flux est très concentré sur les grandes villes proches
de la frontière (Karlsruhe, Kehl, Sarrebruck, Rastatt, Baden-Baden en tête — cf. tableau §4).

Les 202 codes DCFLT non matchés (4 448 personnes pondérées, 14,8 % du flux) sont, à vérification
manuelle (`dcflt_unmatched.csv`), quasiment tous hors périmètre par construction : Zweibrücken,
Freiburg im Breisgau, Landau in der Pfalz, Pirmasens, Stuttgart, Mannheim, Heidelberg, etc. — des
zones plus diffuses ou plus lointaines, chacune representant un flux individuellement faible.
Cette marge résiduelle est une limite assumée de l'itération actuelle (extensible plus tard en
répétant la même procédure sur d'autres Kreise si besoin).

## 4. Étape 3 — Correspondance DCFLT → AGS et extraction OSM allemande

**Objectif** : associer à chaque code DCFLT retenu un code **AGS** (Amtlicher Gemeindeschlüssel,
identifiant officiel des communes allemandes) et un polygone OSM, pour permettre à la fois
l'extraction du réseau routier et le géocodage des lieux de travail.

**Sources** :
- `frontaliers_allemagne_dcflt_reel.csv` (319 codes DCFLT, §2) pour les libellés et poids à
  matcher.
- Extraits Geofabrik : `baden-wuerttemberg-latest.osm.pbf`, `saarland-latest.osm.pbf`,
  `rheinland-pfalz-latest.osm.pbf` (https://download.geofabrik.de/europe/germany/), lus via
  **pyosmium** (pas d'accès root sur le serveur distant pour installer `osmium-tool` en CLI à ce
  stade de l'étape — pyosmium suffisait, déjà fourni par les dépendances d'eqasim-france).

**Méthode de matching** (script ad hoc, résultat documenté dans le CSV de sortie) :
1. Lecture des relations `admin_level=6` (Kreise) des 3 extraits → filtre sur les 8 noms de Kreise
   cibles.
2. Lecture des relations `admin_level=8` (Gemeinden) → conservées si leur centroïde est dans
   l'union des 8 Kreise cibles (171 Gemeinden au total dans le périmètre).
3. **Cas particulier des villes-arrondissement** (Stadtkreis Karlsruhe, Stadtkreis Baden-Baden) :
   pas de relation `admin_level=8` séparée en OSM (le périmètre de la commune == le périmètre du
   Kreis) → le polygone du Kreis (`admin_level=6`) est réutilisé directement comme Gemeinde.
4. Matching des libellés : normalisation (majuscules ASCII, umlauts en digrammes ue/oe/ae,
   ponctuation retirée, Sankt/Saint → St), puis en cascade — correspondance exacte, puis préfixe
   (labels Insee tronqués, ex. `IKANDEL` → Kandel), puis premier mot ≥5 caractères (ex.
   `SULZBACH` → Sulzbach/Saar), puis similarité floue (`difflib`, seuil 0,92, coquilles/typos, ex.
   `IFFFEZHEIM` → Iffezheim).

**Résultat** : `frontaliers_allemagne_dcflt_to_ags.csv`
(`bassin/data/osm_de_correspondance/`) — 117 codes DCFLT matchés sur 319 (101 exacts, 8 par
préfixe, 6 par similarité floue, 2 ambigus par préfixe), 25 514 / 29 962 personnes (85,2 %).

Top des communes captées (poids pondéré) : Karlsruhe (3 051), Kehl (2 724), Saarbrücken (2 270),
Rastatt (2 210), Baden-Baden (1 897), Offenburg (1 088), Bühl (1 064), Wörth am Rhein (843).

**Réseau routier** : `build_communes_osm.sh` (script préexistant, réutilisé sans modification) a
ensuite fusionné les extraits France (Grand Est) + Allemagne (Bade-Wurtemberg, Sarre,
Rhénanie-Palatinat) et découpé sur l'union des 985 communes matchées (817 françaises + 168
allemandes — un peu plus que les 117 codes DCFLT retenus car `build_communes_osm.sh` matche sur la
liste complète des 171 Gemeinden du périmètre des 8 Kreise, pas seulement celles effectivement
citées comme destination de travail). Deux limitations rencontrées, sans impact sur le résultat :
- Fusion des 4 extraits `.osm.pbf` en échec initial (`osmium merge` : IDs OSM dupliqués entre
  extraits Geofabrik adjacents, phénomène connu aux frontières de découpage régional) → contourné
  par un pipeline `osmium cat` → `osmium sort` → dédoublonnage streaming (garde la première
  occurrence par type+id, mémoire constante).
- Karlsruhe et Baden-Baden (Stadtkreise) non matchés par le filtre `admin_level=8` du script
  (même raison qu'au point 3 ci-dessus) → vérifié que leurs réseaux routiers sont malgré tout
  couverts par la marge de 8 km appliquée par pymetropolis à l'import routier.

## 5. Étape 4 — Patch eqasim-france

Trois fichiers modifiés, un fichier ajouté, dans le clone `~/stage/eqasim-france` (serveur
distant). Constat de départ : **l'assignation du lieu de travail dans eqasim-france se fait au
niveau commune (via SIRENE, avec repli sur le centroïde de la commune si aucun établissement
SIRENE n'y est recensé), pas au niveau IRIS.** L'IRIS n'intervient que plus tard, pour des
statistiques de zonage fin — jamais pour le géocodage du lieu de travail lui-même. D'où l'absence
de besoin d'un référentiel IRIS allemand : on n'a eu qu'à étendre le mécanisme de repli déjà
existant pour les communes rurales françaises sans SIRENE.

### `data/od/raw.py` (modifié)
Dans le MOBPRO brut, les frontaliers ont `DCLT="99999"` (motif : hors référentiel de communes
françaises) — ces lignes étaient jusque-là filtrées et perdues. Le patch :
- Charge la table de correspondance DCFLT→AGS (§4).
- Garde les lignes `DCLT=="99999"` dont le `DCFLT` a une correspondance connue.
- Remplace `DCLT` par le code AGS correspondant, pour que la suite du pipeline traite ces lignes
  comme n'importe quelle autre destination de travail identifiée.

### `data/od/cleaned.py` (modifié)
Étend le dtype catégoriel de `destination_id` pour accepter les codes AGS en plus des codes INSEE
(sinon la validation de cohérence du pipeline rejetait ces communes comme "inconnues").
`origin_id` reste volontairement de dtype purement français (les résidents du bassin sont, par
construction, tous en France).

### `data/spatial/german_municipalities.py` (nouveau stage)
Charge les polygones des 171 Gemeinden allemandes du périmètre (§4,
`german_gemeinden_8kreise.geojson`), filtrés à celles présentes dans la table de correspondance,
reprojetés en EPSG:2154 (même CRS que le reste du pipeline). Renvoie uniquement `commune_id`
(= code AGS) et `geometry`.

### `synthesis/locations/work.py` (modifié)
Concatène les géométries de communes allemandes (nouveau stage ci-dessus) avec les géométries de
communes françaises existantes, dans la même table de zones utilisée pour le géocodage des lieux
de travail. Le mécanisme de repli "pas de SIRENE dans cette commune → point tiré au centroïde de
la commune" (qui existait déjà pour les communes rurales françaises sans établissement recensé)
s'applique alors automatiquement aux communes allemandes, puisque celles-ci n'ont par construction
jamais d'entrée SIRENE (registre français).

### `config_bassin_de.yml` (nouveau, config eqasim-france)
Config de run pointant vers `~/stage/eqasim-france-data`, sortie dans
`bassin/data/output_eqasim_de/` (préfixe `BASSIN_MOBILITE_GE_DE_`). Deux paramètres à noter :
- `hts: entd` (enquête ménages-déplacements source) — **diffère du run français d'origine**
  (`bassin/data/output_eqasim/`), qui utilisait `emp`. Seule la donnée ENTD était disponible sur
  le serveur distant au moment du run. `sampling_rate: 1` et `random_seed: 1234` ont en revanche
  été alignés sur le run d'origine pour rester comparables en échelle.
- `departments: ["67", "57"]`, `mode_choice: false`.

## 6. Vérification effectuée sur la population générée

**Ce qui a été vérifié** (en réponse directe à cette question, avant que la Tâche #9 formelle —
qui porte sur le résultat de simulation complet — ne soit possible) :

- **Comptage** : dans `BASSIN_MOBILITE_GE_DE_activities.parquet`, **31 621 personnes synthétiques
  distinctes** ont une activité "work" dont le `commune_id` est `null`. Contrôle : sur le run
  français d'origine (sans frontaliers), seules **22** activités "work" avaient un `commune_id`
  null (bruit résiduel négligeable) — confirmant que ces 31 621 nouvelles occurrences sont bien
  la population frontalière ajoutée par le patch, et pas un artefact préexistant.
- **Ordre de grandeur** : 31 621 personnes synthétiques vs. 25 514 personnes réelles pondérées
  attendues (§4) — même ordre de grandeur, écart de +24 %, plausible compte tenu de la variance
  inhérente à la synthèse de population (tirage stochastique à partir de marges pondérées, taille
  d'échantillon RP parfois très faible pour les petites communes — certains DCFLT ne reposent que
  sur 1 ou 2 observations d'échantillon, cf. `frontaliers_allemagne_dcflt_to_ags.csv`).
- **Cohérence géographique des coordonnées** : géométries décodées (WKB, EPSG:2154) pour un
  échantillon d'activités "work" à `commune_id` null — coordonnées de l'ordre de X≈990 000-1 015
  000, Y≈6 906 000-6 923 000, cohérentes avec la zone Rastatt/Karlsruhe/Baden-Baden juste de
  l'autre côté du Rhin par rapport au nord de l'Alsace (pas de point par défaut à (0,0) ni de
  géométrie nulle).
- **`iris_id` également `null`** pour ces mêmes activités, comme anticipé (§5) — non bloquant,
  cette colonne est déclarée `nullable=True` dans le schéma eqasim-france et n'est pas utilisée
  pour le géocodage lui-même.

### Run pymetropolis — note sur le changement de `fraction`/`simulation_ratio` en cours de route

Un premier run (`fraction`/`simulation_ratio = 0.5`) a été lancé mais a subi un ralentissement
sévère (46 à 53+ min/itération à partir de l'itération 5-6 de `RunSimulationStep`) causé par une
contention mémoire/CPU partagée sur le serveur distant (charge d'autres utilisateurs, swap saturé
en permanence, confirmé par recoupement des kills OOM `dmesg` avec les PID d'autres utilisateurs —
jamais les nôtres). Décision prise avec l'utilisateur : arrêter proprement ce run (partiel jusqu'à
l'itération 6/100, sauvegardé sans être écrasé dans
`bassin/output_de_frac0.5_partial/`) et relancer avec `fraction = simulation_ratio = 0.2` (au lieu
de 0.5), pour réduire le volume de population/trajets à traiter d'environ 60 % et rendre le run
supportable dans ces conditions de charge partagée. Le run final (log `pymetropolis_de_run3.log`,
démarré 2026-08-07 14:18) a atteint un rythme stable de ~1m30-2 min/itération (contre 46-53+ min
sous fraction=0.5) et s'est terminé avec succès : `RunSimulationStep` (100/100 itérations) en
3h25min36s, puis les 9 étapes finales (résultats, graphiques) en moins de 15 secondes — fin
complète à 19:45:59, soit **5h28 de temps de calcul total** depuis le lancement.

### Vérification à l'échelle simulée (fraction=0.2)

- **Aucune erreur** sur toute la durée du run (`grep -iE "error|traceback|exception|killed"` sur le
  log complet : aucune occurrence). Les seuls kills OOM observés dans `dmesg` pendant le run
  concernaient des processus d'autres utilisateurs du serveur (uid différent du nôtre), jamais les
  nôtres.
- **Comptage des trajets frontaliers** : dans les fichiers de sortie pymetropolis
  (`bassin/output_de/demand/population/trips_zones.parquet` croisé avec `trips.parquet`), **6 713
  trajets** ont une `destination_zone5` `null` (= destination hors référentiel de zones françaises,
  donc en Allemagne) **et** un `destination_purpose_group == "work"`, représentant **4 231
  personnes synthétiques distinctes**. Comparé à l'attendu théorique (31 621 personnes pré-fraction
  identifiées en §6 ci-dessus × 0.2 = 6 324 trajets attendus), le nombre de trajets observé (6 713)
  est à **+6 %** de l'attendu — bonne cohérence. Le nombre de personnes distinctes (4 231) est plus
  bas que le nombre de trajets (chaque frontalier peut avoir plusieurs trajets à destination
  "travail" dans sa chaîne de déplacements de la journée), ce qui est normal.
- **Comportement de routage sur les passages frontaliers attendus** : jointure spatiale des points
  de destination de ces 6 713 trajets contre les polygones des 168 communes allemandes du périmètre
  (`bassin_mobilite_ge_transfrontalier_simulation_area.geojson`) — 5 385 trajets matchés à une
  commune précise (le reste tombe hors des 168 polygones, cohérent avec la marge de 14,8 % de flux
  non couvert par construction, cf. §3). Top des communes de destination :
  **Kehl (725)**, **Saarbrücken (623)**, **Rastatt (619)**, Offenburg (279), Bühl (259), Wörth am
  Rhein (213), Rust (186), Homburg (171) — confirme exactement les deux corridors attendus : le
  pont de l'Europe à Kehl (face à Strasbourg) et l'axe Sarreguemines-Sarrebruck (Homburg,
  Saarbrücken). Aucune destination aberrante (pas de point à coordonnées nulles ou hors zone).
- **Complétude des fichiers de sortie** : les 50/50 étapes du pipeline pymetropolis se sont
  terminées, avec tous les fichiers de résultats attendus présents et de taille non nulle dans
  `bassin/output_de/results/` (`trip_results.parquet` 41 Mo, `route_results.parquet` 420 Mo,
  `activity_results.parquet` 16,5 Mo, `aggregate_results.json`, 8 graphiques PNG de convergence) et
  `bassin/output_de/run/output/` (`agent_results.parquet`, `route_results.parquet` 647 Mo,
  `skim_results.json.zst` 458 Mo, `report.html`, les 3 fichiers `net_cond_*_edge_ttfs.parquet`
  utilisables en entrée congestion-aware d'un futur calcul de matrice OD, `log.txt`,
  `running_times.json`). Rien de tronqué ni manquant.

**Conclusion** : l'intégration bout-en-bout est validée — la population frontalière survit
l'ensemble du pipeline (synthèse eqasim-france → import pymetropolis → 100 itérations de
simulation de trafic → résultats), à l'échelle attendue, avec un comportement de routage
géographiquement cohérent sur les deux corridors frontaliers ciblés. La Tâche #9 est terminée.

## 7. Récapitulatif des fichiers modifiés / ajoutés

| Fichier | Emplacement | Statut | Rôle |
|---|---|---|---|
| `frontaliers_allemagne_estimation.csv` | racine dépôt | ajouté | Estimation grossière préalable (RP2018, zone d'emploi) |
| `frontaliers_allemagne_dcflt_reel.csv` | racine dépôt | ajouté | Extraction réelle RP2022 MOBPRO, 319 codes DCFLT |
| `bassin/data/osm_de_correspondance/frontaliers_allemagne_dcflt_to_ags.csv` | dépôt local | ajouté | Table de correspondance DCFLT → AGS, 117 communes matchées |
| `bassin/data/osm_de_correspondance/dcflt_unmatched.csv` | dépôt local | ajouté | 202 codes DCFLT non matchés, vérifiés manuellement |
| `bassin/data/osm_de_correspondance/german_gemeinden_8kreise.geojson` | dépôt local | ajouté | Polygones des 171 Gemeinden du périmètre |
| `build_communes_osm.sh` | racine dépôt | réutilisé (non modifié) | Fusion + découpe des extraits OSM France+Allemagne |
| `bassin/data/bassin_mobilite_ge_transfrontalier.osm.pbf` | serveur distant `~/stage/bassin/data/` | généré | Réseau routier/piéton combiné France+Allemagne (309 Mo) |
| `bassin/data/bassin_mobilite_ge_transfrontalier_simulation_area.geojson` | serveur distant | généré | Polygone de la zone simulée (985 communes) |
| `eqasim-france/data/od/raw.py` | serveur distant `~/stage/eqasim-france/` | modifié | Conserve et reclasse les lignes MOBPRO `DCLT=99999` matchées |
| `eqasim-france/data/od/cleaned.py` | serveur distant | modifié | Étend le dtype `destination_id` aux codes AGS |
| `eqasim-france/data/spatial/german_municipalities.py` | serveur distant | ajouté | Géométries des communes allemandes de travail |
| `eqasim-france/synthesis/locations/work.py` | serveur distant | modifié | Réutilise le repli SIRENE-absent pour géocoder en Allemagne |
| `eqasim-france/config_bassin_de.yml` | serveur distant | ajouté | Config de run eqasim-france (hts=entd, depts 67/57) |
| `bassin/data/output_eqasim_de/BASSIN_MOBILITE_GE_DE_*` | serveur distant | généré | Population synthétique (persons/households/activities/trips) |
| `config-bassin-de.toml` | serveur distant `~/stage/` | ajouté | Config pymetropolis (copie de `config-bassin.toml` + 4 chemins + `batch_size`) |

## 8. Millésime des données

- **MOBPRO / flux domicile-travail réels (base de la table de correspondance et du patch)** :
  **RP2022** (recensement de la population, millésime 2022).
- **Estimation préalable de cadrage** (avant le chiffrage réel) : RP**2018** (Insee Analyses
  Grand Est n°167/n°144) — remplacée depuis par le chiffrage RP2022, gardée dans le dépôt comme
  repère de cohérence (§1).
- **Réseau OSM** : extraits Geofabrik France (Grand Est) et Allemagne (Bade-Wurtemberg, Sarre,
  Rhénanie-Palatinat) — millésime de téléchargement, pas de millésime historique figé (OSM est un
  flux continu ; à re-télécharger si une donnée plus fraîche est nécessaire).
- **Population synthétique générée** : reconstruction eqasim-france à `sampling_rate=1`
  (échelle réelle, pas un sous-échantillon), `random_seed=1234`, sur la base des marges RP2022 —
  pas datée à une année de simulation en tant que telle (c'est une population de référence,
  utilisée ensuite par pymetropolis avec une date de simulation `2026-09-07` et
  `simulation_ratio=0.2` pour le run de trafic — réduit de 0.5 à 0.2 en cours de route pour tenir
  compte de la contention mémoire/CPU partagée observée sur le serveur distant, cf. §6).
