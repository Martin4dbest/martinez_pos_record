import hashlib
from fastapi import HTTPException
from database import get_db

# -----------------------------
# Password Hashing (SHA-256)
# -----------------------------
def hash_password(password: str):
    """
    Hash a password using SHA-256.
    """
    password = password.strip()
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str):
    """
    Verify a password against its SHA-256 hash.
    """
    return hashlib.sha256(password.strip().encode()).hexdigest() == hashed

# -----------------------------
# Admin Verification
# -----------------------------

def verify_admin(user_id: int):
    """
    Check if user is admin. Raises 401 if not.
    """
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT role FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()

        if not user or user[0] != "admin":
            raise HTTPException(status_code=401, detail="Admin access required")

        return user_id
    finally:
        cur.close()
        conn.close()
