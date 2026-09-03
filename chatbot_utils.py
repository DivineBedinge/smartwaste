import psycopg2
import psycopg2.extras
import requests
import json
import os
from app.services.ai_runtime import get_cross_encoder, get_embedding_model
from database import get_db_connection
from redis_utils import (
    obtenir_reponse_cachee,
    enregistrer_reponse_cachee,
    obtenir_memoire_session,
    ajouter_message_session,
    obtenir_types_precedents
)

# ============================================================
# CHARGEMENT DES MODÈLES (avec fallback)
# ============================================================

# ============================================================
# FONCTIONS DE BASE
# ============================================================

def generer_embedding(texte: str):
    return get_embedding_model().encode(texte).tolist()

def recherche_rag(question_embedding, top_k=5):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, type_dechet, question, reponse, detail_technique,
               impact_environnement, methode_valorisation, contact_douala,
               conseil_pratique,
               1 - (embedding <=> %s::vector) AS similarite
        FROM chatbot_embeddings
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (question_embedding, question_embedding, top_k))
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

def construire_contexte(fiche, langue='fr'):
    return f"""
Type de déchet : {fiche['type_dechet']}
Réponse générale : {fiche['reponse']}
Détail technique : {fiche['detail_technique']}
Impact environnement : {fiche['impact_environnement']}
Valorisation : {fiche['methode_valorisation']}
Contact à Douala : {fiche['contact_douala']}
Conseil pratique : {fiche['conseil_pratique']}
"""

def appeler_llm(question, contexte, langue='fr'):
    system_prompt = f"""
[SYSTEM]
Tu es un assistant d'information convivial.
Réponds de manière simple, naturelle et chaleureuse.
N'utilise jamais de JSON, de listes à puces, ni de termes techniques.
Si tu ne sais pas, dis-le poliment.
Langue : {"français" if langue == 'fr' else "anglais"}.
Ne dévie pas du contexte fourni.

CONTEXTE :
{contexte}

QUESTION :
{question}

RÉPONSE :
"""
    try:
        reponse = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "qwen2.5:3b",
                "prompt": system_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.85,
                    "top_k": 30,
                    "repeat_penalty": 1.1,
                    "num_predict": 200
                }
            },
            timeout=180
        )
        if reponse.status_code == 200:
            data = reponse.json()
            texte = data.get("response", "").strip()
            if texte.startswith('{'):
                try:
                    parsed = json.loads(texte)
                    for cle in ['reponse', 'response', 'message', 'texte', 'answer']:
                        if cle in parsed and isinstance(parsed[cle], str):
                            return parsed[cle].strip()
                    for valeur in parsed.values():
                        if isinstance(valeur, str):
                            return valeur.strip()
                    return "Je n'ai pas cette information."
                except:
                    pass
            if not texte or "Je n'ai pas cette information" in texte:
                return "Je n'ai pas cette information."
            return texte
        else:
            return "Je ne peux pas générer une réponse pour le moment."
    except Exception:
        return "Je ne peux pas générer une réponse pour le moment."

def verifier_reponse(reponse_llm, contexte):
    mots_interdits = ['inventé', 'selon mes connaissances', 'je pense', 'peut-être']
    for mot in mots_interdits:
        if mot in reponse_llm.lower():
            return "Je n'ai pas cette information."
    return reponse_llm

def traduire_en_anglais(texte: str) -> str:
    """Traduit un texte en anglais en utilisant le LLM local (qwen2.5:3b)."""
    if not any(c in "éèêàôûïç" for c in texte.lower()):
        return texte

    prompt = f"""Tu es un traducteur professionnel.
    Traduis ce texte en anglais de manière fidèle et naturelle.
    Règles strictes :
    - Aucun mot français.
    - Aucun accent français (é, è, ê, à, ô, û, ï, ç).
    - Réponds UNIQUEMENT avec le texte traduit.
    - Si tu ne peux pas traduire, réponds exactement : "TRADUCTION_IMPOSSIBLE"

    Texte à traduire :
    {texte}

    Traduction anglaise :"""

    try:
        reponse = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "qwen2.5:3b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "top_p": 0.7, "top_k": 10, "num_predict": 500}
            },
            timeout=120
        )
        if reponse.status_code == 200:
            traduction = reponse.json().get("response", "").strip()
            if traduction and "TRADUCTION_IMPOSSIBLE" not in traduction and not any(c in "éèêàôûïç" for c in traduction.lower()):
                return traduction
            else:
                return texte
        else:
            return texte
    except Exception as e:
        print(f"⚠️ Erreur traduction LLM : {e}")
        return texte

# ============================================================
# NOUVELLE FONCTION : REFORMULATION HUMAINE
# ============================================================

def formuler_reponse_humaine(contenu: dict, langue: str = "fr") -> str:
    """
    Transforme une réponse structurée en phrase naturelle via LLM.
    Si le LLM échoue, retourne un texte de secours lisible.
    """
    # Construire un résumé textuel du contenu
    resume = ""
    if contenu.get("type_dechet"):
        resume += f"Type de déchet : {contenu['type_dechet']}. "
    if contenu.get("reponse"):
        resume += contenu["reponse"]
    if contenu.get("detail_technique"):
        resume += f" Détail : {contenu['detail_technique']}."
    if contenu.get("impact_environnement"):
        resume += f" Impact : {contenu['impact_environnement']}."
    if contenu.get("methode_valorisation"):
        resume += f" Valorisation : {contenu['methode_valorisation']}."
    if contenu.get("contact_douala"):
        resume += f" Contact : {contenu['contact_douala']}."
    if contenu.get("conseil_pratique"):
        resume += f" Conseil : {contenu['conseil_pratique']}."
    if contenu.get("points_proches"):
        pts = contenu["points_proches"]
        if pts:
            resume += " Points proches : " + ", ".join([p["nom"] for p in pts]) + "."

    # Si aucun contenu, renvoyer un message générique
    if not resume:
        return "Je n'ai pas d'informations à ce sujet."

    prompt = f"""
[SYSTEM]
Tu es un assistant convivial qui parle comme un humain.
Réponds de manière naturelle, simple et chaleureuse, en utilisant les informations ci-dessous.
Ne mentionne jamais de termes techniques (comme "type_dechet", "similarite").
Ne liste jamais de points sous forme de JSON ou de puces.
Réponds en une ou deux phrases fluides.
Langue : {"français" if langue == "fr" else "anglais"}.

INFORMATIONS :
{resume}

RÉPONSE :
"""
    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "qwen2.5:3b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "top_p": 0.85, "num_predict": 150}
            },
            timeout=60
        )
        if response.status_code == 200:
            texte = response.json().get("response", "").strip()
            if texte and "Je n'ai pas" not in texte and "TRADUCTION_IMPOSSIBLE" not in texte:
                return texte
    except Exception as e:
        print(f"⚠️ Erreur reformulation : {e}")

    # Fallback : template humain simple
    fallback = contenu.get("reponse", "")
    if contenu.get("conseil_pratique"):
        fallback += " " + contenu["conseil_pratique"]
    if contenu.get("points_proches"):
        pts = contenu["points_proches"]
        if pts:
            fallback += f" Les points de collecte les plus proches sont : " + ", ".join([p["nom"] for p in pts]) + "."
    return fallback.strip()

# ============================================================
# RAG HYBRIDE
# ============================================================

def recherche_vectorielle(question: str, top_k: int = 10):
    q_embedding = generer_embedding(question)
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, type_dechet, reponse, detail_technique,
               impact_environnement, methode_valorisation,
               contact_douala, conseil_pratique,
               1 - (embedding <=> %s::vector) AS score
        FROM chatbot_embeddings
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (q_embedding, q_embedding, top_k))
    results = cur.fetchall()
    cur.close()
    conn.close()
    for r in results:
        r['id'] = r.get('id', r.get('type_dechet', ''))
    return results

def recherche_bm25(question: str, top_k: int = 10):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_name = 'faq_entries'
        )
    """)
    faq_exists = cur.fetchone()['exists']
    
    if faq_exists:
        cur.execute("""
            SELECT id, question, reponse,
                   ts_rank(vecteur, plainto_tsquery('french', %s)) AS score
            FROM faq_entries
            WHERE vecteur @@ plainto_tsquery('french', %s)
            ORDER BY score DESC
            LIMIT %s
        """, (question, question, top_k))
    else:
        cur.execute("""
            SELECT id, question, reponse, 1.0 AS score
            FROM chatbot_embeddings
            WHERE question ILIKE %s OR reponse ILIKE %s
            LIMIT %s
        """, (f'%{question}%', f'%{question}%', top_k))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

def reciprocal_rank_fusion(list_a, list_b, k: int = 60):
    scores = {}
    for rank, item in enumerate(list_a):
        item_id = item.get('id', str(rank))
        scores[item_id] = scores.get(item_id, 0) + 1 / (k + rank + 1)
    for rank, item in enumerate(list_b):
        item_id = item.get('id', str(rank))
        scores[item_id] = scores.get(item_id, 0) + 1 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)

def rerank(question: str, chunks: list, top_k: int = 5):
    cross_encoder = get_cross_encoder()
    if not chunks or cross_encoder is None:
        return chunks[:top_k]
    pairs = [(question, chunk.get('reponse', '')) for chunk in chunks if chunk.get('reponse')]
    if not pairs:
        return chunks[:top_k]
    scores = cross_encoder.predict(pairs)
    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
    return [chunk for chunk, _ in ranked[:top_k]]

def generer_reponse_avec_contexte(question: str, contexte_chunks: list) -> str:
    contexte = "\n\n".join([c.get('reponse', '') for c in contexte_chunks if c.get('reponse')])
    prompt = f"""
[SYSTEM]
Tu es un assistant convivial.
Réponds de manière naturelle et fluide en utilisant uniquement le CONTEXTE ci-dessous.
Ne mentionne jamais de termes techniques.
Si tu ne sais pas, dis-le poliment.

CONTEXTE:
{contexte}

QUESTION:
{question}

RÉPONSE:
"""
    try:
        reponse = requests.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "qwen2.5:3b",
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "top_p": 0.85, "num_predict": 200}
            },
            timeout=180
        )
        if reponse.status_code == 200:
            return reponse.json().get("response", "Je n'ai pas compris.")
        else:
            return "Je ne peux pas générer une réponse pour le moment."
    except Exception:
        return "Je ne peux pas générer une réponse pour le moment."
