# insert_all_fiches.py
from sentence_transformers import SentenceTransformer
from database import get_db_connection

model = SentenceTransformer('all-MiniLM-L6-v2')

fiches = [
    {
        "type_dechet": "battery",
        "question": "Que faire avec une pile usagée ?",
        "reponse": "Les piles ne se jettent jamais à la poubelle. Elles contiennent des métaux lourds qui polluent durablement.",
        "detail_technique": "Une pile convertit l'énergie chimique en électricité grâce à une anode, une cathode et un électrolyte. Elle contient du zinc, du manganèse, du lithium ou du cadmium selon le type.",
        "impact_environnement": "Jetée dans la nature, la pile se corrode et libère des métaux lourds (mercure, plomb, cadmium) qui contaminent les sols et les nappes phréatiques. Brûlée, elle dégage des gaz toxiques. Ces substances provoquent des troubles neurologiques et rénaux.",
        "methode_valorisation": "Déposer les piles usagées dans un point de collecte DEEE. Les métaux sont extraits et réutilisés.",
        "contact_douala": "EcoCollect (centres de tri agréés) ; NAMé Recycling (Zone industrielle) - +237 6 94 01 10 87.",
        "conseil_pratique": "Stockez les piles dans un bocal en verre au sec, puis déposez-les lors de votre prochain passage en ville."
    },
    {
        "type_dechet": "biological",
        "question": "Que faire avec les restes de nourriture et déchets organiques ?",
        "reponse": "Les déchets organiques (restes de nourriture, épluchures, feuilles) se compostent facilement et deviennent un engrais naturel.",
        "detail_technique": "La décomposition est effectuée par des micro-organismes (bactéries, champignons) en présence d'oxygène. Le compostage transforme la matière organique en humus riche en nutriments.",
        "impact_environnement": "En décharge, les déchets organiques fermentent sans oxygène et produisent du méthane, un gaz à effet de serre 25 fois plus puissant que le CO₂. Ils attirent aussi les rats et contaminent les eaux.",
        "methode_valorisation": "Compostage domestique ou communautaire. À Douala, certains quartiers ont des composteurs collectifs (ex. Douala Clean City).",
        "contact_douala": "Douala Clean City (CUD) ; associations de quartier.",
        "conseil_pratique": "Utilisez un vieux bidon percé, alternez déchets verts (épluchures) et déchets bruns (feuilles mortes, carton). Retournez chaque semaine."
    },
    {
        "type_dechet": "cardboard",
        "question": "Que faire avec le carton ?",
        "reponse": "Le carton se recycle et se revend aux récupérateurs. Il peut aussi servir de matière brune pour le compost.",
        "detail_technique": "Le carton est fabriqué à partir de fibres de bois. Il est recyclable en pâte à papier pour fabriquer de nouveaux emballages.",
        "impact_environnement": "Jeter le carton à la poubelle augmente le volume des déchets et le gaspillage de fibres. Sa décomposition lente libère du méthane en décharge.",
        "methode_valorisation": "Revente aux récupérateurs informels (50 FCFA/kg environ), recyclage, compostage (carton brun non imprimé).",
        "contact_douala": "EcoCollect, récupérateurs des marchés (Bepanda, Ndokoti, Central).",
        "conseil_pratique": "Pliez à plat, gardez au sec, regroupez pour la revente."
    },
    {
        "type_dechet": "clothes",
        "question": "Que faire avec les vieux vêtements ?",
        "reponse": "Les vêtements usagés se donnent, se réutilisent ou se transforment en chiffons, sacs, ou rembourrage.",
        "detail_technique": "Le textile est majoritairement composé de coton (fibres végétales) ou de fibres synthétiques (plastique). Le coton est compostable, le synthétique met des centaines d'années à se dégrader.",
        "impact_environnement": "Jeter les vêtements augmente les déchets et le gaspillage de ressources (eau, énergie). La production textile est très polluante.",
        "methode_valorisation": "Don à des associations, revente dans les marchés de friperie, transformation en chiffons.",
        "contact_douala": "Marchés de friperie (Marché Central, New Bell), associations caritatives.",
        "conseil_pratique": "Lavez et pliez les vêtements réutilisables. Donnez-les ou revendez-les plutôt que de les jeter."
    },
    {
        "type_dechet": "glass",
        "question": "Que faire avec les bouteilles en verre ?",
        "reponse": "Le verre se recycle à l'infini. À Douala, certaines brasseries et récupérateurs rachètent les bouteilles consignées.",
        "detail_technique": "Le verre est fabriqué à partir de sable, de soude et de calcaire. Il fond à haute température et peut être refondu sans perte de qualité.",
        "impact_environnement": "Le verre abandonné dans la nature ne se décompose pas et présente un danger (coupures). Sa production consomme beaucoup d'énergie.",
        "methode_valorisation": "Consigne (brasseries), revente aux récupérateurs, recyclage.",
        "contact_douala": "Brasseries (SABC), dépôts de boissons, récupérateurs.",
        "conseil_pratique": "Rincez les bouteilles, gardez-les entières, regroupez-les pour la consigne ou la revente."
    },
    {
        "type_dechet": "metal",
        "question": "Que faire avec les métaux (canettes, ferraille, fer) ?",
        "reponse": "Les métaux se recyclent très bien et sont recherchés par les récupérateurs. L'aluminium et le fer se revendent au kilo.",
        "detail_technique": "L'aluminium est léger et recyclable sans perte de qualité. Le fer est séparé par aimant dans les centres de tri.",
        "impact_environnement": "Extraire les métaux vierges est très énergivore et polluant. Le recyclage économise jusqu'à 95% d'énergie.",
        "methode_valorisation": "Revente aux ferrailleurs (100-200 FCFA/kg selon le métal), dépôt dans les centres de tri.",
        "contact_douala": "EcoCollect, ferrailleurs de Bonabéri, Ndokoti.",
        "conseil_pratique": "Écrasez les canettes, regroupez les métaux propres, vendez-les au kilo."
    },
    {
        "type_dechet": "paper",
        "question": "Que faire avec le papier ?",
        "reponse": "Le papier se recycle ou se composte s'il n'est pas souillé par des produits toxiques.",
        "detail_technique": "Le papier est composé de fibres de cellulose. Il peut être recyclé en pâte à papier, mais la qualité diminue à chaque cycle.",
        "impact_environnement": "La production de papier consomme du bois et de l'eau. Le jeter en décharge génère du méthane.",
        "methode_valorisation": "Recyclage (50 FCFA/kg), compostage (papier non imprimé).",
        "contact_douala": "Récupérateurs, EcoCollect.",
        "conseil_pratique": "Séparez le papier propre du papier souillé. Regroupez-le pour la revente."
    },
    {
        "type_dechet": "plastic",
        "question": "Que faire avec les bouteilles et sachets plastiques ?",
        "reponse": "Les plastiques se revendent aux récupérateurs (75 FCFA/kg pour le PET). Certains sont recyclés localement.",
        "detail_technique": "Le plastique est un polymère issu du pétrole. Il met plusieurs centaines d'années à se dégrader. Le PET (bouteilles) est recyclable, les sachets le sont difficilement.",
        "impact_environnement": "Le plastique abandonné obstrue les drains, provoque des inondations, pollue l'océan et tue la faune. Brûlé, il libère des dioxines cancérigènes.",
        "methode_valorisation": "Revente aux récupérateurs, recyclage (NAMé Recycling), réutilisation.",
        "contact_douala": "NAMé Recycling (+237 6 94 01 10 87), EcoCollect, récupérateurs des marchés.",
        "conseil_pratique": "Rincez, écrasez les bouteilles, regroupez-les. Évitez les sachets à usage unique."
    },
    {
        "type_dechet": "shoes",
        "question": "Que faire avec les vieilles chaussures ?",
        "reponse": "Les chaussures usagées peuvent être réparées, données ou recyclées. Certaines associations les collectent.",
        "detail_technique": "Les chaussures sont composées de cuir, caoutchouc, tissu, plastique. Difficiles à recycler en raison de la mixité des matériaux.",
        "impact_environnement": "Jeter les chaussures augmente les déchets. Le caoutchouc et le synthétique mettent des siècles à se dégrader.",
        "methode_valorisation": "Réparation (cordonnerie), don, revente en friperie.",
        "contact_douala": "Marchés de friperie, cordonniers locaux.",
        "conseil_pratique": "Réparez si possible. Sinon donnez les paires encore utilisables."
    },
    {
        "type_dechet": "trash",
        "question": "Que faire avec les déchets non recyclables ?",
        "reponse": "Ces déchets doivent être mis dans la poubelle ordinaire. Ils seront acheminés en décharge par Hysacam ou Genelcam.",
        "detail_technique": "Il s'agit de déchets souillés, mélangés ou sans filière de valorisation (ex. emballages gras, textiles déchirés, vaisselle cassée).",
        "impact_environnement": "Ces déchets en décharge génèrent du méthane et peuvent contaminer les sols. Il faut donc en réduire la quantité.",
        "methode_valorisation": "Aucune valorisation directe. Réduction à la source : achetez en vrac, évitez les produits jetables.",
        "contact_douala": "Hysacam, Genelcam (collecte municipale ou privée).",
        "conseil_pratique": "Avant de jeter, demandez-vous si l'objet peut être réparé, donné ou recyclé. Réduire est la meilleure valorisation."
    }
]

conn = get_db_connection()
cur = conn.cursor()

for fiche in fiches:
    texte_complet = " ".join([
        fiche["type_dechet"],
        fiche["question"],
        fiche["reponse"],
        fiche["detail_technique"],
        fiche["impact_environnement"],
        fiche["methode_valorisation"],
        fiche["contact_douala"],
        fiche["conseil_pratique"]
    ])
    embedding = model.encode(texte_complet).tolist()
    
    cur.execute("""
        INSERT INTO chatbot_embeddings 
        (type_dechet, question, reponse, detail_technique, impact_environnement, 
         methode_valorisation, contact_douala, conseil_pratique, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        fiche["type_dechet"], fiche["question"], fiche["reponse"],
        fiche["detail_technique"], fiche["impact_environnement"],
        fiche["methode_valorisation"], fiche["contact_douala"],
        fiche["conseil_pratique"], embedding
    ))

conn.commit()
cur.close()
conn.close()
print(f"✅ {len(fiches)} fiches insérées avec embeddings.")