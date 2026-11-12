# Thème 0 — Prise en main des librairies

Voir [README](README.md) pour l'environnement de travail (LUTIStras recommandé, gros
fichiers).

> **Format** : chaque exercice a un **objectif**, des **contraintes** (dont certaines
> sont volontairement bloquantes — c'est le but), une **recherche imposée**
> (documentation officielle ou source externe à trouver et **citer**, pas de contenu
> généré par un LLM comme unique source), et un **rendu attendu**. Aucun corrigé fourni.
> Rendu = un fichier `.py` par exercice dans `exercices/theme0/`, exécutable tel quel
> (`python3 exXX_nom.py`), avec en tête de fichier un commentaire de 2-3 lignes qui
> répond à la question de recherche et **cite sa source** (URL ou nom du document
> officiel).
>
> Règle transversale : pas de `print` de debug qui traîne dans le rendu final, pas de
> `except Exception: pass`, tout chemin de fichier en argument de script (`argparse`) —
> aucun chemin en dur dans le corps des fonctions.
>
> **Priorité polars.** Tu connais déjà pandas : ici l'objectif est de désapprendre les
> réflexes pandas (`.apply()`, `.iterrows()`, index implicite) et d'apprendre à penser en
> **expressions** et en **contexts** (le modèle mental de polars). pandas n'apparaît que
> dans un seul exercice (Ex07, benchmark), en option.

## Ex00 — Environnement reproductible

**Objectif** : être capable de reconstruire l'environnement Python du projet sur
n'importe quelle machine, sans improviser.

**Contraintes** :
- Ne réutilise pas tel quel `pymetropolis/.venv` — pars de zéro avec `uv venv` (ou
  `python3 -m venv`), et un fichier `requirements.txt` ou `pyproject.toml` que **tu
  écris toi-même**, avec les versions figées (`polars==...`, pas `polars`).
- Le venv doit contenir au minimum : `polars`, `geopandas`, `matplotlib`, `pyarrow`.
  `duckdb` en bonus (utile dès Ex07). `pandas` seulement si tu veux faire la variante
  bonus d'Ex07 (geopandas l'installe de toute façon comme dépendance transitive).
- Écris un script `check_env.py` qui importe chaque librairie et affiche sa version — le
  script doit se terminer avec un code de sortie non nul (`sys.exit(1)`) si une seule
  d'entre elles manque.

**Recherche imposée** : polars est construit sur **Apache Arrow** (format colonnaire en
mémoire). Trouve dans le "User Guide" officiel de polars (section concepts /
architecture) ou dans la doc Arrow ce que ça change concrètement pour les performances
d'agrégation par rapport à un DataFrame pandas classique (mémoire par ligne vs par
colonne). Résume en 3 lignes, avec la source.

**Rendu** : `exercices/theme0/ex00_check_env.py` + le fichier de dépendances figées.

---

## Ex01 — Expressions et contexts : le cœur de l'API polars

**Objectif** : maîtriser les 4 "contexts" de polars (`select`, `with_columns`, `filter`,
`group_by().agg()`) et l'enchaînement d'expressions `pl.col(...)`, sans jamais passer par
une boucle Python.

**Contraintes** :
- Fichier cible : `bassin/data/output_eqasim_de/BASSIN_MOBILITE_GE_DE_persons.parquet`.
- Crée une colonne catégorielle `tranche_age` (`0-17`, `18-24`, `25-34`, `35-49`, `50-64`,
  `65+`) à partir de la colonne d'âge, **uniquement** avec des expressions polars
  chaînées (`pl.when(...).then(...).when(...).then(...).otherwise(...)`).
- **Interdiction stricte** : `.map_elements()` et `.apply()` sont interdits dans cet
  exercice (et en général en polars, sauf dernier recours — c'est justement la
  recherche imposée ci-dessous).
- Produis un tableau croisé `tranche_age` × sexe (ou équivalent dispo dans le fichier),
  avec effectif et pourcentage de la population totale, trié par tranche d'âge.

**Recherche imposée** : cherche dans la doc polars (ou un article de blog officiel) la
justification de la mise en garde contre `.map_elements()`/`.apply()` — pourquoi c'est
un anti-pattern en polars (indice : perte de la vectorisation/parallélisation). Cite ta
source.

**Rendu** : `exercices/theme0/ex01_expressions.py`.

---

## Ex02 — Lazy API, query plan et streaming

**Objectif** : comprendre concrètement pourquoi `pl.scan_parquet` existe, pas juste en
théorie — et écrire un pipeline qui ne charge jamais tout en mémoire.

**Contraintes** :
- Fichier cible : `bassin/output_de/run/output/route_results.parquet` (~420M, sur
  LUTIStras).
- Version A (`--mode eager`) : `pl.read_parquet` puis filtre + agrégation. Mesure le pic
  de mémoire du process (`resource.getrusage(resource.RUSAGE_SELF).ru_maxrss`, ou
  `/usr/bin/time -v python3 script.py`).
- Version B (`--mode lazy`) : **exactement le même filtre + la même agrégation**, avec
  `pl.scan_parquet` + `.filter()` + `.group_by()` + `.collect()`.
  - **Interdiction** : dans la version lazy, `.collect()` ne peut apparaître qu'à la
    toute dernière ligne du pipeline.
- Bonus : ajoute un `--mode sink` qui écrit le résultat filtré directement dans un
  nouveau fichier avec `sink_parquet(...)`, sans jamais appeler `.collect()`.
- Produis un tableau texte comparant temps d'exécution et mémoire pic des modes testés.

**Recherche imposée** : lis la doc polars sur le "query plan" (`.explain()`). Colle en
commentaire le résultat de `lazyframe.explain()` sur ta requête B, et identifie
l'opération qui correspond à ton `.filter()` (le "predicate pushdown" — pourquoi
l'ordre dans lequel tu écris `.filter()` avant/après `.select()` n'a en général pas
d'impact sur le plan final).

**Rendu** : `exercices/theme0/ex02_lazy.py`, prend `--mode eager|lazy|sink` en argument.

---

## Ex03 — Joins avancés

**Objectif** : aller au-delà du `left join` par défaut, et apprendre à vérifier
l'intégrité d'une jointure au lieu de la supposer correcte.

**Contraintes** :
- Fichiers cibles (LUTIStras) : `bassin/output_de/demand/population/trips.parquet` et
  `.../trips_zones.parquet` (clé commune : `trip_id`) — les mêmes fichiers utilisés
  pendant la vérification de la Tâche #9.
- Fais un `inner` join, puis un `anti` join dans les deux sens (`trips` sans
  correspondance dans `trips_zones`, et inversement) — le résultat attendu est **vide**
  dans les deux sens (les deux fichiers doivent couvrir exactement les mêmes trip_id) ;
  si ce n'est pas vide, explique pourquoi avant de continuer.
- Utilise le paramètre de validation de jointure de polars (1:1, 1:m, m:1, m:m — cherche
  le nom exact du paramètre dans la doc) pour vérifier que `trip_id` est bien une clé
  unique dans les deux fichiers, sans le faire "à la main" avec un `group_by` + comptage.

**Recherche imposée** : trouve dans la doc polars la liste des `how=` possibles pour
`.join()` (au minimum `inner`, `left`, `full`, `semi`, `anti`), et note en 2 lignes la
différence entre un `semi` join et un `inner` join (un `semi` join ne duplique jamais de
lignes, contrairement à un `inner` — pourquoi, dans quel cas ça compte).

**Rendu** : `exercices/theme0/ex03_joins.py`.

---

## Ex04 — Group_by avancé et window functions

**Objectif** : calculer une statistique "par groupe" **sans** perdre le niveau de détail
ligne à ligne — le réflexe pandas serait `groupby().transform()` ou un merge après coup ;
en polars c'est `.over()`.

**Contraintes** :
- Fichier cible : `.../trips.parquet` (LUTIStras).
- Ajoute une colonne `nb_trajets_personne` = nombre total de trajets de la personne,
  calculée avec `pl.count().over("person_id")` (ou équivalent), **sans** faire de
  `group_by` suivi d'un `join` pour la recoller aux lignes d'origine.
- Calcule ensuite, pour chaque trajet, son rang de départ dans la journée de la personne
  (`pl.col("departure_time").rank().over("person_id")`).
- Sur `.../trips_zones.parquet` joint à `trips.parquet` (comme en Ex03), calcule le
  classement des communes de destination par nombre de trajets `work` reçus
  (`.over()` ou `group_by` classique — justifie ton choix en commentaire).

**Recherche imposée** : cherche la page "window functions" (ou "over") de la doc polars,
et note un cas d'usage où `.over()` est strictement nécessaire (impossible à faire
proprement avec un simple `group_by().agg()`).

**Rendu** : `exercices/theme0/ex04_window.py`.

---

## Ex05 — Namespaces `str` et temporel

**Objectif** : manipuler du texte et du temps sans quitter l'API polars (pas de
`.to_list()` puis boucle Python).

**Contraintes** :
- Partie texte : sur `bassin/data/bassin_mobilite_ge_transfrontalier_simulation_area.geojson`
  chargé en polars (colonne `insee` uniquement — pas besoin de geopandas ici), reproduis
  **proprement** la distinction FR (code à 5 caractères) / DE (code à 8 caractères) avec
  le namespace `.str` (`pl.col("insee").str.len_chars()`), **sans regex** — c'est
  exactement le bug qu'on a eu pendant la Tâche #9 (un regex mal échappé dans une
  commande shell imbriquée a donné un résultat faux) ; ici l'exercice est de montrer
  qu'une solution plus simple et plus robuste existait.
- Partie temporelle : sur `.../trips.parquet`, `departure_time` est un entier en
  secondes depuis minuit. Sans `.map_elements()`, crée une colonne `heure` (division
  entière par 3600) et une colonne `periode` (`pointe_matin` 6h-9h, `pointe_soir` 16h-19h,
  `hors_pointe` sinon) via `pl.when/then/otherwise`.
- Bonus : convertis `departure_time` en vrai type temporel polars (`pl.Duration` ou
  `pl.Time`, à toi de choisir lequel a du sens ici) et refais le découpage en périodes
  avec le namespace `.dt` plutôt qu'un calcul entier manuel.

**Recherche imposée** : dans la doc polars, trouve la page sur le namespace `.str` (ou
`.dt` si tu fais le bonus) et cite une méthode que tu n'as pas utilisée dans cet exercice
mais qui pourrait servir ailleurs dans le projet (ex : `str.contains`, `str.extract`,
`dt.hour`...).

**Rendu** : `exercices/theme0/ex05_str_dt.py`.

---

## Ex06 — CRS et projections, sans te tromper

**Objectif** : ne plus jamais calculer une distance ou une surface en `EPSG:4326`
(coordonnées géographiques, pas métriques) sans t'en rendre compte.

**Contraintes** :
- Charge `bassin/data/bassin_mobilite_ge_transfrontalier_simulation_area.geojson` avec
  `geopandas`.
- Calcule la surface totale de la zone de deux façons : (a) directement sur les
  géométries sans reprojection, (b) après `.to_crs("EPSG:2154")`. Affiche les deux
  résultats et l'écart en %.
- Le script doit lever une exception explicite (pas un warning silencieux) si on lui
  demande de calculer une distance/surface alors que le GeoDataFrame est encore en CRS
  géographique (`gdf.crs.is_geographic`) — écris toi-même cette vérification, n'utilise
  pas d'option cachée d'une lib qui le ferait à ta place.

**Recherche imposée** : trouve la documentation officielle (IGN ou EPSG.io) qui explique
ce qu'est le Lambert-93 (`EPSG:2154`) et pourquoi c'est la projection standard pour la
France métropolitaine (conforme ? équivalente ? sur quelle référence ?). Cite la source
et résume en 3 lignes max. En bonus, trouve pourquoi `geopandas` dépend de bibliothèques
C externes (GEOS/GDAL/PROJ) alors que `polars` n'a pas ce genre de dépendance système.

**Rendu** : `exercices/theme0/ex06_crs.py`.

---

## Ex07 — Benchmark rigoureux polars / duckdb (pandas en option)

**Objectif** : produire une comparaison de performance qui tient la route
méthodologiquement, pas juste "un run, un chrono".

**Contraintes** :
- Requête cible : sur `bassin/data/output_eqasim_de/BASSIN_MOBILITE_GE_DE_trips.geoparquet`,
  calcule le nombre de trajets par `following_purpose`, trié par ordre décroissant.
- Implémente la requête en polars **eager**, polars **lazy**, et **duckdb** (SQL direct
  sur le fichier parquet). pandas en 4e variante, en bonus seulement (tu le connais
  déjà — l'intérêt ici est de voir où il se situe, pas de le pratiquer).
- **Répète chaque mesure au moins 10 fois**, écarte le premier run (effet cache
  disque/OS), rapporte moyenne **et** écart-type — un seul chrono par méthode est
  refusé.
- Produis un graphique `matplotlib` (barres avec barres d'erreur, `yerr=` dans
  `plt.bar`) comparant les méthodes testées.

**Recherche imposée** : trouve un benchmark public (blog officiel polars, ou
h2oai/db-benchmark, ou une autre source citable) qui compare polars et duckdb sur des
opérations de type group-by. Ton résultat va dans le même sens ? Si non, formule une
hypothèse sur pourquoi (taille du fichier trop petite pour que le multi-threading paie,
format geoparquet vs parquet simple, etc.) — pas besoin de la vérifier, juste de la
formuler proprement.

**Rendu** : `exercices/theme0/ex07_benchmark.py` + `ex07_benchmark.png`.

---

## Ex08 — CLI d'inspection généraliste (100% polars)

**Objectif** : un outil réutilisable pour tous les thèmes suivants, pas un script
jetable — et l'occasion de mettre bout à bout tout ce qui précède.

**Contraintes** :
- Un seul script `inspect_parquet.py`, avec `argparse`, implémenté uniquement avec
  polars (aucun `import pandas`), qui prend : un chemin de fichier parquet/geoparquet,
  une colonne optionnelle, un mode (`--schema`, `--stats`, `--hist`).
  - `--schema` : affiche colonnes + types, sans charger les données (`scan_parquet` +
    `collect_schema()`, jamais de chargement complet pour ce mode).
  - `--stats` : affiche l'équivalent polars de `describe()` sur la colonne demandée.
  - `--hist` : sauvegarde un histogramme de la colonne demandée en PNG.
- Doit gérer proprement (message clair, `sys.exit(1)`, pas de traceback brut) : fichier
  inexistant, colonne inexistante, colonne non numérique demandée en `--hist`.
- Au moins 4 tests avec `pytest` (utilise un petit parquet de test généré dans le test,
  pas un fichier du projet — le test doit pouvoir tourner sans accès à LUTIStras).

**Recherche imposée** : regarde la doc `pytest` sur les fixtures (`tmp_path` en
particulier, pour créer un fichier temporaire dans un test) — explique en commentaire
pourquoi c'est préférable à écrire un fichier en dur dans `/tmp`.

**Rendu** : `exercices/theme0/inspect_parquet.py` + `exercices/theme0/test_inspect_parquet.py`.

---

## Bonus — Ex09 : packager proprement

Transforme `inspect_parquet.py` en petit module installable (`pyproject.toml`, point
d'entrée `console_scripts`), avec docstrings sur chaque fonction publique et type hints
partout (y compris les types polars comme `pl.DataFrame`/`pl.LazyFrame` dans les
signatures). Si `ruff` ou `mypy` sont disponibles, le code doit passer sans erreur
(`ruff check .`, `mypy .`) — sinon, justifie dans un commentaire ce qui bloquerait.

---

## Grille d'auto-correction — Thème 0

À cocher toi-même avant de dire que le thème est fini (esprit peer-eval 42, en solo
ici) :

- [ ] Ex00 : le script détecte bien une lib manquante (teste en désinstallant `duckdb`)
- [ ] Ex01 : aucun `.map_elements()`/`.apply()` dans le fichier, tableau croisé correct
- [ ] Ex02 : la version lazy tient dans une mémoire nettement inférieure à la version eager (mesuré, pas supposé)
- [ ] Ex03 : les deux `anti` joins sont bien vides (ou l'écart est expliqué), la validation de jointure est utilisée
- [ ] Ex04 : `nb_trajets_personne` est calculée sans perdre une seule ligne du fichier d'origine
- [ ] Ex05 : la distinction FR/DE fonctionne sans regex, testée sur au moins un cas piège (ex : Strasbourg)
- [ ] Ex06 : l'exception CRS se déclenche réellement si on retire volontairement le `.to_crs()`
- [ ] Ex07 : écart-type affiché, graphique avec barres d'erreur, source du benchmark externe citée
- [ ] Ex08 : les 3 cas d'erreur (fichier/colonne/type) sont testés, pas juste gérés "à l'œil", zéro `import pandas`
- [ ] Aucun chemin en dur, aucun `print` de debug oublié, chaque recherche imposée est sourcée
