# Thème 0 — Retours de correction

> Document de suivi, pas un nouvel énoncé. Résume la vérification faite sur ton rendu
> (exécution réelle des scripts, pas juste relecture). À consulter en attendant tes
> corrections d'Ex05/Ex07.

## Bugs confirmés (exécution)

### Ex05 — `pointe_soir` jamais assigné
`pl.when(pl.col("heure").is_between(16, 9))` : bornes inversées (16 > 9), condition
toujours fausse. Vérifié : 252 088 trajets partent entre 16h et 19h, **aucun** n'est
classé `pointe_soir` (tous tombent dans `hors_pointe`).
**Correction** : `is_between(16, 19)`.

### Ex07 — comparaison biaisée entre méthodes
`data_p` (polars eager) et `data_pd` (pandas) sont chargés **une seule fois hors de la
boucle** de mesure → seul le calcul est chronométré. En lazy, chaque `.collect()`
ré-exécute le plan **et relit le fichier**. En duckdb, `read_parquet()` est **dans la
requête SQL chronométrée**, donc relu à chaque itération.
Résultat : tu compares "calcul seul" (eager/pandas) à "lecture + calcul" (lazy/duckdb) —
pas équitable.
**Correction** : soit chronométrer la lecture + le calcul pour les 4 méthodes de façon
uniforme (recharger à chaque itération), soit exclure explicitement la lecture des 4
(charger/scanner une fois hors boucle, dont pour duckdb via une vue/relation déjà créée
au lieu de `read_parquet()` dans la requête répétée). Choisis une des deux logiques et
applique-la aux 4 méthodes, pas un mélange.
Pense aussi à confronter ton résultat corrigé à la source citée (danilchenko.dev) :
va-t-il dans le même sens ? Sinon, formule l'hypothèse (taille du fichier, format...).

## Autres points relevés (non bloquants pour la suite, à garder en tête)

| Exercice | Point |
|---|---|
| Ex00 | `try/except` inutile (imports hors du bloc) ; `requirements.txt` contient une ligne `-e file:...` locale, casse la reproductibilité |
| Ex01 | pourcentage de la population totale non calculé ; tranches encodées en entiers plutôt qu'en labels lisibles ; docstring de recherche vide |
| Ex02 | pas de mesure de temps (seulement mémoire) ; pas de tableau comparatif produit ; recherche sur `.explain()` absente |
| Ex03 | `trips.parquet` manquant du dossier de rendu (script non autonome) ; vérification de vacuité non automatisée ; recherche semi vs inner absente |
| Ex04 | contresens sur le classement des communes de destination : ranké par personne (`.over("person_id")`) au lieu d'un classement global des communes par nombre de trajets `work` reçus |
| Ex06 | le fichier geojson est déjà en `EPSG:2154` → écart mesuré = 0,0 %, la démonstration prévue (distorsion géographique vs projetée) n'est jamais visible, et le `raise GeometryError` n'est jamais déclenché |
| Ex08 | fichier nommé `inspect_parquest.py` (typo) au lieu de `inspect_parquet.py` ; `test_inspect_parquet.py` absent du rendu |

## Ce qui est acquis (pas à refaire)

Contexts/expressions, `.over()` pour les window functions, jointures avec `validate`,
lazy API de base, namespace `.str` sans regex — les fondamentaux polars sont là. Le
point commun des bugs trouvés (Ex04, Ex05, Ex06) : rien dans les scripts ne vérifiait
que le résultat obtenu correspondait à ce qui était attendu. C'est le réflexe à
prendre pour la suite, plus que la syntaxe polars elle-même.
