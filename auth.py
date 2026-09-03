from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import psycopg2
import psycopg2.extras
from core.security import hash_password, verify_password, create_access_token, decode_token
from database import get_db_connection
from core.policy import Role

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

security = HTTPBearer()

class UserRegister(BaseModel):
    email: str
    password: str
    arrondissement: str = None

class UserLogin(BaseModel):
    email: str
    password: str

@router.post("/register")
def register(user: UserRegister):
    """Inscription d'un nouvel utilisateur."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT id FROM users WHERE email = %s", (user.email,))
    if cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(400, "Cet email est déjà utilisé")
    
    hashed = hash_password(user.password)
    
    role = Role.CITOYEN.value
    cur.execute("""
        INSERT INTO users (email, password_hash, role, arrondissement)
        VALUES (%s, %s, %s, %s)
        RETURNING id
    """, (user.email, hashed, role, user.arrondissement))
    
    user_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    
    token = create_access_token(user_id, role)
    
    return {
        "id": user_id,
        "email": user.email,
        "role": role,
        "arrondissement": user.arrondissement,
        "access_token": token,
        "token_type": "bearer"
    }

@router.post("/login")
def login(user: UserLogin):
    """Connexion d'un utilisateur."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cur.execute("""
        SELECT id, email, password_hash, role, arrondissement 
        FROM users 
        WHERE email = %s
    """, (user.email,))
    user_data = cur.fetchone()
    cur.close()
    conn.close()
    
    if not user_data:
        raise HTTPException(401, "Email ou mot de passe incorrect")
    
    if not verify_password(user.password, user_data["password_hash"]):
        raise HTTPException(401, "Email ou mot de passe incorrect")
    
    token = create_access_token(user_data["id"], user_data["role"])
    
    return {
        "id": user_data["id"],
        "email": user_data["email"],
        "role": user_data["role"],
        "arrondissement": user_data["arrondissement"],
        "access_token": token,
        "token_type": "bearer"
    }

@router.get("/me")
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Récupère l'utilisateur connecté à partir du token."""
    token = credentials.credentials
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(401, "Token invalide ou expiré")
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, email, role, arrondissement 
        FROM users 
        WHERE id = %s
    """, (payload["user_id"],))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if not user:
        raise HTTPException(401, "Utilisateur non trouvé")
    
    return user