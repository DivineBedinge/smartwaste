# Stockage privé des médias

`MediaStorage` découple les règles métier du backend physique. Le prototype utilise
`LocalPrivateMediaStorage`; S3 ou MinIO pourront implémenter la même interface.
`MEDIA_STORAGE_PATH` vaut par défaut `./var/private_media`, hors de `static`, et le
dossier est ignoré par Git. Les racines système, le dépôt, `.git`, `static` et les
chemins vides sont refusés.

Les noms physiques sont des UUID générés côté serveur. Les images JPEG, PNG et WebP
sont décodées, vérifiées, réencodées sans EXIF, bornées en taille et dimensions,
puis écrites dans un fichier temporaire et déplacées atomiquement. La table
`media_assets` conserve uniquement métadonnées, SHA-256, usage, propriétaire,
ressource et rétention; aucun octet d'image n'y est stocké.

Les uploads autonomes restent `temporary` pendant 24 heures. Leur propriétaire peut
les supprimer. Lors d'un rattachement métier ils deviennent `active`. Une erreur
SQL pendant l'enregistrement est compensée immédiatement; le nettoyage idempotent
des temporaires expirés et fichiers orphelins est prévu dans les tâches du Prompt 3.

Les endpoints `/api/v1/media` sont authentifiés. La lecture dépend du propriétaire,
de l'affectation, de la participation à la conversation ou du rôle gestionnaire.
Une ressource inaccessible retourne 404. Les réponses utilisent `private, no-store`,
`nosniff` et un nom de fichier neutre sans exposer le chemin physique.

Les colonnes Base64 historiques demeurent lisibles via l'endpoint de compatibilité
des signalements. Les nouveaux signalements, preuves et messages écrivent désormais
un identifiant `media_assets`; toute nouvelle écriture Base64 est dépréciée et
interdite. Aucune conversion automatique des données historiques n'est réalisée.
