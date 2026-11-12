import geopandas as gpd
from pyrosm import OSM

if __name__ == '__main__':
    osm = OSM('bassin_mobilite_ge_transfrontalier.osm.pbf')
    routes = osm.get_network(network_type="driving")
    print(routes.head())
    print(routes.crs)
    ## l'utilisation de pyrosm est préférable pour récupérer les routes et
    ## gérer les osm files
    ## l'opiton -e ajoute d'autre information autre que le header
    ## (affichage par défaut), les éléments de la partie Data ne sont pas
    ## affiché généralement comme number of nodes, number of ways, ...
