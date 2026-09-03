# router.py
import re

def is_faq_question(question: str) -> bool:
    """
    Détecte si la question est une FAQ (simple, courte, avec mots-clés génériques).
    """
    faq_keywords = ['acteurs', 'prix', 'réglementation', 'loi', 'recyclage', 'douala', 'coût', 'tarif']
    tokens = question.lower().split()
    if len(tokens) < 12:  # Questions courtes
        for kw in faq_keywords:
            if kw in question.lower():
                return True
    return False