# Matrice de tracabilite finale

| Besoin | Role | Fonction/API | Service/persistance | Interface | Permission | Preuve test | Resultat et limite |
|---|---|---|---|---|---|---|---|
| Authentification | tous | `/api/v1/auth/*` | `auth.py`, `users` | quatre pages | JWT + role + compte actif | `test_security_hardening.py`, `test_role_matrix.py` | teste; JWT navigateur, pas de revocation centrale |
| Signalement et IA | citoyen | creation signalement | `core/classification.py`, `reports` | `citoyen.html` | propriete | `test_api.py`, `test_classification.py` | workflow teste; poids IA absents, revue humaine en mode degrade |
| Validation/affectation/preuve | gestionnaire, agent | routes workflow | `workflows.py`, preuves/historique | trois interfaces | role + zone + affectation | `test_assignments.py`, `test_workflow_states.py` | implemente et teste |
| Contestation/reouverture | citoyen, gestionnaire | routes workflow | `report_disputes`, audit | deux interfaces | propriete/perimetre | `test_workflow_states.py` | implemente et teste |
| Collecte domestique | citoyen, ramasseur | routes collections | subscriptions/occurrences | deux interfaces | propriete + affectation + etat | `test_collections.py`, `test_tour_security.py` | implemente et teste |
| Tournee/carte/routage | trois roles operationnels | `/api/v1/map/*` | geo/routing, migration 008 | quatre cartes | role + perimetre + emprise | `test_geo.py`, `test_routing.py` | contrat teste; OSRM reel non evalue |
| Messagerie | quatre roles | communications | conversations/messages | `communications.js` | participant + contexte | `test_communications.py` | implemente et teste |
| Notifications temps reel | quatre roles | notifications/WS | outbox | shell commun | destinataire | `test_realtime_notifications.py`, `test_websocket_security.py` | mono-instance hors broker partage |
| Hors connexion | citoyen, ramasseur | synchronisation | IndexedDB, UUID client | offline/SW | identite + deduplication | `test_service_worker.py`, `test_pwa_ui.py` | statique; appareil non teste |
| Chatbot/assistant | quatre roles | chatbot/assistant geo | catalogue ferme, RAG optionnel | mascotte | role/propriete avant outil | `test_geo_assistant.py`, `test_chat_routing.py` | assistant controle; RAG complet non evalue |
| Medias prives | acteurs autorises | `/api/v1/media/*` | MediaStorage/media_assets | preuves | propriete/affectation | `test_media_storage.py`, `test_upload_security.py` | stockage local, pas multi-instance |
| Audit/automatisation | gestionnaire/systeme | worker | audit_logs/job_runs/verrou | diagnostics | restreint | `test_automation_worker.py` | worker demo, pas orchestrateur industriel |
| Securite/PWA | tous | middleware/manifest/SW | CSP/rate limit/request ID | shell | serveur | `test_security_configuration.py`, `test_pwa_ui.py` | dette CSP historique documentee |

Une fonctionnalite n'est qualifiee terminee que si API, persistance, permission
et test sont relies.
