# Thème 2 — Population synthétique (sorties eqasim-france)

Voir [README](README.md) pour l'environnement de travail.

> Même format qu'aux Thèmes 0 et 1 (objectif / contraintes / recherche imposée sourcée /
> rendu / exemple de sortie attendue, priorité polars, `geopandas` pour le spatial).
>
> **Contexte à connaître avant de commencer** : `bassin/data/output_eqasim_de/` (préfixe
> `BASSIN_MOBILITE_GE_DE_`) est le run avec frontaliers Allemagne intégrés ;
> `bassin/data/output_eqasim/` (préfixe `BASSIN_MOBILITE_GE_`, **sans** `_DE`) est
> l'ancien run France seule, gardé pour comparaison. Fais attention au nom de fichier —
> se tromper de préfixe est facile et donne des résultats qui se ressemblent.
>
> **Point important, différent du Thème 0** : ces fichiers eqasim sont générés avec
> `sampling_rate: 1` (population à l'échelle réelle, cf. `eqasim-france/config_bassin_de.yml`)
> — contrairement aux résultats de simulation pymetropolis (Thème 3) qui sont sous-échantillonnés
> par `simulation_ratio`. Ne divise ni ne multiplie rien ici, les effectifs comptés sont
> déjà les effectifs réels.
>
> Rendu = un fichier `.py` par exercice dans `exercices/theme2/`, mêmes règles
> transversales qu'aux thèmes précédents (pas de chemin en dur → `argparse`, pas de
> `print` de debug oublié, recherche sourcée en commentaire).

## Ex00 — Explorer les schémas avant de coder

**Objectif** : ne jamais écrire une ligne de traitement avant d'avoir vu le schéma réel
— surtout ici où plusieurs fichiers portent des noms proches (`.parquet` vs
`.geoparquet`, `GE_` vs `GE_DE_`).

**Contraintes** :
- Pour `BASSIN_MOBILITE_GE_DE_persons.parquet`, `..._households.parquet`,
  `..._activities.parquet` et `..._trips.parquet` : affiche le schéma de chacun avec
  `pl.scan_parquet(...).collect_schema()` (pas de chargement complet).
- Fais la même chose pour `..._activities.geoparquet` et `..._trips.geoparquet` — note
  en commentaire la différence de colonnes avec leurs équivalents `.parquet` (une seule
  colonne en plus, mais qui change tout pour l'Ex04).
- Identifie, dans `..._activities.parquet`, la colonne qui donne le type d'activité
  (travail, domicile, etc.) et celle qui donne la commune associée.

**Exemple de sortie attendue** :
```
persons.parquet     : Schema({'person_id': Int64, 'household_id': Int64, 'age': Int64, ...})
households.parquet  : Schema({'household_id': Int64, 'income': Float64, ...})
activities.parquet  : Schema({'person_id': Int64, ..., 'purpose': String,
                               'commune_id': String, ...})   # pas de géométrie
activities.geoparquet: idem + colonne 'geometry'
colonne type d'activité -> purpose
colonne commune         -> commune_id
```

**Recherche imposée** : aucune nouvelle recherche externe — mais relis la doc eqasim
(README du dépôt `eqasim-france` cloné sur LUTIStras, ou sa doc en ligne officielle) sur
la différence entre les stages `synthesis` (population) et `matsim` (simulation), pour
situer où se place ce que tu inspectes ici.

**Rendu** : `exercices/theme2/ex00_schemas.py`.

---

## Ex01 — Effet de l'intégration allemande sur la population

**Objectif** : comparer deux runs pour isoler ce qui a réellement changé — et être
capable d'expliquer un résultat qui, au premier abord, semble "ne rien montrer".

**Contraintes** :
- Sur les deux runs (`GE_DE_` et `GE_`), calcule : nombre total de personnes, nombre de
  ménages, taille moyenne des ménages (`persons / households`).
- **Tu vas trouver des chiffres identiques entre les deux runs.** Ce n'est pas un bug de
  ta part — explique en commentaire pourquoi, à ton avis, l'intégration des frontaliers
  n'a pas changé le nombre de résidents simulés (indice : à quelle étape du pipeline la
  population de *résidents* est-elle générée, par rapport à l'étape qui assigne les
  *lieux de travail* ? — relis `docs/email_equipe_frontaliers_allemagne.md` si tu l'as
  sous la main).
- Compare la taille moyenne des ménages obtenue à un ordre de grandeur national connu
  (recherche imposée ci-dessous).

**Exemple de sortie attendue** :
```
[GE_DE] persons=2 206 781  households=1 041 456  taille_moyenne=2.119
[GE]    persons=2 206 781  households=1 041 456  taille_moyenne=2.119
```

**Recherche imposée** : trouve sur insee.fr le chiffre national (ou Grand Est) de la
taille moyenne des ménages le plus récent disponible, et compare-le à ce que tu obtiens
ici — explique en une phrase si l'écart (s'il y en a un) te semble cohérent avec le
profil du bassin (zone plutôt urbaine/périurbaine).

**Rendu** : `exercices/theme2/ex01_comparaison_runs.py`.

---

## Ex02 — Là où l'intégration allemande se voit vraiment : les activités

**Objectif** : l'Ex01 vient de montrer que le mauvais indicateur (population totale) ne
bouge pas — cet exercice cherche le bon indicateur.

**Contraintes** :
- Sur `..._activities.parquet` des deux runs, filtre `purpose == "work"` et compte : (a)
  le nombre total d'activités work, (b) celles où `commune_id` est nul.
- Le run `GE` (France seule) doit avoir un nombre d'activités work **strictement
  inférieur** au run `GE_DE`, et un nombre de `commune_id` nuls proche de zéro (quelques
  unités seulement — du bruit de fond préexistant, pas lié aux frontaliers). Si tu
  trouves l'inverse ou des ordres de grandeur très différents, relis ton filtre.
- Calcule la différence brute entre les deux runs pour (a) — c'est le vrai nombre
  d'activités work ajoutées par l'intégration allemande.

**Exemple de sortie attendue** :
```
[GE_DE] activites work total=1 331 284   commune_id nul=50 887
[GE]    activites work total=1 243 392   commune_id nul=22
activites work ajoutees par l'integration : 87 892
```

**Recherche imposée** : ouvre `docs/methodologie_frontaliers_allemagne.md` et retrouve
le chiffre qu'il documente pour ce même indicateur (nombre d'activités/personnes
frontalières identifiées). Compare-le au tien et explique l'écart s'il y en a un (indice
: ce document parle-t-il du niveau eqasim, ou du niveau simulation pymetropolis après
application de `simulation_ratio` ? — relis l'encadré en tête de ce thème).

**Rendu** : `exercices/theme2/ex02_activites_work.py`.

---

## Ex03 — Distribution du nombre de trajets par personne

**Objectif** : vérifier la plausibilité d'une distribution simulée par rapport à un
ordre de grandeur connu de mobilité quotidienne — pas juste calculer une moyenne et
passer à autre chose.

**Contraintes** :
- Sur `..._trips.parquet` (le `.parquet` simple suffit ici, pas besoin de géométrie),
  groupe par `person_id` et compte le nombre de trajets, puis utilise `.describe()`
  (moyenne, médiane, quartiles, min/max).
- Le nombre de lignes de `person_id` distincts obtenus ici doit être **inférieur** au
  nombre total de personnes de l'Ex01 — explique en commentaire pourquoi tout le monde
  n'a pas forcément de trajet (indice : personnes sans aucune activité hors domicile ce
  jour-là dans la simulation).

**Exemple de sortie attendue** :
```
shape: (9, 2)
┌────────────┬──────────┐
│ statistic  ┆ value    │
╞════════════╪══════════╡
│ count      ┆ 1 793 624│
│ mean       ┆ 4.09     │
│ std        ┆ 2.28     │
│ min        ┆ 1.0      │
│ 25%        ┆ 2.0      │
│ 50%        ┆ 4.0      │
│ 75%        ┆ 6.0      │
│ max        ┆ 14.0     │
└────────────┴──────────┘
```

**Recherche imposée** : trouve un chiffre de référence Insee ou Enquête Nationale
Transports et Déplacements (ENTD/EMP) sur le nombre moyen de déplacements quotidiens par
personne en France, et compare-le à la moyenne obtenue ici — explique une raison
plausible d'écart si tu en observes un (indice : la moyenne obtenue ici ne compte que
les personnes avec au moins un trajet, contrairement à une moyenne "par habitant" qui
inclurait les personnes totalement immobiles ce jour-là).

**Rendu** : `exercices/theme2/ex03_trajets_par_personne.py`.

---

## Ex04 — Identifier la commune allemande de destination (jointure spatiale)

**Objectif** : reproduire, à ta façon, la vérification géographique faite pour la
Tâche #9 du projet — `commune_id` est nul pour les activités work en Allemagne, donc il
faut passer par la géométrie pour savoir *quelle* commune allemande précisément.

**Contraintes** :
- Cette fois tu as besoin de la géométrie : charge `..._activities.geoparquet` (pas la
  version `.parquet`, cf. Ex00) avec geopandas, filtre `purpose == "work"` et
  `commune_id` nul.
- Charge `eqasim-france-data/german/german_gemeinden_8kreise.geojson` (polygones des
  communes allemandes), reprojette-le dans le même CRS que les activités.
- Fais une jointure spatiale (`gpd.sjoin`, `predicate="within"`) entre les points
  d'activité et les polygones de communes, puis produis un top 10 des communes
  allemandes de destination par nombre d'activités.
- Quelques points ne tomberont dans aucun polygone (bord de commune, imprécision
  géométrique) — compte-les séparément, ne les fais pas disparaître silencieusement
  d'un `inner join`.

**Exemple de sortie attendue** :
```
name
Saarbrücken       12 100
Karlsruhe          4 525
Kehl               3 646
Rastatt            3 073
Saarlouis          2 714
Baden-Baden        2 375
Bühl               1 484
Offenburg          1 316
Homburg            1 255
Wörth am Rhein     1 146
Name: count, dtype: int64
non matches (hors polygone Gemeinde) : 11
```

**Recherche imposée** : sur destatis.de ou Wikipedia (version allemande), trouve la
structure du code AGS (Amtlicher Gemeindeschlüssel, 8 chiffres) — quelles positions du
code correspondent au Land, au Kreis, à la Gemeinde. Vérifie que 2-3 codes AGS de ton
top 10 (consultables dans `german_gemeinden_8kreise.geojson`, colonne `ags`) sont bien
cohérents avec cette structure (même préfixe de Land pour les communes du
Bade-Wurtemberg, préfixe différent pour celles de Sarre).

**Rendu** : `exercices/theme2/ex04_jointure_spatiale.py`.

---

## Bonus — Ex05 : où sont passés les "faux" lieux de travail ?

**Objectif** : comprendre un mécanisme du pipeline eqasim-france que tu as vu mentionné
dans le mail équipe (`docs/email_equipe_frontaliers_allemagne.md`), sans juste le croire
sur parole.

**Contraintes** :
- Dans `..._activities.parquet` (run `GE_DE`), les activités work en Allemagne
  partagent-elles vraiment le même point géographique par commune (le centroïde,
  cf. mail équipe) ? Vérifie-le : sur les activités work d'une même commune allemande
  (utilise le résultat de l'Ex04 pour associer chaque activité à sa commune), compte le
  nombre de géométries **distinctes** (`geometry.unique()` ou équivalent) par commune.
  Tu dois trouver **une seule géométrie distincte par commune**, quel que soit le nombre
  d'activités qui y sont rattachées.

**Exemple de sortie attendue** :
```
commune          n_activites  n_geometries_distinctes
Saarbrücken      12100        1
Karlsruhe        4525         1
Kehl             3646         1
```

**Rendu** : `exercices/theme2/ex05_verification_centroide.py`.

---

## Grille d'auto-correction — Thème 2

- [ ] Ex00 : schémas affichés sans chargement complet, différence `.parquet`/`.geoparquet` identifiée
- [ ] Ex01 : chiffres identiques entre les deux runs correctement expliqués (pas traité comme un bug)
- [ ] Ex02 : bon indicateur isolé (activités work, pas population totale), différence brute calculée
- [ ] Ex03 : `.describe()` utilisé, écart avec la référence externe expliqué
- [ ] Ex04 : jointure spatiale sur la bonne version du fichier (`.geoparquet`), non-matches comptés séparément (pas d'inner join silencieux)
- [ ] Chaque recherche imposée cite une source vérifiable (URL ou document officiel nommé précisément)
- [ ] Bonus Ex05 fait si le temps le permet
