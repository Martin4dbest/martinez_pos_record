from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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

    # Verify admin
    verify_admin(req.current_user_id)

    conn = get_db()
    cur = conn.cursor()

    # Check if username already exists
    cur.execute("SELECT id FROM users WHERE username=%s", (req.username,))
    existing = cur.fetchone()
    if existing:
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = hash_password(req.password)

    cur.execute("""
        INSERT INTO users (username, password, role)
        VALUES (%s, %s, %s)
    """, (req.username, hashed_password, req.role))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": f"User '{req.username}' registered successfully"}

# ============================================================
# CREATE TRANSACTION
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

# ============================================================
# GET ALL TRANSACTIONS (Admin Dashboard)
# ============================================================
@app.get("/all_transactions")
def all_transactions():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT s.id,
               u.username AS attendant_name,
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
# GET ALL ATTENDANTS
# ============================================================
@app.get("/attendants")
def get_attendants():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, username
        FROM users
        WHERE role = 'attendant'
        ORDER BY id DESC
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [
        {
            "id": r[0],
            "username": r[1]
        }
        for r in rows
    ]

# ============================================================
# DASHBOARD STATS
# ============================================================

# Total Attendants
@app.get("/attendants_count")
def attendants_count():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM users WHERE role='attendant'")
    count = cur.fetchone()[0]

    cur.close()
    conn.close()

    return {"count": count}

# Total Transactions
@app.get("/transactions_count")
def transactions_count():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM sales")
    count = cur.fetchone()[0]

    cur.close()
    conn.close()

    return {"count": count}

# Total Sales (Amount + Charge)
@app.get("/total_sales")
def total_sales():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COALESCE(SUM(amount_withdrawn + charge), 0)
        FROM sales
    """)

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
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete all transactions")
    finally:
        cur.close()
        conn.close()

# ============================================================
# SERVE FRONTEND
# ============================================================
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
