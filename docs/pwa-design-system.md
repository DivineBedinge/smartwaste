# Design system PWA SmartWaste

La couche commune utilise le CSS compilé localement depuis `static/src/smartwaste.css`. Les primitives `sw-card`, `sw-btn`, `sw-field`, `sw-badge`, `sw-glass` et `sw-skeleton` couvrent les variantes principales sans dépendre de données utilisateur.

La navigation comporte au plus cinq destinations selon le rôle. La mascotte SVG locale ouvre l'assistant géographique existant dans une bottom sheet mobile ou un panneau latéral. L'historique court reste dans `sessionStorage`; aucune action métier sensible n'est exécutée automatiquement.

Le thème suit la préférence système ou la préférence locale. Les safe areas iOS, les cibles de 44 px, le focus, le contraste renforcé et `prefers-reduced-motion` sont pris en charge.
