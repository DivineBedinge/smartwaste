# Guide de démonstration

## Préparation

1. Copier `.env.example` vers `.env` et renseigner uniquement des valeurs locales.
2. Démarrer PostgreSQL/PostGIS avec `docker compose up -d` si Docker est disponible.
3. Appliquer `python migrate_schema.py`.
4. Installer les dépendances puis lancer `uvicorn main:app --reload`.
5. Ouvrir `/citoyen`, `/gestionnaire`, `/agent` ou `/ramasseur`.

## Comptes fictifs

Créer les comptes depuis l'API avec des adresses de démonstration et des mots de passe temporaires propres à la démonstration. L'inscription publique crée toujours un citoyen. Les comptes agent et ramasseur sont créés par un gestionnaire via `/api/v1/agents` et `/api/v1/ramasseurs`.

## Scénario citoyen

Se connecter comme citoyen, créer un signalement avec une image valide, consulter ses signalements et vérifier la notification de réception. Créer ensuite un abonnement domestique avec un plan actif et consulter `/api/v1/abonnements-domestiques/mes-abonnements`.

## Scénario gestionnaire

Se connecter avec un rôle `admin` ou `municipal`, créer un plan, créer un ramasseur, générer des occurrences sur une période, affecter une occurrence et consulter les journaux d'audit. Les erreurs de zone, de disponibilité et de capacité doivent être présentées comme des refus métier.

## Scénario ramasseur

Se connecter avec un compte `ramasseur`, ouvrir `/ramasseur`, consulter les collectes affectées et faire progresser une occurrence. Une collecte manquée exige un motif.

## IA et carte

Une confiance IA d'au moins 80 % est acceptée automatiquement; une confiance plus faible ou un hors sujet passe en revue. Les tests automatisés simulent OSRM. En cas d'indisponibilité OSRM, l'API retourne les points sans géométrie et un message d'indisponibilité.

## Limites connues

La génération automatique n'est pas un worker périodique. Les interfaces gestionnaire et citoyenne historiques ne couvrent pas encore toutes les nouvelles routes. Les migrations et les scénarios end-to-end nécessitent une base de test locale; aucune base de production ne doit être utilisée.