"""
enrichir_chatbot_knowledge.py
------------------------------------------------------------------
Peuplement enrichi de la base de connaissances du chatbot SmartWaste CM+.

Contexte :
- Couvre les 12 classes du dataset "Garbage Classification" prévu pour
  le réentraînement du modèle de vision (battery, biological, brown-glass,
  cardboard, clothes, green-glass, metal, paper, plastic, shoes, trash,
  white-glass).
- Chaque fiche est contextualisée pour Douala (économie informelle de
  la récupération, points de collecte réels identifiés lors des enquêtes,
  contraintes de connectivité).
- Un champ `mots_cles` (synonymes locaux / camfranglais) a été ajouté
  pour être exploité par normalizer.py (rapidfuzz + langdetect) afin
  d'améliorer la reconnaissance des requêtes citoyennes en français,
  anglais, ou camfranglais.

⚠️ Les prix de rachat NE SONT PAS codés en dur ici : ils sont gérés
dynamiquement via la table `prix_reference` (déjà peuplée avec les
prix officiels) et interrogés par l'endpoint /chatbot/prix. Chaque
fiche renvoie donc vers cette table plutôt que d'afficher un chiffre
qui deviendrait vite obsolète.
"""

from sentence_transformers import SentenceTransformer
from database import get_db_connection

model = SentenceTransformer('all-MiniLM-L6-v2')

# ------------------------------------------------------------------
# 1. Mise à jour du schéma : ajout de la colonne mots_cles si absente
# ------------------------------------------------------------------
SCHEMA_UPDATE_SQL = """
ALTER TABLE chatbot_embeddings
ADD COLUMN IF NOT EXISTS mots_cles TEXT[];
"""

# ------------------------------------------------------------------
# 2. Fiches enrichies (12 classes + encombrant)
# ------------------------------------------------------------------
fiches = [
    
        {
            "type_dechet": "dechet_capillaire",
        "mots_cles": [
            "meche", "mèche", "cheveux", "hair", "wicks", "extension",
            "postiche", "meches", "perruque", "greffon"
        ],
        "question": "Que faire avec de vieilles mèches ou cheveux ?",
        "reponse": (
            "Les mèches synthétiques ne sont pas recyclables mais peuvent être "
            "réutilisées si elles sont propres. Les cheveux naturels peuvent "
            "être donnés à des ateliers qui fabriquent des extensions, ou "
            "utilisés pour la fabrication de perruques."
        ),
        "detail_technique": (
            "Les mèches synthétiques sont composées de fibres de polyester ou "
            "d'acrylique, dérivées du pétrole. Les cheveux naturels sont des "
            "fibres protéinées qui se décomposent lentement mais peuvent être "
            "réutilisés en extension ou en rembourrage."
        ),
        "impact_environnement": (
            "Jetées dans la nature, les mèches synthétiques ne se dégradent "
            "pas et peuvent boucher les caniveaux. Les cheveux naturels "
            "peuvent contaminer le sol s'ils sont mélangés à des produits "
            "chimiques (teintures, produits coiffants)."
        ),
        "methode_valorisation": (
            "Don à des salons de coiffure, revente à des fabricants "
            "d'extensions, ou transformation en perruques. Sinon, élimination "
            "avec les déchets non recyclables."
        ),
        "contact_douala": (
            "Salons de coiffure du marché (Marché Central, New Bell), "
            "boutiques d'extensions capillaires, ateliers de fabrication de "
            "perruques."
        ),
        "conseil_pratique": (
            "Ne jetez jamais les mèches dans les caniveaux. Proposez-les à un "
            "salon de coiffure ou à une boutique d'extensions ; elles ont "
         "souvent une valeur de revente."
        )
    },
    {
        "type_dechet": "battery",
        "mots_cles": [
            "pile", "piles", "batterie", "battery", "accu", "accumulateur",
            "pile bouton", "pile electrique", "wata", "pile ya radio"
        ],
        "question": "Que faire avec une pile ou une batterie usagée ?",
        "reponse": (
            "Les piles et batteries ne se jettent jamais avec les ordures "
            "ménagères. Elles contiennent des métaux lourds qui polluent "
            "durablement le sol et l'eau."
        ),
        "detail_technique": (
            "Une pile convertit l'énergie chimique en électricité grâce à "
            "une anode, une cathode et un électrolyte. Selon le type, elle "
            "contient du zinc, du manganèse, du lithium, du nickel-cadmium "
            "ou du plomb (batteries de moto/véhicule)."
        ),
        "impact_environnement": (
            "Jetée dans la nature ou brûlée à l'air libre (pratique courante "
            "à Douala faute d'alternative), la pile libère des métaux lourds "
            "(mercure, plomb, cadmium) et des fumées toxiques. Ces substances "
            "contaminent les nappes phréatiques et provoquent des troubles "
            "neurologiques et rénaux à long terme."
        ),
        "methode_valorisation": (
            "Dépôt dans un point de collecte DEEE (Déchets d'Équipements "
            "Électriques et Électroniques). Les métaux sont extraits et "
            "réintroduits dans l'industrie."
        ),
        "contact_douala": (
            "NAMé Recycling (Zone industrielle) — +237 6 94 01 10 87 ; "
            "centres de tri agréés EcoCollect."
        ),
        "conseil_pratique": (
            "Gardez un petit bocal ou une boîte fermée pour stocker vos "
            "piles usagées à la maison, et déposez-les dès votre prochain "
            "passage près d'un point de collecte. Ne les brûlez jamais."
        ),
    },
    {
        "type_dechet": "biological",
        "mots_cles": [
            "reste de nourriture", "epluchure", "epluchures", "dechet organique",
            "biodegradable", "compost", "reste manger", "residus alimentaires",
            "food waste", "dechets de cuisine"
        ],
        "question": "Que faire avec des restes de nourriture ou déchets organiques ?",
        "reponse": (
            "Les déchets organiques (épluchures, restes de repas, feuilles) "
            "se compostent très facilement et représentent la meilleure "
            "valorisation possible pour ce type de déchet."
        ),
        "detail_technique": (
            "La décomposition est réalisée par des micro-organismes en "
            "présence d'oxygène (compostage aérobie). Le résultat est un "
            "humus riche en nutriments, utilisable comme engrais naturel."
        ),
        "impact_environnement": (
            "En décharge non contrôlée ou dans un dépôt sauvage, les déchets "
            "organiques se décomposent sans oxygène et produisent du méthane, "
            "un gaz à effet de serre bien plus puissant que le CO₂. Ils "
            "attirent aussi les rats et favorisent la stagnation d'eau, "
            "aggravant les risques d'inondation en saison des pluies."
        ),
        "methode_valorisation": (
            "Compostage domestique en bidon percé ou en fosse ; certains "
            "quartiers disposent de composteurs communautaires portés par "
            "des associations locales."
        ),
        "contact_douala": (
            "Associations de quartier et initiatives de salubrité "
            "communautaire (Douala Clean City) ; se renseigner auprès du "
            "chef de quartier."
        ),
        "conseil_pratique": (
            "Alternez déchets « verts » humides (épluchures) et déchets "
            "« bruns » secs (feuilles mortes, carton déchiré) dans votre "
            "composteur pour éviter les mauvaises odeurs. Ne jetez jamais "
            "ces déchets dans un caniveau : ils bouchent les drains."
        ),
    },
    {
        "type_dechet": "brown-glass",
        "mots_cles": [
            "bouteille brune", "bouteille de biere", "verre brun",
            "verre marron", "bouteille beer", "bouteille castel",
            "bouteille guinness"
        ],
        "question": "Que faire avec une bouteille en verre brun (bière) ?",
        "reponse": (
            "Le verre est recyclable à l'infini sans perte de qualité. Les "
            "bouteilles brunes (bière) doivent idéalement être triées "
            "séparément des verres transparents ou verts."
        ),
        "detail_technique": (
            "Le verre est fabriqué à partir de sable, de calcaire et de "
            "soude fondus à très haute température. La couleur brune "
            "provient d'oxydes de fer et de soufre ajoutés pour protéger "
            "le contenu (bière) de la lumière."
        ),
        "impact_environnement": (
            "Le verre mal jeté (fragments dans les rues, points d'eau) "
            "représente un risque de blessure important, notamment pour "
            "les enfants pieds nus et les récupérateurs informels. Il ne "
            "se dégrade quasiment jamais dans la nature."
        ),
        "methode_valorisation": (
            "Revente directe aux brasseries (Guinness Cameroun, SABC) qui "
            "réutilisent les bouteilles consignées, ou recyclage par fusion "
            "chez les récupérateurs de verre."
        ),
        "contact_douala": (
            "Dépôts-vente et cabarets qui reprennent les bouteilles "
            "consignées ; points de collecte NAMé Recycling pour le verre "
            "non consigné."
        ),
        "conseil_pratique": (
            "Ne cassez jamais une bouteille pour la jeter : une bouteille "
            "intacte a de la valeur en consigne, un fragment de verre n'en "
            "a plus et devient dangereux."
        ),
    },
    {
        "type_dechet": "cardboard",
        "mots_cles": [
            "carton", "boite en carton", "cartoon", "emballage carton",
            "carton box", "boite carton"
        ],
        "question": "Que faire avec un emballage en carton ?",
        "reponse": (
            "Le carton se recycle facilement s'il reste propre et sec. Il "
            "a une bonne valeur de revente auprès des récupérateurs."
        ),
        "detail_technique": (
            "Le carton est fabriqué à partir de fibres de cellulose issues "
            "du bois. Les fibres peuvent être réutilisées 5 à 7 fois avant "
            "de devenir trop courtes pour le recyclage."
        ),
        "impact_environnement": (
            "Un carton mouillé (souvent le cas en saison des pluies s'il "
            "traîne dans un dépôt sauvage) devient inutilisable pour le "
            "recyclage et se transforme en déchet organique qui pourrit. "
            "Jeté sec, il occupe un volume important inutilement."
        ),
        "methode_valorisation": (
            "Aplatir et regrouper les cartons pour la revente au poids "
            "auprès des récupérateurs, ou dépôt dans un point de collecte."
        ),
        "contact_douala": (
            "Récupérateurs de marché (Marché Central, Marché Sandaga) qui "
            "achètent le carton au kilo ; NAMé Recycling."
        ),
        "conseil_pratique": (
            "Retirez le scotch et les agrafes avant de plier le carton à "
            "plat. Protégez-le de la pluie en attendant la collecte : un "
            "carton sec vaut plus qu'un carton mouillé."
        ),
    },
    {
        "type_dechet": "clothes",
        "mots_cles": [
            "vetement", "habit", "vieux habit", "friperie", "clothes",
            "tissu", "linge usage", "sapes"
        ],
        "question": "Que faire avec de vieux vêtements ?",
        "reponse": (
            "Les vêtements en bon état peuvent être donnés ou revendus en "
            "friperie ; les tissus abîmés peuvent être transformés en "
            "chiffons de nettoyage."
        ),
        "detail_technique": (
            "Les textiles sont composés de fibres naturelles (coton) ou "
            "synthétiques (polyester, nylon). Les fibres synthétiques sont "
            "dérivées du pétrole et se dégradent très lentement."
        ),
        "impact_environnement": (
            "Brûler des vêtements synthétiques libère des fumées toxiques. "
            "Les textiles jetés dans la nature s'accumulent et bouchent les "
            "cours d'eau, contribuant aux inondations locales."
        ),
        "methode_valorisation": (
            "Don à des proches, revente au marché de la friperie (souvent "
            "appelé « soulala » ou « bend-skin » dans certains quartiers), "
            "ou transformation en chiffons pour ateliers mécaniques."
        ),
        "contact_douala": (
            "Marchés de friperie locaux ; associations caritatives de "
            "quartier pour les dons."
        ),
        "conseil_pratique": (
            "Lavez et pliez les vêtements avant de les donner : cela "
            "augmente fortement leurs chances d'être réutilisés plutôt que "
            "jetés."
        ),
    },
    {
        "type_dechet": "green-glass",
        "mots_cles": [
            "bouteille verte", "verre vert", "bouteille de vin",
            "bouteille malta", "bouteille sprite ancienne"
        ],
        "question": "Que faire avec une bouteille en verre vert ?",
        "reponse": (
            "Comme les autres verres, la bouteille verte se recycle très "
            "bien mais doit être triée séparément des verres bruns ou "
            "transparents pour une meilleure valorisation."
        ),
        "detail_technique": (
            "La coloration verte provient d'oxydes de chrome ou de fer "
            "présents dans le sable utilisé pour la fabrication."
        ),
        "impact_environnement": (
            "Comme tout verre, il ne se dégrade pratiquement jamais dans "
            "la nature et représente un risque de coupure important lorsqu'il "
            "est brisé et abandonné dans les zones de passage."
        ),
        "methode_valorisation": (
            "Consigne auprès des points de vente de boissons, ou revente "
            "au poids aux récupérateurs de verre."
        ),
        "contact_douala": (
            "Dépôts-vente de boissons ; NAMé Recycling pour le verre non "
            "consigné."
        ),
        "conseil_pratique": (
            "Regroupez vos bouteilles par couleur si possible : cela "
            "facilite le travail des récupérateurs et peut améliorer le "
            "prix de rachat."
        ),
    },
    {
        "type_dechet": "metal",
        "mots_cles": [
            "boite de sardine", "canette", "ferraille", "metal", "fer",
            "aluminium", "boite de conserve", "capsule", "cannette biere",
            "tole"
        ],
        "question": "Que faire avec une canette ou une boîte de conserve ?",
        "reponse": (
            "Le métal (aluminium, fer-blanc) est l'un des matériaux les "
            "plus recherchés par les récupérateurs à Douala car il a une "
            "bonne valeur de revente."
        ),
        "detail_technique": (
            "L'aluminium (canettes) et le fer-blanc (boîtes de conserve) "
            "sont des métaux recyclables à l'infini sans perte de qualité, "
            "contrairement à de nombreux plastiques."
        ),
        "impact_environnement": (
            "L'extraction minière de métaux neufs (bauxite pour "
            "l'aluminium) est très énergivore et polluante ; recycler un "
            "kilo de métal évite une extraction équivalente. Les objets "
            "métalliques abandonnés rouillent et peuvent contaminer les "
            "sols avec des résidus de peinture ou de revêtement."
        ),
        "methode_valorisation": (
            "Revente directe au poids auprès des ferrailleurs et "
            "récupérateurs informels, très présents dans les marchés et "
            "quartiers de Douala."
        ),
        "contact_douala": (
            "Ferrailleurs de quartier (souvent identifiables par leur "
            "charrette) ; NAMé Recycling pour les gros volumes."
        ),
        "conseil_pratique": (
            "Rincez les boîtes de conserve pour éviter les odeurs et les "
            "insectes, et écrasez les canettes pour gagner de la place en "
            "attendant la collecte."
        ),
    },
    {
        "type_dechet": "paper",
        "mots_cles": [
            "papier", "feuille", "journal", "cahier", "paper", "papie usage",
            "vieux journal", "feuille de cahier"
        ],
        "question": "Que faire avec du papier ou des vieux journaux ?",
        "reponse": (
            "Le papier propre et sec se recycle bien et peut être revendu "
            "au poids, comme le carton."
        ),
        "detail_technique": (
            "Comme le carton, le papier est fabriqué à partir de fibres de "
            "cellulose. Le papier peut être recyclé entre 4 et 6 fois avant "
            "que les fibres ne deviennent trop courtes."
        ),
        "impact_environnement": (
            "Le papier souillé (huile, nourriture) n'est plus recyclable "
            "et doit être traité comme déchet résiduel. Brûlé en grande "
            "quantité, il contribue à la pollution de l'air en zone urbaine "
            "dense."
        ),
        "methode_valorisation": (
            "Revente aux récupérateurs de papier/carton, ou réutilisation "
            "directe (emballage, cahier de brouillon)."
        ),
        "contact_douala": (
            "Récupérateurs de marché ; imprimeries locales qui reprennent "
            "parfois les chutes de papier."
        ),
        "conseil_pratique": (
            "Séparez le papier propre (journaux, cahiers) du papier "
            "souillé (papier alimentaire) : seul le premier a de la valeur."
        ),
    },
    {
        "type_dechet": "plastic",
        "mots_cles": [
            "sachet", "bouteille plastique", "plastic", "nylon", "sac plastique",
            "emballage plastique", "bouteille pet", "sachet noir",
            "sachet eau", "pure water"
        ],
        "question": "Que faire avec une bouteille ou un sachet en plastique ?",
        "reponse": (
            "Les bouteilles en plastique (PET) se recyclent bien et peuvent "
            "être revendues aux récupérateurs. Les sachets fins sont plus "
            "difficiles à valoriser et doivent être réduits à la source."
        ),
        "detail_technique": (
            "Le plastique est un polymère dérivé du pétrole. Le PET "
            "(bouteilles) est le plastique le plus facilement recyclable ; "
            "les sachets fins en polyéthylène basse densité sont peu "
            "rentables à recycler et sont souvent brûlés ou jetés."
        ),
        "impact_environnement": (
            "Les sachets plastiques bouchent les caniveaux et sont l'une "
            "des principales causes des inondations récurrentes à Douala "
            "en saison des pluies. Brûlé, le plastique libère des dioxines "
            "toxiques et cancérigènes."
        ),
        "methode_valorisation": (
            "Revente des bouteilles PET aux récupérateurs et à NAMé "
            "Recycling ; réutilisation des sachets solides pour d'autres "
            "usages avant élimination."
        ),
        "contact_douala": (
            "NAMé Recycling (+237 6 94 01 10 87) ; récupérateurs des "
            "marchés ; EcoCollect."
        ),
        "conseil_pratique": (
            "Rincez et écrasez les bouteilles pour gagner de la place. "
            "Évitez au maximum les sachets à usage unique lors de vos "
            "achats et privilégiez un sac réutilisable."
        ),
    },
    {
        "type_dechet": "shoes",
        "mots_cles": [
            "chaussure", "vieille chaussure", "sandale", "shoes", "basket",
            "godasse", "savate"
        ],
        "question": "Que faire avec de vieilles chaussures ?",
        "reponse": (
            "Les chaussures encore portables peuvent être données, "
            "réparées par un cordonnier, ou revendues en friperie. "
            "Les chaussures hors d'usage sont plus difficiles à valoriser."
        ),
        "detail_technique": (
            "Une chaussure combine souvent plusieurs matériaux difficiles "
            "à séparer : cuir ou synthétique, caoutchouc, mousse, textile, "
            "colle. Cette hétérogénéité rend le recyclage complexe."
        ),
        "impact_environnement": (
            "Les semelles en caoutchouc ou en mousse mettent plusieurs "
            "dizaines d'années à se dégrader dans la nature."
        ),
        "methode_valorisation": (
            "Réparation par un cordonnier de quartier (très courant à "
            "Douala et souvent moins cher qu'un rachat), don, ou revente "
            "en friperie."
        ),
        "contact_douala": (
            "Cordonniers de quartier ; marchés de friperie."
        ),
        "conseil_pratique": (
            "Avant de jeter une paire de chaussures, demandez conseil à un "
            "cordonnier : une simple réparation prolonge souvent sa durée "
            "de vie de plusieurs années."
        ),
    },
    {
        "type_dechet": "trash",
        "mots_cles": [
            "ordure", "dechet non recyclable", "poubelle", "trash",
            "dechet residuel", "couche bebe", "mouchoir", "emballage sale",
            "polystyrene"
        ],
        "question": "Que faire des déchets qui ne se recyclent pas ?",
        "reponse": (
            "Certains déchets (couches, mouchoirs, emballages souillés, "
            "polystyrène) ne sont pas recyclables et doivent être déposés "
            "dans le circuit de collecte classique, jamais brûlés ni jetés "
            "dans la nature."
        ),
        "detail_technique": (
            "Ces déchets sont soit composites (plusieurs matériaux "
            "inséparables), soit souillés par des matières organiques ou "
            "des produits chimiques, ce qui empêche tout recyclage rentable "
            "dans les conditions actuelles."
        ),
        "impact_environnement": (
            "Le brûlage à l'air libre, très répandu à Douala faute de "
            "collecte régulière, dégage des fumées toxiques dangereuses "
            "pour la santé respiratoire, en particulier chez les enfants. "
            "Le dépôt dans les caniveaux aggrave les risques d'inondation."
        ),
        "methode_valorisation": (
            "Aucune valorisation possible : ces déchets doivent être "
            "acheminés vers un site de traitement final (décharge "
            "contrôlée) via la collecte officielle."
        ),
        "contact_douala": (
            "Points de collecte officiels CUD / prestataires (Hysacam, "
            "Genelcam) ; signaler via l'application si aucun service de "
            "collecte n'existe dans votre quartier."
        ),
        "conseil_pratique": (
            "Ne brûlez jamais ces déchets et ne les jetez pas dans un "
            "caniveau. Si votre quartier n'a pas de collecte régulière, "
            "signalez-le via l'application pour qu'un point de collecte "
            "soit envisagé."
        ),
    },
    {
        "type_dechet": "encombrant",
        "mots_cles": [
            "congelateur", "refrigérateur", "electromenager", "frigo",
            "meuble", "matelas", "canapé", "armoire", "table", "chaise"
        ],
        "question": "Que faire avec un vieux congélateur ou réfrigérateur ?",
        "reponse": (
            "Les appareils électroménagers volumineux (congélateur, réfrigérateur) "
            "ne se jettent jamais dans les caniveaux ni dans la rue. Ils peuvent "
            "être confiés à des récupérateurs spécialisés ou déposés dans un point "
            "de collecte DEEE."
        ),
        "detail_technique": (
            "Un congélateur contient un circuit de réfrigération avec des gaz "
            "frigorigènes (fréon) et de l'huile, très polluants s'ils sont libérés. "
            "Il renferme aussi des métaux (acier, cuivre, aluminium) et des "
            "plastiques recyclables."
        ),
        "impact_environnement": (
            "Abandonné ou brûlé, un réfrigérateur relâche des gaz à effet de serre "
            "et des substances nocives qui détruisent la couche d'ozone et "
            "contaminent l'environnement."
        ),
        "methode_valorisation": (
            "Dépôt dans un centre de collecte DEEE, récupération par des ferrailleurs "
            "spécialisés, ou revente à des ateliers de réparation/récupération."
        ),
        "contact_douala": (
            "NAMé Recycling (Zone industrielle) — +237 6 94 01 10 87 ; "
            "centres de tri agréés EcoCollect."
        ),
        "conseil_pratique": (
            "Si l'appareil fonctionne encore, proposez-le d'abord à un réparateur "
            "ou revendez-le sur les marchés d'occasion avant de le confier à un "
            "récupérateur."
        ),
    },
    {
        "type_dechet": "white-glass",
        "mots_cles": [
            "bouteille transparente", "verre transparent", "verre blanc",
            "bouteille whisky", "bocal en verre", "pot en verre"
        ],
        "question": "Que faire avec une bouteille ou un bocal en verre transparent ?",
        "reponse": (
            "Le verre transparent (blanc) est le plus recherché pour le "
            "recyclage car il peut être réutilisé pour fabriquer tout type "
            "de nouveau verre, quelle que soit sa couleur finale."
        ),
        "detail_technique": (
            "Le verre transparent ne contient pas d'oxydes colorants "
            "ajoutés, ce qui en fait la matière première la plus polyvalente "
            "pour la refonte en verrerie."
        ),
        "impact_environnement": (
            "Comme tout verre, il ne se dégrade pas dans la nature et "
            "représente un risque de coupure s'il est brisé et abandonné."
        ),
        "methode_valorisation": (
            "Consigne auprès des points de vente, réutilisation comme "
            "bocal de conservation à la maison, ou revente aux "
            "récupérateurs de verre."
        ),
        "contact_douala": (
            "Dépôts-vente de boissons ; NAMé Recycling."
        ),
        "conseil_pratique": (
            "Un bocal en verre transparent bien lavé peut être réutilisé "
            "des années à la maison (conservation d'aliments, rangement) "
            "avant d'envisager son recyclage."
        ),
    },
]

# ------------------------------------------------------------------
# 3. Exécution : mise à jour du schéma puis insertion des fiches
# ------------------------------------------------------------------
conn = get_db_connection()
cur = conn.cursor()

cur.execute(SCHEMA_UPDATE_SQL)
conn.commit()

for fiche in fiches:
    # Le texte encodé inclut les mots_cles pour améliorer la recherche
    # sémantique (embedding), en plus du matching exact via normalizer.py
    texte_complet = " ".join(
        [str(v) for k, v in fiche.items() if k != "mots_cles"]
        + fiche["mots_cles"]
    )
    embedding = model.encode(texte_complet).tolist()

    cur.execute(
        """
        INSERT INTO chatbot_embeddings
        (type_dechet, mots_cles, question, reponse, detail_technique,
         impact_environnement, methode_valorisation, contact_douala,
         conseil_pratique, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            fiche["type_dechet"],
            fiche["mots_cles"],
            fiche["question"],
            fiche["reponse"],
            fiche["detail_technique"],
            fiche["impact_environnement"],
            fiche["methode_valorisation"],
            fiche["contact_douala"],
            fiche["conseil_pratique"],
            embedding,
        ),
    )

conn.commit()
cur.close()
conn.close()
print(f"{len(fiches)} fiches insérées avec succès (12 classes + encombrant).")