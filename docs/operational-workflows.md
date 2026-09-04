# Workflows opérationnels

La migration `007_operational_workflows.sql` ajoute uniquement les données nécessaires aux décisions humaines, à l’historique des transitions, aux preuves privées et aux tâches automatiques. Elle dépend de `006_private_media.sql`.

## Signalements

La classification IA reste automatique à partir de 80 % de confiance. En dessous de ce seuil, une revue gestionnaire est obligatoire. L’affectation vérifie le rôle actif et la zone de l’agent. Seul l’agent affecté peut prendre en charge le signalement et soumettre une preuve privée. La preuve est ensuite acceptée, refusée ou remplacée par le gestionnaire. Une acceptation clôt le signalement; son propriétaire peut le contester dans la fenêtre configurée par `REPORT_DISPUTE_HOURS`.

## Collectes domestiques

La génération est idempotente grâce à l’unicité `(subscription_id, scheduled_for)`. Une affectation est une proposition limitée par zone, disponibilité et capacité. Le ramasseur peut accepter ou refuser avec motif, puis déclarer `en_route`, `arrivee` et `manquee`. Après l’arrivée, une preuve privée place la collecte en attente de confirmation. Seul le citoyen abonné peut confirmer ou contester.

## Automatisation et notifications

`python run_automation.py` exécute une tâche quotidienne protégée par un verrou consultatif PostgreSQL et par `job_runs`. Elle génère l’horizon futur, expire les propositions, marque les occurrences échues, purge les notifications lues, les médias temporaires et les positions GPS expirées. Les événements utilisateur passent par `create_notification`, donc par l’outbox existante. La planification externe de cette commande reste une responsabilité d’exploitation.

Toutes les commandes doivent recevoir une `DATABASE_URL` dont le nom de base contient `_test` durant les tests. Les médias de test utilisent un répertoire temporaire via `MEDIA_STORAGE_PATH`.
