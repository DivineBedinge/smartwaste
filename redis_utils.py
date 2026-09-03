import redis
import json
import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)

def obtenir_reponse_cachee(question: str):
    """Récupère une réponse mise en cache pour une question."""
    key = f"chatbot_cache:{question.lower().strip()}"
    data = redis_client.get(key)
    if data:
        return json.loads(data)
    return None

def enregistrer_reponse_cachee(question: str, reponse: dict, ttl: int = 3600):
    """Enregistre une réponse dans le cache Redis."""
    key = f"chatbot_cache:{question.lower().strip()}"
    redis_client.setex(key, ttl, json.dumps(reponse, ensure_ascii=False))

def obtenir_memoire_session(session_id: str, max_messages: int = 20):
    """Récupère les derniers messages d'une session."""
    key = f"session:{session_id}:messages"
    messages = redis_client.lrange(key, 0, -1)
    messages = [json.loads(m) for m in messages][-max_messages:]
    return messages

def ajouter_message_session(session_id: str, role: str, content: str, type_dechets: list = None):
    """Ajoute un message à la session, et si type_dechets est fourni, met à jour les types précédents."""
    key = f"session:{session_id}:messages"
    message = {
        "role": role,
        "content": content,
        "type_dechets": type_dechets or []
    }
    redis_client.rpush(key, json.dumps(message, ensure_ascii=False))
    redis_client.ltrim(key, -50, -1)  # garde les 50 derniers

    # Mettre à jour la liste des types précédents
    if type_dechets:
        types_key = f"session:{session_id}:types"
        for t in type_dechets:
            # Éviter les doublons (on garde les 10 plus récents)
            redis_client.rpush(types_key, t)
        redis_client.ltrim(types_key, -10, -1)

def obtenir_types_precedents(session_id: str) -> list:
    """Récupère les types de déchets mentionnés dans les messages précédents."""
    types_key = f"session:{session_id}:types"
    types = redis_client.lrange(types_key, 0, -1)
    # Dédoublonner en conservant l'ordre
    seen = []
    for t in types:
        if t not in seen:
            seen.append(t)
    return seen