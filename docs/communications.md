# Communications, support et notifications

## Portée réellement reliée

Le centre commun `static/communications.js` est chargé par les interfaces citoyen,
agent, ramasseur et gestionnaire. Il affiche l'historique paginé, le compteur non
lu, la lecture individuelle et globale, les états vide/chargement/erreur et les
liens internes validés. Il interroge l'API toutes les 30 secondes; les WebSockets
historiques restent cloisonnés par utilisateur mais ne transportent pas encore ce
catalogue complet.

Les événements effectivement reliés sont: réception, changement d'état et résultat
de preuve d'un signalement; création et modification d'un abonnement; affectation,
rappel, reprogrammation, annulation et absence pour une collecte; réception,
réponse et changement d'état d'une demande de support; nouveau message, clôture de
conversation, demande de rappel et changement de son état. Les événements annoncés
mais dépourvus de transition métier restent seulement des types prévus:
acceptation/refus du ramasseur et confirmation/contestation citoyenne.

Les notifications stockent une seule clé (`notification.*`) et ses paramètres
JSONB, avec titre et contenu français historiques de secours. `static/i18n.js`
rend les libellés système FR/EN; les textes libres des utilisateurs ne sont jamais
traduits. Le français est le repli.

## Participants et sécurité

| Ressource | Participants dérivés |
|---|---|
| Signalement | citoyen propriétaire, agent affecté, gestionnaires actifs |
| Collecte active | citoyen abonné, ramasseur affecté, gestionnaires actifs |
| Tournée | agent affecté, gestionnaires actifs |
| Support | auteur, gestionnaire affecté, gestionnaires actifs |

Il n'existe ni recherche de personnes ni ajout arbitraire. Chaque lecture et envoi
revérifie l'appartenance, l'expéditeur vient du JWT, les requêtes sont paramétrées,
les conversations closes refusent les envois et la limite est de 30 messages par
minute. Une photo passe par le validateur d'upload existant. Les messages sont
rendus avec `textContent`. L'identifiant UUID client est unique par conversation,
ce qui rend les reprises idempotentes. Les signalements d'abus sont conservés.

## Cycle de vie et mode hors connexion

Une conversation est créée ou récupérée pour une seule ressource, puis ouverte,
lue et enfin close. Une conservation applicative de 365 jours après clôture est
recommandée; aucun effacement automatique n'est activé dans cette tranche afin de
ne pas supprimer de données sans politique validée.

IndexedDB conserve UUID, conversation, texte, photo facultative, date, tentatives,
état et dernière erreur. Les états sont `pending`, `sending`, `failed` et
`auth_required`; le succès serveur supprime seulement alors l'entrée locale. La
reprise se fait au retour en ligne ou via `retryPendingMessages()`.

## Support, rappel et téléphone

Les catégories et états sont contrôlés par l'API. Une ressource liée doit appartenir
au demandeur; les gestionnaires peuvent répondre et changer l'état avec audit.
Les rappels ont un motif, une date souhaitée facultative et un historique. Le seul
appel proposé est un lien `tel:` vers `SUPPORT_PHONE`, validé au format E.164 et
journalisé sans contenu d'appel. Aucun numéro personnel, VoIP, WebRTC ou audio.

## API et migration

- `/api/v1/notifications`, `/unread-count`, `/{id}/read`, `/read-all`
- `/api/v1/demandes-support` et endpoints gestionnaire associés
- `/api/v1/conversations`, `/{id}/messages`, `/{id}/read`, `/{id}/close`
- `/api/v1/messages/{id}/report`
- `/api/v1/callback-requests` et `/api/v1/support-phone`

`migrations/004_communications.sql` est additive et aligne notifications, support,
conversations, participants, messages, lectures, abus et rappels. Le fichier
`.down.sql` est volontairement non destructif. `test.sql` demeure le schéma de
référence historique aligné.
