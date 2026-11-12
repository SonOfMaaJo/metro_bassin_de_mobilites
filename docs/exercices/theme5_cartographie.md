# Thème 5 — Cartographie et graphiques

> Voir [README](README.md) pour l'environnement de travail.

> Ce thème réutilise principalement la sortie eqasim-france complète (`bassin/data/output_eqasim_de/`,
> `sampling_rate: 1`, comme au Thème 2) plutôt que les résultats pymetropolis sous-échantillonnés —
> pour des cartes, on veut la population réelle complète, pas 20 % de celle-ci. Vérifie bien de
> quel dossier tu pars pour chaque exercice.

## Ex00 — Carte simple de la zone de simulation

**Objectif** : produire une carte des 985 communes de la zone simulée, en distinguant visuellement
la partie française de la partie allemande.

**Contraintes** :
- Fichier : `bassin/data/bassin_mobilite_ge_transfrontalier_simulation_area.geojson` (985 communes :
  colonnes `insee`, `name`, `geometry`).
- Reprojette en `EPSG:2154` avant de tracer (`gdf.to_crs(...)`) — en `EPSG:4326` (degrés), la
  France et l'Allemagne s'affichent déformées (l'axe X/Y n'a pas la même échelle en mètres).
- Piège : le code INSEE ne suffit pas à distinguer FR/DE de manière fiable par simple préfixe
  numérique — utilise plutôt la longueur de la chaîne (`insee.str.len() == 8` pour les codes AGS
  allemands à 8 chiffres, vs 5 chiffres pour les codes INSEE français, cf. Thème 2 Ex04).

**Recherche imposée sourcée** : aucune (réutilisation directe d'un résultat déjà produit et validé
dans ce projet — l'image `zone_bassin_ge_frontaliers.png` existe déjà, à ne consulter qu'*après*
avoir produit la tienne, pour comparer).

**Exemple de sortie attendue** (chiffres réels) :
```
985 communes au total
817 communes françaises (Bas-Rhin: 67, Moselle: 57)
168 communes allemandes (8 Kreise)
```

**Rendu** : `exercices/theme5/ex00_carte_zone.py` produisant un PNG avec légende (2 couleurs, 2
effectifs).

---

## Ex01 — Desire lines des trajets frontaliers

**Objectif** : visualiser, sous forme de segments (pas de vrais itinéraires routiers), les flux
domicile-travail entre communes de résidence françaises et communes de travail allemandes.

**Contraintes** :
- Il faut croiser 3 informations qui ne sont dans aucun fichier unique : (1) la commune de
  résidence (`commune_id` sur l'activité `purpose == "home"` de `..._activities.parquet`), (2) la
  commune allemande de travail (obtenue par jointure spatiale comme au Thème 2 Ex04 — l'activité de
  travail correspondante a un `commune_id` nul dans le fichier non-géométrique), (3) le nombre de
  personnes par couple origine-destination.
- Piège : une jointure spatiale sur *toutes* les activités serait beaucoup plus lente que
  nécessaire — restreins d'abord aux activités `purpose == "work"` avec `commune_id` nul, comme au
  Thème 2, avant de faire le `gpd.sjoin`.
- Trace un `shapely.geometry.LineString` entre le centroïde de la commune de résidence et le
  centroïde de la commune allemande — pas l'inverse, et pas de itinéraire routier réel (ce n'est pas
  l'objet de cet exercice, contrairement au Thème 3 Ex02).
- Fais varier l'épaisseur du trait (`linewidth`) proportionnellement au nombre de personnes sur
  chaque couple origine-destination, sinon la carte n'apporte rien de plus qu'un nuage de points.

**Recherche imposée sourcée** : cherche ce qu'est une carte de type "desire lines" /
"flow map" en cartographie des transports (origine : un manuel ou une ressource de cartographie
thématique/géovisualisation) — en particulier pourquoi ce type de carte représente un flux
agrégé et non un itinéraire réel, et quelles précautions de lisibilité (superposition de lignes,
échelle d'épaisseur) sont habituellement recommandées.

**Exemple de sortie attendue** (couples origine-destination réels, triés par effectif) :
```
57660 (residence) -> Saarbrücken : 856 personnes
Strasbourg        -> Kehl        : 816 personnes
57227 (residence) -> Saarbrücken : 770 personnes
Sarreguemines     -> Saarbrücken : 595 personnes
57659 (residence) -> Saarbrücken : 425 personnes
```
(certains codes INSEE de résidence n'ont pas de nom affiché — normal, voir le piège de l'Ex02
ci-dessous, ça n'empêche pas de tracer la ligne à partir du code seul.)

**Rendu** : `exercices/theme5/ex01_desire_lines.py` produisant un PNG (fond de carte des 985
communes en gris clair + segments par-dessus, épaisseur proportionnelle au flux).

---

## Ex02 — Choroplèthe des frontaliers par commune de résidence

**Objectif** : produire une carte choroplèthe (couleur = intensité d'une variable par polygone) du
nombre de résidents travaillant en Allemagne, par commune de résidence.

**Contraintes bloquantes** :
- **Piège réel et non anecdotique** : en jointant les `commune_id` de résidence (venant de la
  population synthétique) aux `insee` du fichier
  `bassin_mobilite_ge_transfrontalier_simulation_area.geojson`, **149 communes de résidence sur 570
  concernées ne trouvent pas de correspondance géométrique** (un `left join` classique laisserait
  ces lignes avec une géométrie nulle, invisibles sur la carte silencieusement). Ne fais pas
  disparaître ces communes sans le signaler : affiche explicitement combien de communes (et
  combien de personnes) sont perdues par ce mismatch avant de tracer la carte.
- `gdf.plot(column="n_frontaliers", legend=True)` suffit pour le choroplèthe une fois la jointure
  propre faite — pas besoin de bins manuels pour une première version.
- Compare avec une échelle de couleur linéaire d'abord ; si la carte est illisible (une poignée de
  communes avec des valeurs très supérieures aux autres, ex. Strasbourg), documente ce que tu
  observes plutôt que de changer d'échelle sans le dire.

**Recherche imposée sourcée** : cherche pourquoi deux référentiels de codes commune INSEE
(différentes années/vintages du Code Officiel Géographique, ou geéométrie vs recensement) peuvent
diverger sur certaines communes (fusions de communes, communes nouvelles, changements de code) —
une explication officielle Insee ou IGN sur le Code Officiel Géographique (COG) suffit comme
source.

**Exemple de sortie attendue** (calcul réel, sur 31 613 frontaliers identifiés) :
```
top 5 communes de résidence (par nb de frontaliers travaillant en Allemagne) :
Strasbourg      : 1777
57227 (?)       : 1149
57660 (?)       : 1112
Sarreguemines   :  990
57537 (?)       :  741

570 communes de résidence concernées au total
149 / 570 communes sans correspondance dans le geojson de la zone (~26%) — à documenter, pas à
masquer silencieusement.
```

**Rendu** : `exercices/theme5/ex02_choroplethe.py` produisant un PNG + une ligne de log explicite
indiquant le nombre de communes et de personnes exclues de la carte faute de géométrie.

---

## Ex03 — Bonus (optionnel) : version interactive avec plotly

**Objectif** : reproduire l'Ex02 ou l'Ex01 avec `plotly` plutôt que `matplotlib`, pour bénéficier
du zoom/hover — utile quand une carte statique devient illisible avec beaucoup de communes/segments
superposés (cf. piège de lisibilité de l'Ex01).

**Contraintes** :
- `plotly.express.choropleth_mapbox` ou `plotly.express.scatter_mapbox` conviennent ; il faut
  d'abord convertir la géométrie en `EPSG:4326` (plotly/mapbox attendent des degrés, pas des
  mètres — piège inverse de l'Ex00).
- Pas de clé API nécessaire pour un fond de carte basique (`mapbox_style="carto-positron"` ou
  équivalent open, sans token).

**Recherche imposée sourcée** : aucune de plus — cet exercice est une transposition technique des
précédents, pas une nouvelle question de fond.

**Rendu** : `exercices/theme5/ex03_plotly_interactif.py` (ou `.html` exporté via `fig.write_html`).

---

## Ex04 — Reproduire un graphique déjà généré par pymetropolis

**Objectif** : vérifier que tu comprends exactement ce qu'un graphique déjà produit représente, en
le reproduisant toi-même à partir des données brutes.

**Contraintes** :
- Choisis un PNG dans `bassin/output_de/results/graphs/` (par exemple
  `trip_mode_shares.png` — directement reproductible avec les chiffres du Thème 3 Ex00 — ou
  `trip_departure_time_distribution.png`, qui nécessite de regrouper `trip_results.parquet` par
  tranche horaire de `departure_time`).
- Ne vise pas un rendu graphique identique au pixel près (couleurs, police) — vise la même
  **information** (mêmes catégories, mêmes proportions/valeurs).
- Piège : `departure_time` dans `trip_results.parquet` est un `Duration`, pas une heure du jour —
  il faut le convertir avant de faire un histogramme par heure (`.dt.total_seconds() // 3600`).

**Recherche imposée sourcée** : aucune — l'exercice consiste à lire le PNG source lui-même comme
référence, pas à chercher une documentation externe.

**Rendu** : `exercices/theme5/ex04_reproduction_graphe.py` + le PNG produit, avec en commentaire le
nom du PNG pymetropolis original reproduit et 1-2 phrases sur les écarts éventuels constatés.

---

## Grille d'auto-correction — Thème 5

- [ ] Ex00 : carte reprojetée en EPSG:2154, distinction FR/DE par longueur de code (pas par
      préfixe), légende avec les bons effectifs (817/168).
- [ ] Ex01 : jointure spatiale restreinte aux activités work à commune_id nulle avant le
      `gpd.sjoin` (pas sur toute la table), lignes tracées résidence → commune allemande (bon sens),
      épaisseur/couleur proportionnelle au flux (pas uniforme).
- [ ] Ex02 : mismatch de 149/570 communes explicitement détecté et documenté (pas de perte
      silencieuse de données), carte produite malgré tout sur les communes matchées.
- [ ] Ex03 (si fait) : carte interactive fonctionnelle, CRS en degrés pour plotly/mapbox.
- [ ] Ex04 : graphique reproduit avec la bonne conversion de type (`Duration` → heures), écarts
      avec l'original commentés plutôt qu'ignorés.
