# Audit final des sinks HTML

Inventaire initial : 30 `innerHTML`, 0 `outerHTML`, 0 `insertAdjacentHTML`,
0 `document.write` et 10 appels Leaflet `bindPopup`.

Les 14 `innerHTML` conservés sont classés comme suit :

- `dashboard.html` (légende) et `gestionnaire.html` (légende) : constantes statiques sûres ;
- `citoyen.html` (indicateur de saisie) : constante statique sûre ;
- `citoyen.html` (cartes et modale) : données serveur, toutes les interpolations passent par `safeHtml` ;
- `dashboard.html` (carte hors sujet) : données serveur, interpolations par `safeHtml` et image contrôlée par `safeImageDataUrl` ;
- `gestionnaire.html` (signalements, tournées, agents, prix, points, groupes et résumé d'itinéraire) : données serveur ou localisées, interpolations par `safeHtml` ; les identifiants d'action sont convertis en nombres ;
- les affectations servant seulement à vider un conteneur ou afficher un texte ont été remplacées par `replaceChildren`/`textContent`.

Les 10 popups Leaflet sont soit des constantes, soit des éléments DOM créés explicitement,
soit des gabarits `safeHtml`. Aucun contenu serveur n'est concaténé sans échappement.

`safeUrl` limite les liens à HTTPS et `tel:` ; HTTP n'est accepté que si l'appelant le
demande explicitement sur localhost. Les URL `javascript:` et `data:` sont refusées.
Les aperçus image utilisent une validation distincte limitée à PNG, JPEG et WebP base64 ;
SVG est refusé. Les URL blob créées localement pour les exports ne proviennent pas du serveur.
