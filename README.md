# SmartWaste CM+

SmartWaste CM+ est un prototype de PWA FastAPI/PostgreSQL/PostGIS pour les
signalements de salubrite et les collectes domestiques a Douala. Quatre roles
sont controles cote serveur : citoyen, agent, ramasseur et gestionnaire.

## Etat reel

- API FastAPI, workflows, permissions, stockage prive, audit et outbox :
  implementes et testes.
- Cartographie Leaflet et contrat de routage : implementes. Le routage routier
  n'est reel que si `ROUTING_PROVIDER=osrm` pointe vers une instance disponible.
- Classification ONNX et RAG : code present, mais aucun poids n'est versionne.
  Des poids locaux ignores peuvent activer un mode partiel; l'image Docker
  standard demarre en mode degrade. Aucune performance de
  classification n'est revendiquee sans execution du protocole d'evaluation.
- PostgreSQL/PostGIS : huit migrations additives et schema `test.sql`.
- Deploiement : profil Docker de demonstration mono-instance, pas une production
  publique ni une architecture multi-instance.

La matrice de preuve et les limites sont dans
[`docs/final/traceability.md`](docs/final/traceability.md) et
[`docs/final/limitations.md`](docs/final/limitations.md).

## Installation et validation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm ci
Copy-Item .env.example .env
uvicorn main:app --reload
```

Ne conservez des valeurs reelles que dans `.env`, qui est ignore. La base
d'integration autorisee est uniquement `smartwaste_test` sur le port hote
`55433`.

```powershell
$env:APP_ENV='test'
$env:POSTGRES_TEST_PORT='55433'
$env:MEDIA_STORAGE_PATH="$env:TEMP\smartwaste-media-test"
pytest -q
npm run build:css
npm run build:icons
npm run check:js
node tests/check_inline_scripts.js
node tests/check_dom_security.js
python scripts/ai_preflight.py --verify-classifier --database
```

La pre-verification IA ne telecharge rien. Pour calculer des metriques avec de
vraies predictions, utilisez `scripts/evaluate_classifier.py`; le CSV attendu
contient `actual,predicted,confidence,latency_ms`. Dataset, poids et separation
train/test doivent etre documentes.

## Documentation

- exploitation : [`docs/deployment-demo.md`](docs/deployment-demo.md)
- dossier final : [`docs/final/`](docs/final/)
- validation scientifique : [`docs/final/scientific-evaluation.md`](docs/final/scientific-evaluation.md)
- recette : [`docs/final/acceptance.md`](docs/final/acceptance.md)
- soutenance : [`docs/final/defense.md`](docs/final/defense.md)

Le prototype ne garantit pas une conformite juridique complete. Les essais sur
appareils physiques et l'evaluation quantitative de l'IA restent a realiser
tant qu'aucune preuve correspondante n'est fournie.
