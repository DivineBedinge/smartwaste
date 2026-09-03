from deep_translator import GoogleTranslator
from database import get_db_connection
import time

conn = get_db_connection()
cur = conn.cursor()

# Récupérer toutes les fiches
cur.execute("SELECT id, reponse, detail_technique, impact_environnement, methode_valorisation, contact_douala, conseil_pratique FROM chatbot_embeddings")
rows = cur.fetchall()

for row in rows:
    id_fiche = row[0]
    champs = row[1:]  # reponse, detail_technique, impact, methode, contact, conseil
    
    traductions = []
    for champ in champs:
        if champ:
            try:
                trad = GoogleTranslator(source='fr', target='en').translate(champ)
                traductions.append(trad if trad else champ)
            except:
                traductions.append(champ)  # si échec, on garde le texte original
        else:
            traductions.append(None)
        time.sleep(0.1)  # respecter la limite
    
    cur.execute("""
        UPDATE chatbot_embeddings SET
        reponse_en = %s,
        detail_technique_en = %s,
        impact_environnement_en = %s,
        methode_valorisation_en = %s,
        contact_douala_en = %s,
        conseil_pratique_en = %s
        WHERE id = %s
    """, (*traductions, id_fiche))
    print(f"✅ Fiche {id_fiche} traduite")

conn.commit()
cur.close()
conn.close()
print("Toutes les fiches sont traduites en anglais.")