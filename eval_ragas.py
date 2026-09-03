# eval_ragas.py
import requests

questions = [
    "Que faire avec une pile usagée ?",
    "Quels sont les acteurs du recyclage à Douala ?",
    "Comment composter les restes de nourriture ?",
    "Où vendre le plastique à Douala ?"
]

for q in questions:
    response = requests.get(f"http://127.0.0.1:8000/api/v1/chatbot/ask?question={q}")
    data = response.json()
    print(f"Q: {q}")
    print(f"R: {data.get('reponse', '')}")
    print("-" * 50)

