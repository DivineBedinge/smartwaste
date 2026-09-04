# Assistant géographique contrôlé

L’assistant n’utilise ni SQL libre ni appel d’endpoint choisi par un modèle. `geo_assistant.py` identifie une intention dans un catalogue fermé par rôle; le routeur exécute ensuite une requête paramétrée prédéfinie et limitée.

Les réponses proviennent exclusivement d’objets autorisés et distinguent les faits serveur des indisponibilités. Une demande ambiguë produit une demande de précision. Les liens sont construits à partir d’un préfixe local contrôlé et d’un identifiant déjà autorisé.

Les motifs de prompt injection, SQL, secrets, URL ou recherche d’un autre utilisateur sont refusés avant toute consultation. Les requêtes gestionnaire sensibles sont auditées uniquement avec l’intention et le nombre de résultats, jamais avec le texte complet, un token ou des coordonnées.

Le français est le fallback; les réponses et libellés essentiels existent en anglais. L’intégration frontend rend la réponse avec `textContent`.
