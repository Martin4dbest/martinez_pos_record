from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from database import get_db
from auth import hash_password, verify_password, verify_admin
import os

app = FastAPI()

# -----------------------------
# CORS Middleware
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================
# Pydantic Models
# =============================
class LoginRequest(BaseModel):
    username: str
    password: str

class TransactionRequest(BaseModel):
    user_id: int
    amount_withdrawn: float
    charge: float
    transaction_type: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "attendant"
    current_user_id: int

# ============================================================
# FRONTEND PATH
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Serve frontend folder for CSS/JS/images and HTML files
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")

# Serve index.html at root (works locally and in production)
@app.get("/")
def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# Serve dashboards explicitly
@app.get("/admin_dashboard.html")
def admin_dashboard():
    return FileResponse(os.path.join(FRONTEND_DIR, "admin_dashboard.html"))

@app.get("/sales.html")
def sales_dashboard():
    return FileResponse(os.path.join(FRONTEND_DIR, "sales.html"))

# ============================================================
# LOGIN
# ============================================================
@app.post("/login")
def login(req: LoginRequest):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, username, password, role FROM users WHERE username=%s",
        (req.username,)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if not user or not verify_password(req.password, user[2]):
        raise HTTPException(status_code=401, detail="Invalid login")

    return {
        "user_id": user[0],
        "username": user[1],
        "role": user[3]
    }

# ============================================================
# REGISTER (Admin Only)
# ============================================================
@app.post("/register")
def register_user(req: RegisterRequest):
    verify_admin(req.current_user_id)  # ensure only admin can register
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE username=%s", (req.username,))
    if cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = hash_password(req.password)
    cur.execute(
        "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
        (req.username, hashed_password, req.role)
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"message": f"User '{req.username}' registered successfully"}

# ============================================================
# TRANSACTIONS
# ============================================================
@app.post("/transactions")
def log_transaction(req: TransactionRequest):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO sales 
        (user_id, amount_withdrawn, charge, transaction_type, sales_date)
        VALUES (%s, %s, %s, %s, CURRENT_DATE)
    """, (
        req.user_id,
        req.amount_withdrawn,
        req.charge,
        req.transaction_type
    ))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Transaction recorded successfully"}

@app.get("/all_transactions")
def all_transactions():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT s.id,
               u.username,
               s.amount_withdrawn,
               s.charge,
               s.transaction_type,
               s.sales_date
        FROM sales s
        JOIN users u ON s.user_id = u.id
        ORDER BY s.id DESC
    """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id": r[0],
            "attendant_name": r[1],
            "amount_withdrawn": float(r[2]),
            "charge": float(r[3]),
            "transaction_type": r[4],
            "sales_date": str(r[5])
        }
        for r in rows
    ]

# ============================================================
# DASHBOARD STATS
# ============================================================
@app.get("/attendants_count")
def attendants_count():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE role='attendant'")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"count": count}

@app.get("/transactions_count")
def transactions_count():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sales")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"count": count}

@app.get("/total_sales")
def total_sales():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(amount_withdrawn + charge), 0) FROM sales")
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"total": float(total)}

# ============================================================
# DELETE ALL TRANSACTIONS
# ============================================================
@app.delete("/delete_all_transactions")
def delete_all_transactions():
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM sales")
        deleted_count = cur.rowcount
        conn.commit()
        return {"message": f"All transactions deleted ({deleted_count})"}
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete all transactions")
    finally:
        cur.close()
        conn.close()
