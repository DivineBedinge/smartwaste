## README.md pour SmartWaste CM+

Voici un README complet et professionnel, prêt à être placé à la racine de ton projet. Il couvre l’installation, la configuration, l’utilisation, l’architecture et les modules.

---

```markdown
#  SmartWaste CM+

**Plateforme intelligente de gestion des déchets pour Douala, Cameroun**

SmartWaste CM+ est un système complet de signalement, classification, valorisation et optimisation de la collecte des déchets. Il combine **vision par ordinateur**, **chatbot hybride RAG + LLM**, **optimisation VRP** et **cache Redis** pour offrir une solution contextualisée aux réalités camerounaises.

---

##  Fonctionnalités principales

-  **Signalement citoyen** : prise de photo + géolocalisation, classification automatique du type de déchet (12 classes).
-  **Chatbot intelligent** : questions en français, anglais ou camfranglais ; détection multi‑déchets ; réponses basées sur une base de connaissances enrichie ; traduction locale via LLM.
- **Points de collecte** : carte interactive, géolocalisation du point le plus proche, enregistrement des sociétés de retraitement.
- **Optimisation des tournées** : distances routières réelles (OSMnx), résolution VRP multi‑véhicules avec OR‑Tools.
-  **Dashboard gestionnaire** : validation des signalements, clustering spatial, suivi des tournées.
-  **Authentification JWT** : rôles citoyen, agent, municipal, admin.
-  **Cache Redis** : cache sémantique des réponses, mémoire de session.

---

##  Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (HTML/JS + Leaflet)            │
│  Citoyen  ·  Agent  ·  Gestionnaire                         │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP/REST
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                       Backend FastAPI                        │
│  · Auth JWT · Signalements · Chatbot · Tournées · Points    │
└───────────────┬──────────────────────────────┬──────────────┘
                │                              │
        ┌───────▼───────┐              ┌───────▼───────┐
        │ PostgreSQL   │              │ Redis         │
        │ + PostGIS    │              │ cache +       │
        │ + pgvector   │              │ session       │
        └───────┬───────┘              └───────────────┘
                │
        ┌───────▼─────────────────────────────────────────────┐
        │ Services d'IA : ONNX (classification)               │
        │                Ollama (LLM local)                    │
        │                SentenceTransformer (embeddings)      │
        │                CrossEncoder (rerank)                 │
        └─────────────────────────────────────────────────────┘
```

---

## Prérequis

- **Python** 3.9 ou supérieur
- **Docker** + **Docker Compose** (pour PostgreSQL/PostGIS, Redis)
- **Ollama** (pour le LLM local)
- **Connexion internet** (pour télécharger les modèles la première fois)

---

##  Installation

### 1. Cloner le projet

```bash
git clone https://github.com/ton-repo/smartwaste-cm.git
cd smartwaste-cm
```

### 2. Lancer PostgreSQL/PostGIS et Redis avec Docker

```bash
docker compose up -d
```

Ceci démarre :
- `smartwaste_postgres` (PostgreSQL + PostGIS)
- `smartwaste_redis` (Redis 7)

### 3. Configurer l'environnement backend

```bash
cd backend
copy .env.example .env
```

Édite `.env` :

```env
DATABASE_URL=postgresql://user:password@localhost:5432/database_name
POSTGRES_USER=smartwaste
POSTGRES_PASSWORD=replace-with-a-local-password
POSTGRES_DB=smartwaste_db
JWT_SECRET_KEY=replace-with-a-random-secret
COPERNICUS_USERNAME=replace-with-copernicus-username
COPERNICUS_PASSWORD=replace-with-copernicus-password
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=replace-with-a-redis-password
MODEL_TYPE_PATH=./modele_12classes.onnx
MODEL_BINARY_PATH=./modele_2classes.onnx
MODEL_SEVERITY_PATH=./smartwaste_mobilenetv2_clean.onnx
```

Les variables réelles restent dans `.env`, qui ne doit jamais être versionné.

### Modèles locaux

Les poids de modèles ne sont pas conservés dans Git afin d'éviter les fichiers volumineux et les limites de GitHub. Après téléchargement, placez-les à la racine du backend selon les chemins `MODEL_*_PATH` ci-dessus. Le modèle d'embeddings `multilingual-e5-small` doit être placé dans `models/multilingual-e5-small/`, notamment son fichier `model.safetensors`.

### 4. Créer l'environnement virtuel Python

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac
```

### 5. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 6. Installer Ollama et le modèle LLM

```bash
ollama pull qwen2.5:3b
```

> Pour un modèle plus léger : `ollama pull qwen2.5:1.5b`

### 7. Initialiser la base de données

Exécute les scripts SQL fournis dans `backend/sql/` :
- `create_tables.sql`
- `insert_prix.sql`
- `insert_quartiers.sql`
- `insert_points_collecte.sql`
- `insert_faq.sql`

Ou utilise `python init_db.py` si le script existe.

---

##  Lancement

### Backend FastAPI

```bash
cd backend
venv\Scripts\activate
uvicorn main:app --reload
```

### Accès aux interfaces

| Interface | URL |
|-----------|-----|
| Documentation API (Swagger) | http://127.0.0.1:8000/docs |
| Dashboard citoyen | http://127.0.0.1:8000/citoyen |
| Vue agent | http://127.0.0.1:8000/agent |
| Vue gestionnaire | http://127.0.0.1:8000/gestionnaire |
| Dashboard principal | http://127.0.0.1:8000/dashboard |

---

##  Comptes de démonstration

| Rôle | Email | Mot de passe |
|------|-------|--------------|
| Admin / Gestionnaire | `admin@smartwaste.cm` | `demo-admin-password` |
| Agent | `agent1@smartwaste.cm` | `demo-agent-password` |
| Récupérateur | `recup1@smartwaste.cm` | `demo-collector-password` |

> Crée ces comptes via Swagger : `POST /api/v1/auth/register`.

---

##  Modules détaillés

### 1. Module IA Vision
- Modèle : MobileNetV2 fine‑tuné, 12 classes (battery, biological, brown‑glass, cardboard, clothes, green‑glass, metal, paper, plastic, shoes, trash, white‑glass).
- Format : ONNX.
- Prétraitement : resize 224×224, normalisation ImageNet.
- Métriques : accuracy 97,35 %, F1 macro.

### 2. Module Chatbot hybride
- Normalisation : accents, ponctuation, correction orthographique (rapidfuzz).
- Détection de langue : français, anglais, camfranglais.
- Recherche : vectorielle (pgvector) + BM25.
- Fusion : Reciprocal Rank Fusion (RRF).
- Re‑ranking : Cross‑Encoder.
- Génération : LLM local `qwen2.5:3b` avec prompt anti‑hallucination.
- Cache & session : Redis.

### 3. Module Optimisation des tournées
- Graphe OSM de Douala (OSMnx).
- Matrice de distances réelles (Dijkstra).
- Résolution VRP avec OR‑Tools (capacité, nombre de véhicules).
- Paramètres configurables : arrondissement, nb véhicules, capacité, max signalements.

### 4. Module Géospatial
- Tables `zones`, `quartiers_douala`, `points_collecte`.
- Clustering spatial DBSCAN (`ST_ClusterDBSCAN`).
- Heatmap GeoJSON pour Leaflet.

---

## 🔌 Principaux endpoints API

### Auth
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

### Signalements
- `POST /api/v1/signalements`
- `PUT /api/v1/signalements/{id}/valider`
- `PUT /api/v1/signalements/{id}/prendre-en-charge`
- `POST /api/v1/signalements/{id}/preuve-traitement`
- `PUT /api/v1/signalements/{id}/statut`
- `PUT /api/v1/signalements/{id}/reclasser`

### Chatbot
- `GET /api/v1/chatbot/ask`
- `POST /api/v1/chatbot/analyser-image`
- `GET /api/v1/chatbot/point-proche`
- `GET /api/v1/chatbot/prix`

### Tournées
- `GET /api/v1/tournees/optimiser`
- `GET /api/v1/tournees/optimiser-vrp`
- `POST /api/v1/tournees/creer`
- `GET /api/v1/tournees/en-cours`

### Points de collecte
- `GET /api/v1/points-collecte`
- `POST /api/v1/societes/enregistrer`

---

##  Tests et validation

- **Chatbot** : questions types en français, anglais, camfranglais, multi‑déchets, salutations, hors‑sujet.
- **Classification** : matrice de confusion, précision top‑1.
- **VRP** : distance totale, ordre de visite.

---

##  Structure du projet

```
smartwaste-cm/
├── docker-compose.yml
├── README.md
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── auth.py
│   ├── redis_utils.py
│   ├── chatbot_utils.py
│   ├── normalizer.py
│   ├── route_optimizer.py
│   ├── core/
│   │   └── security.py
│   ├── models/
│   │   └── (modèles locaux)
│   ├── static/
│   │   ├── citoyen.html
│   │   ├── agent.html
│   │   ├── gestionnaire.html
│   │   └── dashboard.html
│   ├── sql/
│   │   ├── create_tables.sql
│   │   ├── insert_prix.sql
│   │   ├── insert_quartiers.sql
│   │   └── ...
│   └── requirements.txt
└── docs/
    ├── architecture.md
    ├── chatbot.md
    ├── redis_integration.md
    └── memoire_outline.md
```

---

##  Sources de données

- **OpenStreetMap** : routes, quartiers.
- **EcoCollect** : prix officiels de rachat.
- **NAMé Recycling** : contact, points de retraitement.
- **Enquêtes terrain** : 81 questionnaires ménages, 1 entretien expert.
- **Dataset Garbage Classification** (Kaggle) : images de déchets.

---

##  Améliorations futures

- Dépouillement statistique des questionnaires (pandas).
- Module prédictif des inondations.
- Application mobile Flutter / PWA.
- Tests automatisés (pytest).
- Intégration IoT (capteurs de bacs).
- Refactorisation de `main.py` en routers.

---

##  Licence

Projet académique – Master 2 IABD, Université de Douala.  
Tous droits réservés pour usage pédagogique.

---

##  Auteurs

- **Ton Nom** – Master 2 IABD
- Encadrant : M. Achille Tanko
```

---

##  À faire maintenant

1. **Copie le README** dans un fichier `README.md` à la racine de ton projet.
2. **Crée le dossier `docs/`** et ajoutes-y les fichiers `architecture.md`, `chatbot.md`, `redis_integration.md`, `memoire_outline.md` (je peux te les fournir si besoin).
3. **Vérifie que les URLs** et les endpoints correspondent bien à ton code (ajuste si nécessaire).

Si tu veux que je génère aussi les autres fichiers de documentation (architecture, chatbot, etc.), dis‑moi et je te les fournis immédiatement. 