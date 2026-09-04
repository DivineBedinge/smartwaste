# Cartographie opérationnelle

Le module commun utilise Leaflet déjà présent dans les interfaces et expose une abstraction `MapProvider`. Les données viennent exclusivement de `/api/v1/geo/*`, avec authentification, limites et emprises contrôlées. Les citoyens ne reçoivent que leurs ressources; les ramasseurs ne reçoivent l’adresse exacte qu’après acceptation et pendant un état actif.

Le backend conserve EPSG:4326 pour les échanges et les géométries PostGIS. `008_advanced_mapping.sql` étend les tables historiques `zones` et `tours`, puis ajoute les arrêts, versions de route, positions temporaires et incidents. La réversion est non destructive.

`RoutingProvider` sépare le métier du fournisseur. Le mode par défaut est `disabled`; il répond « itinéraire indisponible » sans fabriquer de ligne routière. OSRM doit être explicitement activé avec `ROUTING_PROVIDER=osrm`. Seules les coordonnées des arrêts sont transmises, avec timeout et validation stricte de la réponse. Les tests utilisent un fournisseur factice local.

Les positions sont volontaires, limitées à une tournée active, horodatées par PostgreSQL, limitées en fréquence et précision, et munies d’une expiration. Le citoyen ne reçoit qu’une position arrondie durant sa propre collecte en route ou arrivée. L’automatisation purge les positions expirées et prépare idempotemment les tournées du jour.

Le cache IndexedDB cartographique est séparé des actions hors connexion, marqué par rôle et vidé lorsqu’aucune authentification n’est disponible. Il sert uniquement d’état ancien explicite; aucune réponse API sensible n’est mise en cache par le service worker.
