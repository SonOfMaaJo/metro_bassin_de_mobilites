# Thème 6 — Mini-projet de synthèse

> Voir [README](README.md) pour l'environnement de travail.

## Objectif

Choisir une question à laquelle `docs/methodologie_frontaliers_allemagne.md` (ou l'email équipe,
`docs/email_equipe_frontaliers_allemagne.md`) ne répond pas complètement, et la traiter de bout en
bout : recherche de la donnée → statistique → graphique → conclusion en 2-3 phrases. Contrairement
aux thèmes précédents, il n'y a pas de série de petits exercices indépendants — c'est un seul
mini-projet, à choisir parmi les 3 pistes ci-dessous (ou une question personnelle, à valider avant
de partir dessus).

## Contraintes générales

- Applique le réflexe des thèmes précédents : `data_path` → schéma → filtre/agrégation →
  vérification (ordre de grandeur plausible, comparaison à un chiffre déjà connu si possible) →
  graphique.
- Attention à l'échelle des fichiers utilisés : `bassin/output_de/` (résultats pymetropolis) est à
  `simulation_ratio = 0.2`, `bassin/data/output_eqasim_de/` (population synthétique) est à
  `sampling_rate: 1` (échelle réelle) — ne mélange pas les deux sans convertir.
- Pas de corrigé unique fourni : les "exemples de sortie attendue" ci-dessous sont des repères
  d'ordre de grandeur pour vérifier que tu es sur la bonne voie, pas la réponse à recopier.

---

## Piste 1 — Profil horaire des trajets frontaliers

**Question** : la répartition horaire des trajets frontaliers (heure de départ) colle-t-elle au
profil "pointe du matin / pointe du soir" attendu pour des trajets domicile-travail classiques ?

**Contraintes spécifiques** :
- Reprends la méthode de sélection des trajets frontaliers de l'Ex00 du Thème 4 (jointure
  `trips.parquet` × `trips_zones.parquet`, motif `work`, `destination_zone5` nulle), puis récupère
  `departure_time` depuis `trip_results.parquet` (Thème 3).
- Regroupe par heure entière (`departure_time.dt.total_seconds() // 3600`) — piège : certaines
  valeurs dépassent 24 (jusqu'à 26-27, cf. Thème 3 Ex04), ce sont des départs après minuit, à ne
  pas essayer de "corriger" modulo 24 (ça casserait la lecture chronologique d'une tournée qui
  déborde sur le petit matin).

**Recherche imposée sourcée** : cherche le profil horaire typique des trajets domicile-travail dans
une enquête mobilité française ou allemande (ex. ENTD/EMP côté français, ou une source de
statistique nationale allemande équivalente) — à quelle heure se situe habituellement le pic du
matin, et le trafic pendulaire présente-t-il généralement un rebond significatif en milieu de
journée (retour au domicile pour le déjeuner) ?

**Exemple de sortie attendue** (calcul réel, 6713 trajets frontaliers) :
```
heure  6 :  1135 trajets
heure  7 :  1519 trajets   <- pic du matin
heure  8 :   623 trajets
...
heure 12 :   584 trajets   <- rebond notable en milieu de journée
heure 13 :   513 trajets
...
heure 17 :    79 trajets   (pas de vrai "pic du soir" symétrique visible ici)
```
**Constat à documenter** : le pic du matin (6h-7h, ~2650 trajets) correspond bien au profil
attendu, mais il y a un **rebond net vers midi (12h-13h, ~1100 trajets)** — plus marqué qu'un simple
"bruit résiduel". Piste d'interprétation à développer dans ta conclusion : est-ce compatible avec
des tournées en plusieurs étapes (retour au domicile le midi puis re-départ), ou un artefact de la
manière dont les tournées sont construites dans la synthèse de population (cf. `tour_id` dans
`trips.parquet`, Thème 4) ? Pas de réponse imposée — c'est le cœur du mini-projet.

---

## Piste 2 — Temps de trajet Kehl vs Saarbrücken

**Question** : quel est le temps de trajet moyen simulé pour rejoindre Kehl (bassin
Strasbourgeois) vs Saarbrücken (bassin de Sarreguemines/Forbach), et cette différence
s'explique-t-elle par la distance, le réseau, ou autre chose ?

**Contraintes spécifiques** :
- Identifie les trajets par destination allemande via une jointure spatiale
  (`trip_destinations.geo.parquet` × `german_gemeinden_8kreise.geojson`, comme au Thème 5 Ex01),
  filtrée sur `name == "Kehl"` vs `name == "Saarbrücken"`.
- Récupère `travel_time` (pas `route_free_flow_travel_time`, qui ignore la congestion) depuis
  `trip_results.parquet` pour ces trajets.
- Piège : ne compare pas seulement la moyenne — regarde aussi le nombre de trajets dans chaque
  groupe (des groupes de taille très différente rendent une comparaison de moyenne moins solide).

**Recherche imposée sourcée** : cherche la distance orthodromique ou routière approximative
Strasbourg-Kehl vs Sarreguemines-Saarbrücken (une carte ou un service de calcul d'itinéraire
suffit comme source) — la différence de temps de trajet observée est-elle du même ordre que la
différence de distance, ou disproportionnée (ce qui indiquerait un effet réseau/congestion plutôt
que pure distance) ?

**Exemple de sortie attendue** (calcul réel) :
```
Kehl         : 725 trajets, temps de trajet moyen = 1635.6s (~27.3 min)
Saarbrücken  : 623 trajets, temps de trajet moyen = 1524.3s (~25.4 min)
```
Kehl est légèrement plus long en moyenne malgré une distance transfrontalière plus courte
(Strasbourg-Kehl ≈ pont de l'Europe, quelques km, contre Sarreguemines-Saarbrücken, une vingtaine
de km) — à toi d'investiguer si c'est un effet de congestion urbaine (Strasbourg/Kehl est une zone
plus dense) ou un artefact du réseau routier importé côté allemand.

---

## Piste 3 — Communes hors périmètre (les 14,8 % non couverts)

**Question** : parmi le flux frontalier non couvert par les 8 Kreise retenus dans cette première
itération, quelles sont les communes allemandes les plus citées dans le MOBPRO brut ? Ça donne une
piste concrète pour une itération future d'extension du périmètre.

**Contraintes spécifiques** :
- Le fichier `bassin/data/osm_de_correspondance/dcflt_unmatched.csv` contient déjà exactement cette
  liste (202 libellés DCFLT non matchés à un code AGS dans les 8 Kreise retenus), avec une colonne
  `ipondi_pondere` (poids IPONDI, donc un ordre de grandeur de population réelle, pas juste un
  nombre de lignes d'échantillon) — pars de ce fichier plutôt que de refaire le matching depuis
  zéro.
- Piège : trie sur `ipondi_pondere` (poids réel), pas sur `nb_observations_echantillon` (taille de
  l'échantillon RP) — les deux ne donnent pas nécessairement le même classement si le taux de
  sondage varie par zone.

**Recherche imposée sourcée** : pour au moins les 2-3 premières communes de ta liste, vérifie sur
une carte dans quel Land/Kreis allemand elles se trouvent réellement, et pourquoi elles ne sont pas
dans les 8 Kreise retenus (trop au sud/nord de la zone frontalière ciblée ? cf. périmètre du
Thème 2).

**Exemple de sortie attendue** (calcul réel, fichier `dcflt_unmatched.csv`) :
```
ZWEIBRUECKEN              poids ≈ 669  (139 obs. échantillon)
FREIBURG IM BREISGAU      poids ≈ 318  (71 obs. échantillon)
LANDAU IN DER PFALZ       poids ≈ 313  (65 obs. échantillon)
PIRMASENS                 poids ≈ 286  (59 obs. échantillon)
BAD BERGZABERN            poids ≈ 174  (35 obs. échantillon)

poids total non couvert (202 libellés) ≈ 4448
```
Remarque que Zweibrücken et Pirmasens sont juste au nord/nord-ouest de Saarpfalz-Kreis (déjà
couvert) — ce sont des candidats naturels pour une extension de périmètre à moindre effort par
rapport à Freiburg im Breisgau, nettement plus au sud.

---

## Rendu

`exercices/theme6/` : un script (ou notebook) par piste choisie, un PNG si un graphique est
pertinent pour la piste, et un fichier `conclusion.md` de 2-3 phrases par piste traitée — la
qualité attendue ici est la clarté de la conclusion, pas le volume de code.

## Grille d'auto-correction — Thème 6

- [ ] La question traitée est énoncée clairement en une phrase avant tout code.
- [ ] Le calcul part bien des fichiers sources indiqués (pas de chiffre recopié depuis ce document).
- [ ] Un ordre de grandeur de vérification a été fait (comparaison à un chiffre déjà établi dans un
      thème précédent, ou à une source externe pour la Piste 2/3).
- [ ] La conclusion (2-3 phrases) répond à la question posée, y compris si la réponse est "les
      données ne permettent pas de trancher" — ce n'est pas un échec, c'est une conclusion valide
      si elle est justifiée.
- [ ] Un graphique appuie la conclusion (pas juste un tableau de chiffres) quand c'est pertinent
      pour la piste choisie.
