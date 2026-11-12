# Exercices : reprendre la main sur les données du projet

Objectif : être capable, seul·e, de retrouver un fichier de données, l'inspecter, en
extraire des statistiques et produire un graphique — sur les inputs (MOBPRO, OSM, GTFS)
comme sur les outputs (population synthétique, résultats de simulation pymetropolis).
La recherche de données inclut aussi la recherche documentaire/web quand c'est demandé
explicitement dans un exercice — ce n'est pas juste "lire les fichiers du projet".

Format des exercices : inspiré des sujets 42 (objectif, contraintes bloquantes,
recherche imposée et sourcée, rendu attendu, pas de corrigé fourni, grille
d'auto-correction en fin de thème). Priorité donnée à **polars** plutôt que pandas
(déjà connu) pour tout ce qui est tabulaire ; `geopandas`/`shapely` pour le spatial.

Un fichier par thème, à faire dans l'ordre. On avance thème par thème — dire quand
passer au suivant.

- [Thème 0 — Prise en main des librairies](theme0_librairies.md)
- [Thème 1 — Retrouver et comprendre les données d'entrée](theme1_donnees_entree.md)
- [Thème 2 — Population synthétique (sorties eqasim-france)](theme2_population_synthetique.md)
- [Thème 3 — Résultats de simulation pymetropolis](theme3_resultats_simulation.md)
- [Thème 4 — Statistiques de vérification / cohérence](theme4_statistiques_verification.md)
- [Thème 5 — Cartographie et graphiques](theme5_cartographie.md)
- [Thème 6 — Mini-projet de synthèse](theme6_mini_projet.md)

> Statut (2026-08-11) : tous les thèmes (0 à 6) sont au format 42 étendu.

## Environnement de travail

La quasi-totalité des gros fichiers de données n'existe que sur LUTIStras
(`lutistras:~/stage`) — voir `~/stage/ORGANISATION.md`. Deux façons de
travailler :

- **Depuis le serveur distant** (recommandé, l'environnement Python est déjà prêt) :
  ```bash
  ssh lutistras
  cd ~/stage
  uv run --project pymetropolis python3        # REPL avec polars, geopandas, etc.
  # ou pour un notebook :
  uv run --project pymetropolis jupyter lab --no-browser --port 8888
  ```
- **En local**, pour des fichiers légers (CSV de `data_frontaliers/`, `config/`) :
  créer un venv avec `polars`, `geopandas`, `matplotlib` (`pymetropolis/.venv` a été
  supprimé localement pour libérer de la place — à recréer avec `uv sync` si besoin
  depuis `pymetropolis/`).

Astuce générale : commence toujours un exercice par `pl.scan_parquet(...).collect_schema()`
(ou l'équivalent geopandas) pour voir les colonnes disponibles avant de chercher à
répondre à la question — c'est ce qu'on a fait systématiquement pendant les
vérifications de la Tâche #9.

Rendu : chaque script d'un thème va dans `exercices/themeN/` (répertoire de travail
personnel, hors de ce dépôt de doc — à créer où tu veux, local ou sur LUTIStras).
