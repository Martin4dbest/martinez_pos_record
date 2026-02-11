import hashlib
import psycopg2

# -----------------------------
# Config
# -----------------------------
DATABASE_URL = "postgresql://neondb_owner:npg_KPB2I6LRDfup@ep-little-lab-ai8sg01t-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"

username = "Martinez"
password = "2019@Harmony"
role = "admin"

# -----------------------------
# Hash the password using SHA-256
# -----------------------------
safe_password = password.strip()  # remove extra whitespace
hashed_password = hashlib.sha256(safe_password.encode()).hexdigest()

# -----------------------------
# Connect to Neon and insert admin
# -----------------------------
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("""
    INSERT INTO users (username, password, role)
    VALUES (%s, %s, %s)
""", (username, hashed_password, role))

conn.commit()
cur.close()
conn.close()

print(f"Admin '{username}' created successfully!")
