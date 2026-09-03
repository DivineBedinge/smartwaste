# Architecture et état vérifié

## Architecture

Le prototype est un monolithe FastAPI. `main.py` contient la majorité des routes et appelle PostgreSQL/PostGIS directement via `psycopg2`. `auth.py` porte l’authentification JWT. Les routeurs spécialisés sont dans `app/routers/`. Le frontend est constitué de pages HTML/JavaScript statiques dans `static/` et utilise Leaflet. Les modèles ONNX sont chargés localement; le chatbot utilise Redis, des embeddings, BM25, un reranker et un LLM local selon la configuration.

## Acteurs et autorisations

| Acteur | Autorité | Périmètre |
|---|---|---|
| Gestionnaire | administration et arbitrage | comptes professionnels, revue IA, opérations et support |
| Agent institutionnel | interventions publiques | missions et tournées qui lui sont affectées |
| Ramasseur privé | collectes domestiques | occurrences qui lui sont affectées |
| Citoyen | signalements et abonnement | ses propres données et services souscrits |

`admin` et `municipal` restent acceptés comme rôles gestionnaire historiques pour compatibilité. Un abonnement ne crée pas de rôle supplémentaire.

## Signalements publics

Les états de référence sont `soumis`, `en_analyse`, `a_verifier`, `classifie`, `valide`, `rejete`, `hors_sujet`, `assigne`, `en_route`, `en_cours`, `traite`, `verification_requise`, `cloture` et `reouvert`. Les transitions autorisées sont centralisées dans `core/policy.py`.

La décision IA utilise `AUTO_ACCEPT_THRESHOLD = 0.80`. Une confiance égale ou supérieure à 80 % est acceptée automatiquement, sauf hors sujet. Une confiance inférieure ou une panne place le signalement en revue/analyse. La persistance des métadonnées détaillées est préparée par `migrations/001_workflows.sql`.

## Collectes domestiques

La migration prépare les plans, créneaux, abonnements et occurrences. Les états d’occurrence sont `programmee`, `affectee`, `en_route`, `arrivee`, `effectuee`, `confirmee`, `manquee` et `reprogrammee`. Un motif est requis pour `manquee` dans l’API ramasseur. La génération automatique d’occurrences, la disponibilité avancée des véhicules et les notifications push restent à implémenter.

## Réclamations, incidents et suggestions

Les demandes transversales sont stockées dans `support_requests`. Elles sont visibles par leur auteur et listables par le gestionnaire. Les catégories restent validées au niveau métier à compléter dans une prochaine tranche; les pièces jointes ne sont pas encore téléversées par ce module.

## Cartographie et temps réel

OSRM fournit les routes lorsque l’appel externe réussit; OSMnx/NetworkX et OR-Tools sont présents pour le graphe et le VRP. Les appels externes ne sont pas encore centralisés dans un adaptateur unique et le suivi GPS n’a pas encore de limitation de fréquence ni de politique de rétention complète. Le WebSocket historique reste global et ne doit pas être présenté comme un canal privé sécurisé.

## Migrations

Les migrations additives sont `migrations/001_workflows.sql` et `migrations/002_collector_operations.sql`. Elles conservent les données existantes et sont suivies par `schema_migrations`. Exécution : `python migrate_schema.py`. Les réversions correspondantes doivent être utilisées uniquement après sauvegarde explicite.

`test.sql` est le schéma historique de référence pour une base neuve. Il contient encore des seeds et des requêtes de diagnostic historiques; les migrations servent à mettre à niveau une base existante. Le bootstrap de `test.sql` est validé sur PostgreSQL/PostGIS local.

## Matrice de maturité

| Fonctionnalité | État |
|---|---|
| Authentification JWT et rôles historiques | implémentée mais à renforcer |
| Quatre rôles métier explicites | implémentée et testée au niveau des règles |
| Contrôle d’affectation agent | partiellement implémenté dans les routes principales |
| Seuil IA 80 % et panne du modèle | implémentée et testée |
| Migration des workflows | implémentée mais non exécutée ici sur une base réelle |
| Abonnements domestiques et statut | implémentés dans l’API et non encore reliés aux écrans |
| Occurrences/calendrier automatique | implémenté et testé au niveau du générateur; planification périodique absente |
| Réclamations/support | implémentés dans l’API et non encore reliés à tous les écrans |
| Carte moderne et suivi GPS sécurisé | partiellement implémentés; carte d’intervention complète restante |
| Notifications persistantes | implémentées dans l’API et testées au niveau du service |
| Tests d’intégration avec PostgreSQL/OSRM | non implémentés |