# Recette fonctionnelle et appareils

## Parcours critiques

Chaque parcours exige connexion, controle serveur, notification/messagerie,
deconnexion et absence d'acces a une ressource tierce.

- Citoyen : signalement, photo privee, position, revue IA/degradee, contestation,
  abonnement, collecte, carte, file hors connexion puis purge.
- Agent : affectation, carte, itineraire ou indisponibilite explicite, prise en
  charge, incident, preuve, messagerie et refus IDOR.
- Ramasseur : proposition, acceptation/refus, tournee, en route, arrivee,
  effectuee/manquee, preuve, reprise hors connexion et refus d'une collecte tierce.
- Gestionnaire : revue/reclassification, affectation, contestation/reouverture,
  tournee/capacite, filtres, audit, assistant et restriction de perimetre.

Les tests API via `TestClient` et PostgreSQL couvrent les parcours critiques au
niveau HTTP/metier; les contrats DOM/PWA sont controles par Node. Les
interactions navigateur reelles restent a completer avec un runner E2E et un
navigateur disponibles localement; aucun binaire n'est telecharge silencieusement.

## Checklist appareil

Statut initial de chaque item : **a realiser sur appareil physique**.

| Appareil | Verifications |
|---|---|
| iPhone recent / Safari | ajout accueil, icone, standalone, safe areas, barre basse, clavier, camera, GPS, carte, mascotte, chatbot, bottom sheet, dark mode, rotation, offline/reconnexion, notifications, badge, purge deconnexion |
| Android / Chrome | installation, icone maskable, camera/GPS, carte, offline, notifications, rotation et purge |
| Ordinateur | clavier, ordre de focus, zoom 200 %, lecteurs d'ecran, offline et responsive |

Ne passer un item a « reussi » qu'avec appareil/version/date et observation.

## Accessibilite

Verifier libelles, focus visible, tailles tactiles, contrastes, formulaires,
messages d'erreur, langue, reduced-motion et equivalence textuelle des cartes.
Les tests statiques ne remplacent ni VoiceOver ni TalkBack.
