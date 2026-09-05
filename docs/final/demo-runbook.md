# Environnement de demonstration reproductible

## Profils

- `degraded` (standard) : `SMARTWASTE_DISABLE_AI=true` et
  `ROUTING_PROVIDER=disabled`; aucune fausse IA/route.
- `complete` : uniquement avec poids verifies, fournisseur de generation local et
  instance OSRM autorisee; executer d'abord `scripts/ai_preflight.py`.

## Lancement

```powershell
$env:POSTGRES_PASSWORD='<mot-de-passe-temporaire>'
$env:JWT_SECRET_KEY='<secret-aleatoire-au-moins-32-octets>'
$env:PUBLIC_ORIGIN='https://demo.smartwaste.invalid'
$env:AUTOMATION_INTERVAL_SECONDS='300'
docker compose -p smartwaste_demo -f docker-compose.demo.yml build
docker compose -p smartwaste_demo -f docker-compose.demo.yml up -d
docker compose -p smartwaste_demo -f docker-compose.demo.yml ps
docker compose -p smartwaste_demo -f docker-compose.demo.yml exec api python scripts/ai_preflight.py
```

Appliquer `test.sql` puis les migrations 001 a 008 selon la procedure de
`docs/deployment-demo.md`. Les comptes temporaires sont crees via l'API ou un
outil de seed explicitement configure; aucun mot de passe permanent n'est fourni.

## Arret limite au projet

```powershell
docker compose -p smartwaste_demo -f docker-compose.demo.yml down
```

Ajouter `--volumes` uniquement apres sauvegarde et confirmation explicite de la
reinitialisation des seules donnees fictives du projet `smartwaste_demo`.
