# Déploiement de démonstration et exploitation

## Configuration

Les environnements acceptés sont `development`, `test`, `demo`, `staging` et `production`. En démonstration/production, le démarrage refuse une clé JWT faible, un mot de passe PostgreSQL fictif, un stockage média relatif ou temporaire, HTTP et les origines non HTTPS. Les secrets sont fournis uniquement par l'environnement.

Exemple de préparation, avec valeurs fictives :

```powershell
$env:POSTGRES_PASSWORD='<mot-de-passe-fictif-à-remplacer>'
$env:JWT_SECRET_KEY='<secret-aléatoire-fictif-de-32-caractères-minimum>'
$env:PUBLIC_ORIGIN='https://demo.smartwaste.invalid'
docker compose -f docker-compose.demo.yml build
docker compose -f docker-compose.demo.yml up -d postgres api proxy
docker compose -f docker-compose.demo.yml run --rm automation
```

Le proxy d'exemple écoute localement sur 8080. TLS doit être terminé par un proxy de confiance : créer les certificats hors dépôt, rediriger HTTP vers HTTPS et limiter `--forwarded-allow-ips` à ce proxy. Aucun DNS ou certificat n'est provisionné par le projet.

L'image de démonstration utilise `requirements-runtime.txt` et démarre avec l'IA lourde désactivée, car les poids ne sont jamais intégrés à l'image. Les fonctions concernées signalent un mode dégradé. Une image IA séparée pourra être construite ultérieurement avec modèles locaux vérifiés, sans élargir les privilèges de l'API.

## Santé et observabilité

- `/health/live` : processus vivant, sans dépendance.
- `/health/ready` : PostgreSQL, PostGIS, migrations et état du routage, sans DSN ni chemin.
- `/health` : statut public minimal et version applicative.

Chaque réponse porte `X-Request-ID`. En `LOG_FORMAT=json`, les logs incluent environnement, route, statut et durée, jamais le token, le corps, le média ou la position. Les automatisations restent indépendantes de l'API et utilisent le verrou consultatif et `job_runs` existants.

## Sauvegarde et restauration

Toujours vérifier explicitement le nom avant une opération. Pour la recette locale, seules les bases contenant `_test` et le port hôte `55433` sont autorisés :

```powershell
docker exec smartwaste_postgres_test psql -U smartwaste_test -d smartwaste_test -Atc 'SELECT current_database()'
docker exec smartwaste_postgres_test pg_dump -U smartwaste_test -d smartwaste_test -Fc -f /tmp/smartwaste_test.dump
docker cp smartwaste_postgres_test:/tmp/smartwaste_test.dump ./smartwaste_test.dump
```

Restaurer dans un conteneur éphémère distinct, attendre son démarrage final, puis créer `smartwaste_restore_test` depuis `template0` avant `pg_restore --exit-on-error`. Cela évite les conflits avec les extensions préchargées par l'image PostGIS. Ne publier aucun port pour ce conteneur. Vérifier `PostGIS_Version()`, `schema_migrations`, les contraintes, l'audit, l'outbox et `media_assets`. Le dump ne contient que les métadonnées média ; les fichiers privés sont sauvegardés séparément, chiffrés en production. Supprimer localement le dump après recette. Un rollback applicatif utilise l'image précédente ; les migrations additives ne sont jamais annulées par suppression silencieuse.

## Médias privés

Le volume `/app/var/private_media` est persistant et inaccessible au proxy. Les limites MIME, taille et dimensions, la normalisation, les fichiers temporaires et les contrôles de chemin restent appliqués. Contrôle en lecture seule :

```powershell
python scripts/media_integrity.py
```

Le rapport recense lignes sans fichier, fichiers orphelins et temporaires expirés. Il ne répare ni ne supprime rien. Toute réparation doit être une opération explicite, sauvegardée et auditée.

## Rétention et confidentialité

Les comptes, signalements et audits suivent la durée métier définie par l'exploitant. Les positions opérationnelles expirent selon la configuration existante ; les médias temporaires et orphelins sont contrôlés régulièrement. Les messages, notifications, preuves, contestations et sauvegardes ne sont accessibles qu'aux rôles autorisés. Les logs minimisent les identifiants et excluent contenus, tokens et coordonnées précises. L'historique assistant reste dans `sessionStorage` et est purgé à la déconnexion. Une conformité légale complète nécessite un audit juridique camerounais dédié.

## Mise à jour et retour arrière

1. Sauvegarder et vérifier l'archive.
2. Construire l'image et exécuter les tests sur `smartwaste_test:55433`.
3. Appliquer les migrations une seule fois.
4. Vérifier readiness, outbox et automatisations.
5. En cas d'échec, remettre l'image précédente sans supprimer les colonnes nouvelles.

## Recette iPhone manuelle

- Ouvrir le site HTTPS avec Safari et l'ajouter à l'écran d'accueil.
- Vérifier l'icône 180 px, le mode standalone, la status bar et les safe areas.
- Tester clavier, rotation, dark mode, mouvement réduit et reprise après fermeture.
- Refuser puis autoriser caméra, géolocalisation et notifications.
- Contrôler navigation basse, carte, mascotte, bottom sheet, déconnexion et purge.
- Tester une mise à jour du Service Worker et une session hors connexion.

Cette checklist est manuelle : aucun test sur iPhone physique n'est revendiqué ici.

## Limites du prototype

Le rate limiting est mono-instance et doit évoluer vers Redis en multi-instance. La CSP conserve temporairement `unsafe-inline` pour les scripts/styles historiques et les CDN Leaflet/Chart.js/Lucide existants. Le proxy fourni documente le raccordement mais ne crée pas de TLS. Le routage reste désactivable et ne fabrique aucune route en cas d'indisponibilité.
