import requests

url = "http://127.0.0.1:8000/api/v1/chatbot/ask"

tests = [
    {"question": "what to do with old chair", "attendu": "encombrant"},
    {"question": "qnd for the can", "attendu": "metal"},
    {"question": "et les veilles de bananes", "attendu": "biological"},
    {"question": "And for batteries?", "attendu": "battery"},
    {"question": "ce koi le pil", "attendu": "battery"},
    {"question": "Komen recycler le plastik?", "attendu": "plastic"},
]

for test in tests:
    response = requests.get(url, params={"question": test["question"]})
    data = response.json()
    
    # Récupérer le type depuis la liste types_detectes ou reponses
    types = data.get("types_detectes", [])
    if types:
        type_det = types[0]
    else:
        type_det = data.get("type_dechet", "None")
    
    statut = "✅" if type_det == test["attendu"] else "❌"
    print(f"{statut} {test['question']} → {type_det} (attendu: {test['attendu']})")