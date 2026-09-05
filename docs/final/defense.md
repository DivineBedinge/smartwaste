# Soutenance SmartWaste CM+

## Resume 30 secondes

SmartWaste CM+ relie quatre acteurs autour des signalements et collectes a
Douala. La PWA associe workflows controles, PostGIS, medias prives, temps reel et
IA optionnelle avec revue humaine sous 80 %. La demonstration est reproductible,
et ses limites — poids IA absents, mono-instance, routage OSRM optionnel — sont
rendues visibles plutot que masquees.

## Scenario principal (8 a 12 minutes)

Probleme (45 s), installation PWA (30 s), citoyen/mascotte/signalement (2 min),
seuil et revue/affectation (1 min 30), preuve privee (45 s), collecte/tournee et
carte (2 min), messagerie/gestionnaire (1 min), securite (45 s), preuves
scientifiques (1 min), limites/perspectives (45 s). Version secours 5 minutes :
video/captures fictives, etat degrade explicite, workflows citoyen-gestionnaire,
tournee deterministe et tableau de preuves.

Sans Internet : utiliser le shell PWA deja charge, le routage desactive et les
resultats enregistres. Ne jamais faire passer une capture pour une execution
directe ni un fournisseur de test pour OSRM.

## Questions difficiles

- **Ou est l'IA ?** Dans les adaptateurs ONNX/RAG optionnels et la decision a
  seuil; sans poids, elle est degradee et l'humain reprend.
- **Quelles metriques ?** Aucune performance validee aujourd'hui; protocole et
  calculateur reproductibles, poids/dataset manquants clairement annonces.
- **Pourquoi Big Data ?** Pour PostGIS, index, pagination, outbox et traitements
  idempotents evolutifs; pas pour revendiquer un volume industriel inexistant.
- **Faux signalements ?** Identite, regroupement, seuil, revue, audit et
  contestation; aucune prevention absolue n'est promise.
- **GPS ?** Mission active, frequence/precision/retenue bornees et divulgation
  minimale.
- **PWA/iPhone ?** Une base Web installable et multiplateforme, avec limites
  Safari a valider physiquement.
- **Sans Internet ?** File locale identifiee/dedupliquee puis synchronisation;
  certaines fonctions serveur restent indisponibles.
- **Erreur du modele ?** Revue sous 80 %, hors sujet et indisponibilite; le
  gestionnaire peut corriger et auditer.
- **Multi-instance ?** Redis/broker, rate limit partage, stockage objet et worker
  orchestre sont requis.
- **Au-dela d'un CRUD ?** Machines a etats, permissions contextuelles, PostGIS,
  optimisation, outbox, offline et preuves privees.
- **Validation Cameroun ?** Contexte cible Douala, mais aucune etude terrain
  formalisee n'est revendiquee.
- **Avant adoption municipale ?** Audit juridique/securite, evaluation terrain,
  accessibilite/appareils, exploitation OSRM/IA, supervision et haute disponibilite.
