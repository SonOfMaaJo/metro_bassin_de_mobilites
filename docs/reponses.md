A1- Normalement TripsCarFreeFlowTravelTimesStep serait éxécuté avant AllRoadDistancesStep mais si TripsCarFreeFlowTravelTimesStep as besoin de AllRoadDistancesStep il sera éxécuté avant (je pense que cela va dépendre de comment les fichiers inputs de TripsCarFreeFlowTimesStep sont générés).

A2- concernant le zones puisque cela prend en entré un geodataframe, on sait que cette colonne geometry est déjà présente dans le DataFrame
maintenant quand il déclare la les colonnes dans schema, on a pas besoin de précisé la colonne geometry parceque de toute les façons durant
la boucle qui drop les colonnes supplémentaires, on saute lorsqu'on tombe sur la colonne geometry donc à la fin cela reste toujours dans le dataFrame final.

A3- Je ne comprends pas très bien cette question.

A4- Chaine pour la classe FreeFlowLassoStep

- metro_calibration/road/free_flow_lasso.py - définition de la classe
- metro_calibration/road/__init__.py exportée dans ROAD_STEPS
- metro_calibration/__init__.py dans la liste finale des STEPS
- schema.py dans METRO_CALIBRATION_STEPS à la ligne 22
je crois que la chiane est tujours de longueur 4.

A5- je ne comprends pas cet exercices

A6- Je crois que c'est cohérent avec ce que la structure du code, comme un
ZonesFile a besoin d'un zone_id pour initialisation d'après le schéme dans zones/file.py,
il y'aura une erreur de GeoDataFrame invalid car cette colonne n'existe pas dans le
GeoDataFrame de départ. cela dit il faut la construire.

A7- on ne peut pas prendre directement le noeud retourné par sjoin_nearest car
il peut arriver qu'il n'est pas situé sur l'arc et donc ce qu'on fait c'est qu'on calcule
la plus petite distance entre la distance vers la source et la target et c'est ce
noeuds que l'on considére en gardant la distance vers le edge (distance entre le
noeuds et le projecté orthogonale vers l'arc). ainsi on saura dans quel sens de parcours sur l'arc on sera
et la distance a parcourir sur l'arc. Le triangle rectangle c'est bien celui dont
l'hypothénuse et constitue du noeud vers la le noeud de plus grande distance entre source et target,
ensuite les deux autres côté sont celles du projecté orthogonal avec le noeud et la source ou target obtenu
précédemment. je crois que c'est une approximation locales qu'on médoïde du réseau lui même.

A8- je ne comprends pas l'exercice.
