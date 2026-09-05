# Registre des limites

| Type | Limite | Evolution |
|---|---|---|
| Securite | JWT dans localStorage, pas de revocation centrale | cookie HttpOnly/SameSite + CSRF, sessions revocables |
| Architecture | rate limiter et temps reel mono-instance | Redis/broker partages |
| CSP | inline et CDN historiques | extraction et dependances locales/SRI |
| Infrastructure | OSRM desactive | instance exploitee et surveillee |
| IA | poids absents, evaluation non executee | artefacts signes, dataset licite et metriques versionnees |
| Automatisation | worker intervalle mono-instance | orchestrateur et metriques |
| Sauvegarde | chiffrement/rotation externes | coffre de cles et politique testee |
| Juridique | aucun audit juridique | DPIA et conseil juridique camerounais |
| Appareils | iPhone/Android non testes physiquement | recette appareils reels |
| Metier | portee zone depend des affectations | gouvernance et revues periodiques |
| Scalabilite | stockage media local | stockage objet prive et multi-instance |

Le prototype ne doit pas etre presente comme une production publique.
