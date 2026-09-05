# Evaluation scientifique reproductible

## Inventaire reel

`python scripts/ai_preflight.py` inspecte sans telechargement dependances et
poids locaux. Au 5 septembre 2026, aucun poids n'est indexe par Git. Des poids
ONNX et SentenceTransformer ignores sont presents sur le poste de validation :
les trois sessions ONNX ont ete chargees sur CPU, mais le chargement des
embeddings n'a pas ete valide et aucun generateur n'est configure. Le mode
constate est donc `partial`; l'image Docker standard reste `degraded`. Le seuil
metier est 0,80; sous ce seuil, ou si le modele echoue, une revue humaine est
requise.

| Composant | Categorie prouvee |
|---|---|
| Decision de severite/seuil 80 % | implemente et teste |
| Sessions ONNX paresseuses | implemente; trois poids locaux ignores charges sur CPU |
| Embeddings, pgvector, BM25, RRF, reranker | code present; chaine complete non evaluee |
| Assistant geographique | catalogue, permissions et refus testes |
| Generateur Ollama | externe optionnel, absent de l'image standard |
| Routage | faux fournisseur deterministe; OSRM reel non evalue |

## Classifieur

Protocole : geler et hacher poids/dataset; separer les sources avant
pretraitement; produire `actual,predicted,confidence,latency_ms`; lancer
`scripts/evaluate_classifier.py`; rapporter taille, classes, accuracy,
precision/rappel/F1, matrice, latence et taux de revue a 0,80.

Resultat actuel : **non execute**, faute de poids et dataset d'evaluation. Aucun
pourcentage de performance n'est revendique et la fuite train/test ne peut pas
etre evaluee sans provenance des donnees.

## RAG, routage et donnees

Le futur jeu RAG, sans donnees personnelles, couvrira tri, valorisation, sources
locales, hors sujet, ambiguite, absence de source, injection, demande tierce,
francais et anglais. Un humain verifiera source, exactitude, refus et pertinence;
le jugement du generateur sur lui-meme ne vaut pas preuve. Actuellement, refus,
permissions, intentions simples et mode degrade sont testes.

Le fournisseur de routage deterministe teste le contrat mais n'est pas un moteur
routier. Sans OSRM, aucune distance/duree routiere reelle n'est annoncee.

PostGIS, GiST, pagination, outbox et traitements idempotents demontrent des
mecanismes compatibles avec une montee en charge, pas un Big Data industriel.
Les menaces a la validite sont : donnees synthetiques, environnement local,
absence d'essai terrain formalise, de poids et de test mobile physique.

La mesure brute du 5 septembre 2026 est conservee dans
`results/data-layer-2026-09-05.json` : base 23 806 755 octets, 1 signalement,
4 utilisateurs fictifs, requete pagee 5,503 ms et requete `ST_DWithin` 110,545
ms. Cet echantillon minuscule mesure uniquement l'environnement local et ne
permet aucune conclusion de scalabilite.
