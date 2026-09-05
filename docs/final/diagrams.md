# Diagrammes conformes au code

```mermaid
flowchart LR
  PWA[PWA 4 roles] --> API[FastAPI + permissions]
  API --> PG[(PostgreSQL/PostGIS)]
  API --> MEDIA[MediaStorage prive]
  API --> OUTBOX[Outbox]
  OUTBOX --> WS[WebSocket prive/polling]
  API --> ROUTE[RoutingProvider]
  API --> AI[IA optionnelle/degradee]
  WORKER[Worker planifie] --> PG
```

```mermaid
sequenceDiagram
  participant U as Utilisateur autorise
  participant A as API/metier
  participant D as PostgreSQL
  participant O as Outbox/WS
  U->>A: action + JWT
  A->>A: role, propriete, etat, zone
  A->>D: transaction parametree
  A->>D: audit + evenement outbox
  D-->>A: commit
  O-->>U: evenement minimal prive
```

```mermaid
flowchart TD
  Q[Question assistant] --> I[Catalogue d'intentions]
  I --> P[Permission serveur]
  P -->|refus| R[Reponse controlee]
  P -->|autorise| S[Service metier]
  S --> R
  R --> T[textContent / lien controle]
```

Medias : upload valide -> fichier temporaire prive -> ligne `media_assets` dans
la transaction -> renommage atomique; acces ensuite par endpoint autorise.
Hors connexion : action UUID liee a l'identite -> file IndexedDB -> reprise ->
deduplication serveur -> suppression locale seulement apres confirmation.
