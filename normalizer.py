import re
import unicodedata
from rapidfuzz import fuzz, process
from langdetect import detect

MOTS_IMPORTANTS = [
    # Français
    'plastique', 'bouteille', 'recycler', 'compost', 'pile',
    'batterie', 'metal', 'verre', 'papier', 'carton', 'dechet',
    'organique', 'poubelle', 'jeter', 'valoriser', 'sachet',
    'canette', 'nourriture', 'reste', 'epluchure', 'vetement',
    'chaussure', 'societe', 'usine', 'entreprise', 'recuperateur',
    'prix', 'vendre', 'gagner', 'argent', 'point', 'collecte',
    'chaise', 'meuble', 'table', 'matelas', 'armoire', 'fauteuil',
    'electromenager', 'frigo', 'television',
    'banane', 'bananes', 'cheveu', 'cheveux', 'peau', 'épluchure',
    'can', 'canette', 'canettes',
    # Anglais
    'plastic', 'bottle', 'recycle', 'compost', 'battery',
    'metal', 'glass', 'paper', 'cardboard', 'waste',
    'organic', 'trash', 'throw', 'reuse', 'reduce',
    'can', 'food', 'leftover', 'peel', 'clothes', 'shoes',
    'company', 'factory', 'price', 'sell', 'money',
    'chair', 'furniture', 'mattress', 'fridge',
    # Fruits / légumes / pourriture
    'ananas', 'pineapple', 'pomme', 'apple', 'fruit', 'legume',
    'vegetable', 'rotten', 'pourri', 'pourriture',
    # Camfranglais / expressions
    'komen', 'comment', 'on dit quoi', 'comment on fait',
    'je veux savoir', 'c\'est comment', 'ou on peut',
    'how for do', 'where for throw', 'what is', 'i want',
    'yo', 'wesh', 'salam', 'coucou', 'moyo', 'frero', 'camarade', 'pote', 'ami'
]

CAMFRANGLAIS = {
    "on dit quoi": "bonjour",
    "comment on fait": "comment faire",
    "c'est comment": "comment",
    "ou on peut": "où peut-on",
    "how for do": "comment faire",
    "where for throw": "où jeter",
    "what is": "qu'est-ce que",
    "i want": "je veux",
    "i don't know": "je ne sais pas",
}

def normaliser_texte(texte: str) -> str:
    texte = texte.lower()
    texte = unicodedata.normalize('NFKD', texte)
    texte = ''.join(c for c in texte if not unicodedata.combining(c))
    texte = re.sub(r'[^\w\s]', ' ', texte)
    texte = re.sub(r'\s+', ' ', texte).strip()
    return texte

def corriger_mot(mot: str) -> str:
    if mot in MOTS_IMPORTANTS:
        return mot
    resultat = process.extractOne(mot, MOTS_IMPORTANTS, scorer=fuzz.ratio)
    if resultat and resultat[1] >= 80:
        return resultat[0]
    return mot

def normaliser_et_corriger(texte: str) -> str:
    texte = normaliser_texte(texte)
    for expr, remplacement in CAMFRANGLAIS.items():
        texte = texte.replace(expr, remplacement)
    mots = texte.split()
    mots_corriges = [corriger_mot(m) for m in mots]
    return ' '.join(mots_corriges)

def detecter_langue(texte: str) -> str:
    """
    Détecte la langue (FR/EN) avec heuristiques pour phrases courtes.
    """
    if len(texte.strip()) < 10:
        mots_anglais = ['the', 'what', 'how', 'where', 'with', 'from', 'is', 'do']
        if any(mot in texte.lower() for mot in mots_anglais):
            return 'en'
        return 'fr'
    
    try:
        langue = detect(texte)
        if langue in ['fr', 'en']:
            return langue
        else:
            if any(mot in texte.lower() for mot in ['the', 'what', 'how', 'where', 'with']):
                return 'en'
            return 'fr'
    except:
        return 'fr'
    
def extraire_mots_cles(texte: str) -> list:
    texte_corrige = normaliser_et_corriger(texte)
    mots = texte_corrige.split()
    return [mot for mot in mots if mot in MOTS_IMPORTANTS]