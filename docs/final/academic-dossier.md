# Dossier academique a relire avant integration au memoire

## Probleme et objectifs

A Douala, le prototype explore une chaine numerique de signalement, revue,
intervention et collecte domestique. Il vise tracabilite, coordination de quatre
acteurs et usage mobile sobre. Il ne prouve pas encore un impact municipal.

## Conception

FastAPI fournit API typee et WebSocket; PostgreSQL assure transactions, audit et
outbox; PostGIS gere zones/proximite; la PWA evite une application native
distincte; Tailwind est compile localement. Les machines a etats evitent les
transitions paralleles, et les medias restent hors du repertoire public.

## IA et donnees

La decision applique un seuil de 80 % : en dessous, hors sujet ou erreur,
l'humain revoit. Ce seuil est une regle de risque produit, pas une performance
scientifique. ONNX, recherche hybride et generation sont optionnels; sans poids,
le mode degrade est affiche. PostGIS, index, pagination, outbox et jobs montrent
des briques evolutives, pas une plateforme Big Data industrielle.

## Strategie de validation

Tests unitaires, API, permissions/IDOR, PostgreSQL/PostGIS, DOM/XSS, WebSocket,
PWA et Docker sont reproductibles. L'evaluation IA exige poids, dataset licite et
split documente. Les validations terrain, juridiques et appareils physiques sont
des travaux futurs.

## Analyse critique et perspectives

Forces : workflows relies, permissions serveur, degradation explicite, preuve
privee et audit. Limites : mono-instance, JWT navigateur, CDN/inline historiques,
absence d'evaluation IA et de routage reel. Perspectives : Redis/broker,
stockage objet prive, sessions revocables, dependances cartographiques locales,
OSRM exploite, evaluation terrain et gouvernance des donnees.
