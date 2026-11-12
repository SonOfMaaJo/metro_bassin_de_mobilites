# Thème 1 — Retrouver et comprendre les données d'entrée

Voir [README](README.md) pour l'environnement de travail.

> Même format qu'au Thème 0 (objectif / contraintes / recherche imposée sourcée / rendu,
> priorité polars). **Nouveauté demandée après le retour sur le Thème 0** : chaque
> exercice inclut maintenant un exemple de sortie attendue (forme du résultat, pas la
> valeur à trouver toi-même quand elle fait partie de l'exercice — parfois la valeur est
> donnée quand elle sert de point de repère pour te dire que tu es sur la bonne piste,
> parfois seulement la forme du tableau).
>
> Rendu = un fichier `.py` par exercice dans `exercices/theme1/`, mêmes règles
> transversales qu'au Thème 0 (pas de chemin en dur → `argparse`, pas de `print` de debug
> oublié, recherche sourcée en commentaire).

## Ex00 — Retrouver le bon fichier (piège dictionnaire vs données)

**Objectif** : ne pas confondre un fichier de métadonnées avec le fichier de données
réel — piège classique avec les fichiers de recensement Insee.

**Contraintes** :
- Dans `data_frontaliers/`, tu trouveras `varmod_mobpro_2022.csv`. Charge-le avec
  polars et regarde ses colonnes (`COD_VAR`, `LIB_VAR`, `COD_MOD`, `LIB_MOD`...).
  **Ce n'est pas le fichier de données** — c'est le dictionnaire des variables et de
  leurs modalités (le "codebook"). Explique en commentaire, en une phrase, comment tu
  t'en rends compte rien qu'en regardant les colonnes.
- Le vrai fichier de données MOBPRO (une ligne = un individu du RP, avec ses variables
  de mobilité) est ailleurs dans l'arborescence de données du projet (`eqasim-france-data/`)
  — à toi de le retrouver (indice : cherche un fichier au format `.parquet` dont le nom
  contient `mobpro`).
- Une fois le bon fichier trouvé, charge son schéma **sans le charger en mémoire
  entièrement** (`pl.scan_parquet(...).collect_schema()`), et identifie les colonnes qui
  correspondent à : commune de résidence, commune du lieu de travail, commune
  frontalière du lieu de travail, poids statistique de l'individu dans l'échantillon.

**Exemple de sortie attendue** (noms de colonnes exacts, à toi de les retrouver dans le
vrai fichier) :
```
Schema({'COMMUNE': Categorical, 'ARM': Categorical, 'DCFLT': Categorical,
        'DCLT': Categorical, 'AGEREVQ': Categorical, ..., 'IPONDI': Float64, ...})
colonne résidence      -> COMMUNE
colonne lieu de travail -> DCLT
colonne frontalier      -> DCFLT
colonne poids           -> IPONDI
```

**Recherche imposée** : trouve dans la documentation Insee du recensement (RP, fichier
détail "mobilités professionnelles" / MOBPRO) la définition officielle de `DCLT` et de
`DCFLT` — en particulier ce que signifie la valeur `99999` pour `DCLT`. Cite la source
(document Insee, pas une reformulation d'IA).

**Rendu** : `exercices/theme1/ex00_localiser_mobpro.py`.

---

## Ex01 — Filtrer les frontaliers par département de résidence

**Objectif** : passer du fichier national au périmètre du bassin, avec une vraie
vérification de cohérence — pas juste "ça a l'air bon".

**Contraintes** :
- Sur le fichier de données trouvé en Ex00, filtre les lignes où `DCLT == "99999"`
  (travail hors de France).
- Extrais les 2 premiers caractères de `COMMUNE` (département de résidence) et compte le
  nombre de lignes pour les départements `67` et `57` séparément.
- **Ce nombre de lignes n'est pas un nombre de personnes réelles** — MOBPRO est un
  fichier d'échantillon, pas exhaustif. Garde cette remarque de côté, elle sert pour
  l'Ex04.

**Exemple de sortie attendue** (ordre de grandeur à retrouver, sur le millésime RP2022 —
si tu tombes sur un ordre de grandeur très différent, quelque chose ne va pas dans ton
filtre) :
```
shape: (2, 2)
┌──────┬───────┐
│ dept ┆ count │
│ str  ┆ u32   │
╞══════╪═══════╡
│ 67   ┆ ~5 700│
│ 57   ┆ ~23 200│
└──────┴───────┘
```

**Recherche imposée** : aucune nouvelle recherche ici — mais relis ta réponse à la
question de recherche de l'Ex00 sur `DCLT == 99999` et vérifie qu'elle est cohérente
avec ce que tu observes (rapport 57/67 très déséquilibré — as-tu une hypothèse sur
pourquoi, en lien avec la géographie du bassin ?).

**Rendu** : `exercices/theme1/ex01_filtre_departement.py`.

---

## Ex02 — Décoder les préfixes DCFLT (recherche internet obligatoire)

**Objectif** : `DCFLT` contient des codes du type `AL157`, `LU320`, `SU611`... —
comprendre ce que ces préfixes signifient, sans deviner.

**Contraintes** :
- Sur les lignes filtrées en Ex01 (dept 67 + 57, `DCLT == "99999"`), extrais les 2
  premiers caractères de `DCFLT` et compte les effectifs par préfixe.
- Pour chaque préfixe qui apparaît avec un effectif non négligeable (disons > 50
  lignes), donne le nom du pays correspondant dans un commentaire ou un dictionnaire
  Python — **sourcé**, pas deviné à l'œil (`AL` ressemble à "Allemagne" mais il faut le
  confirmer, pas le supposer).

**Exemple de sortie attendue** (forme du tableau ; les 2 premiers préfixes dominent
largement) :
```
shape: (6, 2)
┌──────┬───────┐
│ pref ┆ count │
│ str  ┆ u32   │
╞══════╪═══════╡
│ LU   ┆ ~18 900│
│ AL   ┆ ~9 500│
│ SU   ┆ ~290  │
│ ZZ   ┆ ~100  │
│ BE   ┆ ~75   │
│ MO   ┆ ~3    │
└──────┴───────┘
```

**Recherche imposée** : trouve la nomenclature officielle Insee qui liste les codes pays
utilisés dans les variables de type `DCFLT` (recherche sur le site insee.fr, ou dans la
documentation méthodologique du fichier détail MOBPRO — cherche "code officiel
géographique" ou "nomenclature des pays et territoires étrangers"). Cite l'URL ou le nom
exact du document trouvé, pas juste "j'ai déduit que...".

**Rendu** : `exercices/theme1/ex02_decoder_dcflt.py`.

---

## Ex03 — Frontaliers vers l'Allemagne : confrontation à une estimation externe

**Objectif** : ne jamais accepter un chiffre calculé sans le confronter à une source
indépendante — ici, un fichier déjà présent dans le projet qui vient d'une méthode et
d'un millésime différents.

**Contraintes** :
- Isole les lignes avec préfixe `DCFLT` = `AL` (Allemagne) parmi les frontaliers du
  bassin (dept 67 + 57).
- Charge `data_frontaliers/frontaliers_allemagne_estimation.csv` (attention, ce fichier
  a des lignes de commentaire `#` en tête — regarde comment les ignorer proprement avec
  `pl.read_csv(..., comment_prefix="#")` plutôt qu'un filtre a posteriori).
- Somme la colonne d'estimation par bassin de ce fichier, et compare à ton propre
  comptage de lignes `AL`.
- **Les deux chiffres ne doivent pas forcément être égaux.** Explique en commentaire
  au moins deux raisons possibles de l'écart (indice : millésimes de recensement
  différents, méthode de comptage — lignes brutes vs pondération par zone d'emploi,
  périmètre géographique — département administratif vs zone d'emploi Insee qui peut
  déborder du département).

**Exemple de sortie attendue** (forme, pas la valeur exacte — les deux chiffres seront
du même ordre de grandeur mais pas identiques) :
```
lignes DCFLT=AL (dept 67+57, RP2022, non pondéré)   : ~9 500
somme estimation bassin (fichier CSV, RP2018)        : ~60 000
```

**Recherche imposée** : ouvre `docs/methodologie_frontaliers_allemagne.md` (ou son PDF)
et retrouve la méthode utilisée pour produire `frontaliers_allemagne_estimation.csv` —
cite la source Insee mentionnée dans ce document (Insee Analyses Grand Est, numéro et
date).

**Rendu** : `exercices/theme1/ex03_comparaison_estimation.py`.

---

## Ex04 — Poids d'enquête : effectif brut vs effectif pondéré

**Objectif** : MOBPRO est un échantillon, pas un recensement exhaustif à ce niveau de
détail — chaque ligne représente plusieurs personnes réelles, avec un poids différent
d'une ligne à l'autre (contrairement au facteur d'échelle unique `simulation_ratio` vu
au Thème 0). C'est le cas où pondérer par observation devient nécessaire.

**Contraintes** :
- Sur les mêmes lignes qu'à l'Ex03 (`DCFLT` préfixe `AL`, dept 67+57), calcule :
  (a) le nombre de lignes (comptage brut), (b) la somme de la colonne de poids
  identifiée en Ex00 (`IPONDI`).
- Le rapport (b)/(a) doit être **différent** pour des sous-groupes différents (par
  exemple par département, ou par tranche d'âge si tu veux aller plus loin) —
  vérifie-le et affiche le poids moyen par département. Si tous les poids moyens sont
  identiques à la décimale près, quelque chose cloche dans ton calcul (les poids
  d'enquête ne sont jamais parfaitement uniformes).
- **Interdiction** : ne fais pas `df.height * poids_moyen_global` pour approximer (b) —
  calcule la vraie somme ligne à ligne (`pl.col("IPONDI").sum()`), c'est tout l'intérêt
  de l'exercice.

**Exemple de sortie attendue** (forme) :
```
lignes (brut)      : ~9 500
somme IPONDI (b)   : ~42 000-43 000
poids moyen global : ~4.5
poids moyen dept 67 : ...   (différent du poids moyen dept 57)
```

**Recherche imposée** : trouve dans la documentation Insee du RP la définition de la
variable `IPONDI` (poids de l'individu) et ce qu'elle représente statistiquement
(indice : lien avec le taux de sondage du "bulletin individuel" du recensement). Cite la
source.

**Rendu** : `exercices/theme1/ex04_poids_ipondi.py`.

---

## Ex05 — FR/DE dans la zone de simulation, sans regex fragile

**Objectif** : re-vérifier un chiffre déjà utilisé ailleurs dans le projet, avec la
bonne méthode — évite le piège de regex mal échappé déjà rencontré une fois sur ce
projet (Tâche #9).

**Contraintes** :
- Charge `bassin/data/bassin_mobilite_ge_transfrontalier_simulation_area.geojson`
  (colonne `insee`), avec geopandas puis conversion en polars pour la partie tabulaire
  (pas besoin de la géométrie ici).
- Compte les communes françaises et allemandes **par longueur de code**
  (`str.len_chars()`), pas par regex.
- Vérifie que le total (FR + DE) correspond bien au nombre de lignes du fichier
  `bassin/data/bassin_mobilite_insee_codes.txt` **plus** le nombre de communes
  allemandes ajoutées lors de l'extension transfrontalière (le fichier `.txt` ne contient
  que les 817 codes français d'origine — vérifie-le en le comptant directement,
  n'assume pas le chiffre).

**Exemple de sortie attendue** (forme) :
```
shape: (2, 2)
┌─────┬───────┐
│ len ┆ count │
│ u32 ┆ u32   │
╞═════╪═══════╡
│ 5   ┆ 817   │
│ 8   ┆ 168   │
└─────┴───────┘
lignes dans bassin_mobilite_insee_codes.txt : 817
```

**Recherche imposée** : aucune nouvelle recherche externe — mais documente en commentaire
pourquoi `str.len_chars()` est suffisant ici (indice : format des codes INSEE communes
françaises vs format AGS allemand — tu l'as déjà établi au Thème 0 Ex05, réutilise cette
justification plutôt que de la refaire de zéro).

**Rendu** : `exercices/theme1/ex05_fr_de_zone.py`.

---

## Ex06 — Inspecter le réseau OSM transfrontalier

**Objectif** : savoir vérifier rapidement le contenu d'un `.osm.pbf` sans avoir à le
charger entièrement en Python — utile chaque fois qu'on reçoit un nouvel extrait.

**Contraintes** :
- En ligne de commande (pas en Python) : `osmium fileinfo -e
  bassin/data/bassin_mobilite_ge_transfrontalier.osm.pbf` (le `-e` donne des stats
  étendues : nombre de nœuds/ways/relations, bounding box). Si `osmium` n'est pas
  disponible dans ton environnement, regarde comment `scripts/build_communes_osm.sh`
  gère son installation (fonction `install_osmium_tool`) et utilise le même gestionnaire
  de paquets.
- En Python avec geopandas, charge **uniquement les routes** de cet extrait, avec un
  filtre de couche pour ne pas tout charger (`gpd.read_file(..., layer=..., where=...)`
  si tu passes par `pyogrio`, ou explore `pyrosm` comme alternative — indique dans un
  commentaire laquelle des deux approches tu as choisie et pourquoi).
- Compare le nombre de nœuds obtenu par `osmium fileinfo` à un ordre de grandeur
  attendu pour une zone qui couvre le Bas-Rhin + Moselle + 8 Kreise allemands (quelques
  millions de nœuds, pas quelques milliers — sert à détecter un extrait tronqué).

**Exemple de sortie attendue** (format `osmium fileinfo -e`, valeurs à titre indicatif) :
```
File:
  Name: bassin_mobilite_ge_transfrontalier.osm.pbf
  Format: PBF
Header:
  Bounding boxes: ...
Data:
  Number of nodes: 4xxxxxxx
  Number of ways: 5xxxxx
  Number of relations: 6xxx
```

**Recherche imposée** : dans la doc officielle d'osmium-tool (`osmium fileinfo --help`
ou la doc en ligne osmcode.org), trouve ce que signifie exactement l'option `-e`/
`--extended` et cite un champ qu'elle ajoute que tu n'aurais pas sans elle.

**Rendu** : `exercices/theme1/ex06_inspect_osm.sh` (la commande osmium) +
`exercices/theme1/ex06_inspect_osm.py` (le chargement geopandas).

---

## Bonus — Ex07 : recherche documentaire pure

**Objectif** : s'entraîner à chercher une information méthodologique officielle sans
repartir d'un fichier du projet — utile le jour où une donnée manque et qu'il faut
comprendre une nomenclature avant de l'utiliser.

**Contraintes** : pas de code Python ici. Réponds, dans un fichier texte
`exercices/theme1/ex07_recherche.md`, avec pour chaque question la réponse **et** l'URL
ou la référence exacte du document officiel utilisé (Insee, pas un blog ou un résumé
d'IA) :
1. Quelle est la périodicité de collecte du recensement de la population française (RP)
   utilisé par MOBPRO, et sur combien d'années les données d'un "millésime" (ex.
   RP2022) sont-elles agrégées ?
2. Qu'est-ce qu'une "zone d'emploi" au sens Insee (celle utilisée dans
   `frontaliers_allemagne_estimation.csv`), et en quoi ça diffère d'un découpage
   administratif (département, EPCI) ?
3. Trouve la référence exacte (numéro, date) de l'étude Insee Analyses Grand Est citée
   dans `docs/methodologie_frontaliers_allemagne.md`, et vérifie que le lien/la
   référence est toujours valide (accessible) au moment où tu fais l'exercice.

**Rendu** : `exercices/theme1/ex07_recherche.md`.

---

## Grille d'auto-correction — Thème 1

- [ ] Ex00 : le fichier de données réel est bien distingué du dictionnaire de variables, schéma affiché sans chargement complet
- [ ] Ex01 : comptage par département cohérent avec l'exemple de sortie (ordre de grandeur)
- [ ] Ex02 : chaque préfixe important a un pays associé, sourcé (pas deviné)
- [ ] Ex03 : le `comment_prefix` du CSV est bien géré, l'écart entre les deux sources est expliqué avec au moins 2 raisons plausibles
- [ ] Ex04 : la somme pondérée est calculée ligne à ligne (pas une approximation par moyenne globale), le poids moyen diffère selon le sous-groupe
- [ ] Ex05 : comptage FR/DE par longueur de code, sans regex, total vérifié contre le fichier `.txt`
- [ ] Ex06 : commande osmium documentée et exécutée (ou tentative d'installation documentée si indisponible), chargement geopandas ciblé (pas un chargement complet du `.osm.pbf`)
- [ ] Chaque recherche imposée cite une source vérifiable (URL ou document officiel nommé précisément)
