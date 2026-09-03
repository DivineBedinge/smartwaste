from fastapi.testclient import TestClient
import os
from main import app

client = TestClient(app)
TEST_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "test-only-password")

# ========== Tests de base ==========

def test_health():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "SmartWaste CM+ API is running"

def test_login_admin():
    response = client.post("/api/v1/auth/login", json={
        "email": "admin@smartwaste.cm",
        "password": TEST_ADMIN_PASSWORD
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_register_agent():
    response = client.post("/api/v1/auth/register", json={
        "email": "agent_test@smartwaste.cm",
        "password": "test-only-agent-password",
        "role": "agent",
        "arrondissement": "Douala V"
    })
    assert response.status_code in (200, 400)  # 200 si créé, 400 si déjà existant

# ========== Chatbot ==========

def test_chatbot_reponse_plastique():
    response = client.get("/api/v1/chatbot/reponse", params={"question": "bouteille plastique"})
    assert response.status_code == 200
    assert "plastique" in response.json()["reponse"].lower()

def test_chatbot_ask_point_proche():
    response = client.get("/api/v1/chatbot/ask", params={
        "question": "point de collecte le plus proche",
        "lat": 4.0511,
        "lon": 9.7069
    })
    assert response.status_code == 200
    assert "points_proches" in response.json()

def test_point_collecte_proche():
    response = client.get("/api/v1/chatbot/point-proche", params={"lat": 4.0511, "lon": 9.7069})
    assert response.status_code == 200
    assert "points_proches" in response.json()

# ========== Signalements & workflow ==========

def test_create_signalement():
    # On utilise une petite image 1x1 (PNG)
    import base64
    image_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    image_bytes = base64.b64decode(image_b64)
    files = {"file": ("test.png", image_bytes, "image/png")}
    data = {"lat": 4.0511, "lon": 9.7069}
    response = client.post("/api/v1/signalements", files=files, data=data)
    assert response.status_code == 200
    assert "id" in response.json()

def test_optimisation_tournee_vrp():
    # Il faut des signalements existants, sinon retour "Pas assez de signalements"
    response = client.get("/api/v1/tournees/optimiser-vrp", params={
        "arrondissement": "Douala V",
        "nb_vehicules": 1,
        "capacite_vehicule": 1000,
        "max_signalements": 10
    }, headers={"Authorization": "Bearer " + get_token()})
    assert response.status_code in (200, 403)  # 200 si ok, 403 si pas admin

def get_token():
    response = client.post("/api/v1/auth/login", json={
        "email": "admin@smartwaste.cm",
        "password": TEST_ADMIN_PASSWORD
    })
    return response.json()["access_token"]