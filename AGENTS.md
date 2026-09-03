# SmartWaste CM+

## Objectif

SmartWaste CM+ aide à signaler les problèmes de salubrité à Douala, à assister le tri par IA et à organiser les interventions et collectes domestiques. Une fonctionnalité est considérée comme réelle seulement si son interface, son API, sa logique métier, sa persistance, ses permissions et ses tests sont reliés.

## Architecture actuelle

- Backend FastAPI monolithique principalement dans `main.py`.
- Authentification JWT dans `auth.py` et `core/security.py`.
- PostgreSQL/PostGIS via `psycopg2` et `DATABASE_URL`.
- Frontend HTML/CSS/JavaScript statique dans `static/` avec Leaflet.
- IA ONNX pour la sévérité et le type de déchet; chatbot hybride avec Redis et services externes.
- OSRM/OSMnx/OR-Tools présents, mais certaines intégrations restent partielles.
- Aucun ORM ou système de migration complet ne doit être supposé opérationnel sans preuve.

## Dossiers importants

- `main.py`, `auth.py`: routes API actives.
- `app/`: routeurs et services expérimentaux; vérifier leur enregistrement avant usage.
- `static/`: interfaces par acteur.
- `core/`: sécurité.
- `tests/`: tests d’API; `test_chatbot.py` est un script manuel.
- `docs/`: documentation technique et académique.
- `.env`: configuration locale secrète, jamais versionnée.

## Commandes

- Installer: `pip install -r requirements.txt`
- Démarrer les dépendances: `docker compose up -d` (si Docker est disponible)
- Démarrer l’API: `uvicorn main:app --reload`
- Migration existante: `python run_migration.py` (regroupement des signalements uniquement, pas création de schéma)
- Tests: `pytest`
- Syntaxe: `python -m compileall .`
- Aucun lint, formatage ou build frontend n’est actuellement configuré; ne pas les inventer dans les rapports.

## Conventions

- Préserver les routes existantes autant que possible.
- Utiliser des requêtes SQL paramétrées.
- Centraliser les règles métier et les permissions dans des dépendances/services testables.
- Valider les coordonnées, états, tailles de fichiers et entrées utilisateur.
- Documenter explicitement les fonctionnalités implémentées, partielles, simulées et futures.

## Acteurs et sécurité

Les quatre rôles sont `admin`/gestionnaire, `agent` institutionnel, `ramasseur` privé et `citoyen`. Un abonnement est un état métier du citoyen, jamais un rôle supplémentaire.

- Le rôle seul ne suffit pas: vérifier propriété, affectation, statut et périmètre.
- Les secrets viennent de l’environnement; `.env` reste ignoré.
- Les mots de passe utilisent un KDF lent et les JWT ont une clé persistante configurée.
- Les actions sensibles doivent être auditables.
- Les positions GPS sont limitées à une mission active et leur conservation doit être bornée.

## Règles de travail

- Ne pas inventer une fonctionnalité: relier toute promesse à du code, des données et un test.
- Tester chaque changement dans son périmètre, puis exécuter les contrôles disponibles.
- Ne pas désactiver un test pertinent pour obtenir un résultat vert.
- Ne pas publier de secrets, fichiers `.env` ou poids de modèles.

## Travail terminé

Un changement est terminé lorsque le code, la persistance, les permissions, l’interface concernée, la documentation et les tests concordent, que les migrations applicables sont vérifiées, et que les limites restantes sont explicites.