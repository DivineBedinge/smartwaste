# =====================================================
# CHATBOT NLP - SmartWaste CM+
# Gère : Français, Anglais, Camfranglais
# =====================================================

from rapidfuzz import fuzz, process
from langdetect import detect
import re
import unicodedata

# =====================================================
# 1. DICTIONNAIRE CAMFRANGLAIS
# =====================================================

CAMFRANGLAIS = {
    # Salutations
    "on dit quoi": "bonjour",
    "ca dit quoi": "bonjour",
    "salut": "bonjour",
    "hello": "bonjour",
    "hi": "bonjour",
    "good morning": "bonjour",
    "bonsoir": "bonsoir",
    
    # Questions courantes
    "komen": "comment",
    "koment": "comment",
    "koman": "comment",
    "comment on fait": "comment faire",
    "c'est comment": "comment",
    "ca fait comment": "comment faire",
    "how for do": "comment faire",
    "how": "comment",
    
    # Actions
    "fer": "faire",
    "fere": "faire",
    "do": "faire",
    "make": "faire",
    "recyclé": "recycler",
    "recycle": "recycler",
    "recycler": "recycler",
    "recycling": "recycler",
    "valorise": "valoriser",
    "valorisation": "valoriser",
    "vendre": "vendre",
    "sale": "vendre",
    "sell": "vendre",
    "jeter": "jeter",
    "jete": "jeter",
    "throw": "jeter",
    "throw away": "jeter",
    "dispose": "jeter",
    
    # Déchets
    "plastik": "plastique",
    "plastiq": "plastique",
    "plastic": "plastique",
    "bouteil": "bouteille",
    "bottle": "bouteille",
    "canete": "canette",
    "canette": "canette",
    "can": "canette",
    "alu": "aluminium",
    "aluminium": "aluminium",
    "aluminum": "aluminium",
    "verre": "verre",
    "glass": "verre",
    "papier": "papier",
    "paper": "papier",
    "carton": "carton",
    "cardboard": "carton",
    "pile": "pile",
    "batterie": "batterie",
    "battery": "batterie",
    "dechet": "dechet",
    "waste": "dechet",
    "garbage": "dechet",
    "trash": "dechet",
    "ordure": "dechet",
    
    # Argent
    "prix": "prix",
    "price": "prix",
    "combien": "combien",
    "how much": "combien",
    "argent": "argent",
    "money": "argent",
    "gagner": "gagner",
    "earn": "gagner",
    "gain": "gagner",
    "cout": "prix",
    "cost": "prix",
    
    # Lieux
    "ou": "ou",
    "where": "ou",
    "point": "point",
    "centre": "centre",
    "center": "centre",
    "depot": "depot",
    "marché": "marche",
    "marche": "marche",
    "market": "marche",
    
    # Expressions
    "je veux savoir": "comment",
    "i want to know": "comment",
    "dis moi": "expliquer",
    "tell me": "expliquer",
    "explique moi": "expliquer",
    "aide moi": "aider",
    "help me": "aider",
    "stp": "s'il te plait",
    "svp": "s'il vous plait",
    "please": "s'il vous plait",
    
    # Mots de liaison
    "pr": "pour",
    "pour": "pour",
    "for": "pour",
    "avec": "avec",
    "with": "avec",
    "mon": "mon",
    "my": "mon",
    "mes": "mes",
    "dans": "dans",
    "in": "dans",
    "a": "a",
    "at": "a",
}

# =====================================================
# 2. LISTE DES MOTS IMPORTANTS
# =====================================================

TYPES_DECHETS = [
    'plastique', 'aluminium', 'verre', 'papier', 'carton',
    'organique', 'batterie', 'ferraille', 'metal', 'dechet'
]

ACTIONS = [
    'recycler', 'vendre', 'jeter', 'valoriser', 'composter',
    'gagner', 'acheter', 'deposer'
]

QUARTIERS_DOUALA = [
    'Bonanjo', 'Bonapriso', 'Akwa', 'Joss', 'Deido', 'Bonamouti',
    'Njo-Njo', 'Carrefour Ideal', 'New Bell', 'Nkololoun', 'Congo',
    'Babylone', 'Youpwe', 'Kassalafam', 'Lagos Market', 'Bassa',
    'Logbaba', 'Ndogbati', 'Ndogpassi', 'Nyala', 'Japoma', 'Nylon',
    'Tergal', 'Cite des Palmiers', 'PK8', 'PK14', 'Logbessou',
    'Nkolbong', 'Brazzaville', 'Bonassama', 'Bonandale', 'Sodiko',
    'Mambanda', 'Grand Hangar', 'Ndobo', 'Boongo', 'Quartier Bilingue',
    'Bonamatoumbe', 'Bonaberi Rail', 'PK10', 'PK20', 'Mobile Guinness',
    'Bonamoussadi', 'Makepe', 'Logpom', 'Bepanda', 'Cite SIC',
    'Universite', 'Yassa', 'Kotto', 'Beedi', 'Lendi', 'Ndogbong',
    'Malangue', 'Manoka', 'Dahomey', 'Cap Cameroun', 'Bikoro'
]

# =====================================================
# 3. FONCTIONS NLP
# =====================================================

def normaliser_texte(texte: str) -> str:
    """
    Normalise le texte : minuscules, sans accents, sans ponctuation.
    """
    texte = texte.lower()
    texte = ''.join(c for c in unicodedata.normalize('NFKD', texte) 
                    if not unicodedata.combining(c))
    texte = re.sub(r'[^\w\s]', ' ', texte)
    texte = re.sub(r'\s+', ' ', texte).strip()
    return texte


def corriger_camfranglais(texte: str) -> str:
    """
    Corrige les expressions camfranglaises et les fautes.
    """
    texte_normalise = normaliser_texte(texte)
    
    # Remplacer les expressions camfranglaises
    for expression, correction in CAMFRANGLAIS.items():
        if expression in texte_normalise:
            texte_normalise = texte_normalise.replace(expression, correction)
    
    # Corriger mot par mot avec rapidfuzz
    mots = texte_normalise.split()
    mots_corriges = []
    
    mots_connus = list(CAMFRANGLAIS.values()) + TYPES_DECHETS + ACTIONS
    
    for mot in mots:
        # Chercher la meilleure correspondance
        resultat = process.extractOne(mot, mots_connus, scorer=fuzz.ratio)
        
        if resultat and resultat[1] >= 80:
            mots_corriges.append(resultat[0])
        else:
            mots_corriges.append(mot)
    
    return ' '.join(mots_corriges)


def detecter_langue(texte: str) -> str:
    """
    Détecte la langue : 'fr', 'en', ou 'camfranglais'.
    """
    # Vérifier d'abord le camfranglais
    texte_normalise = normaliser_texte(texte)
    for expression in CAMFRANGLAIS.keys():
        if expression in texte_normalise:
            return 'camfranglais'
    
    # Sinon utiliser langdetect
    try:
        langue = detect(texte)
        if langue == 'fr':
            return 'fr'
        elif langue == 'en':
            return 'en'
        else:
            return 'fr'
    except:
        return 'fr'


def extraire_mots_cles(texte: str) -> dict:
    """
    Extrait les mots-clés : type de déchet, action, quartier.
    """
    texte_corrige = corriger_camfranglais(texte)
    mots = texte_corrige.split()
    
    type_dechet = None
    action = None
    quartier = None
    
    for mot in mots:
        # Chercher le type de déchet
        if not type_dechet:
            resultat = process.extractOne(mot, TYPES_DECHETS, scorer=fuzz.ratio)
            if resultat and resultat[1] >= 80:
                type_dechet = resultat[0]
        
        # Chercher l'action
        if not action:
            resultat = process.extractOne(mot, ACTIONS, scorer=fuzz.ratio)
            if resultat and resultat[1] >= 80:
                action = resultat[0]
    
    # Chercher le quartier dans le texte original
    texte_normalise = normaliser_texte(texte)
    for q in QUARTIERS_DOUALA:
        q_normalise = normaliser_texte(q)
        if q_normalise in texte_normalise:
            quartier = q
            break
    
    return {
        "type_dechet": type_dechet,
        "action": action,
        "quartier": quartier,
        "texte_corrige": texte_corrige
    }


def detecter_intention(mots_cles: dict) -> str:
    """
    Détecte l'intention de l'utilisateur.
    """
    if mots_cles["action"] in ["vendre", "gagner", "prix", "combien", "argent"]:
        return "demande_prix"
    elif mots_cles["action"] in ["jeter", "deposer"]:
        return "trouver_point_collecte"
    elif mots_cles["action"] in ["recycler", "valoriser", "composter"]:
        return "demande_valorisation"
    elif mots_cles["quartier"]:
        return "trouver_point_collecte"
    else:
        return "information_generale"