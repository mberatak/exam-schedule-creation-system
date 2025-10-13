
import psycopg2
from psycopg2 import sql, OperationalError
from passlib.hash import bcrypt
import sys

class Database:
    def __init__(self, host="localhost", database="exam_schedule_db", user="postgres", password="thisisapassword", port=5432):
        self.config = dict(host=host, database=database, user=user, password=password, port=port)
        self.conn = None
        self.cur = None

    def connect(self):
        try:
            self.conn = psycopg2.connect(**self.config)
            self.cur = self.conn.cursor()
            # ensure users table exists
            self.create_users_table()
            print("✅ Veritabanına bağlantı başarılı.")
        except OperationalError as e:
            print("❌ Veritabanı bağlantı hatası:", e)
            sys.exit(1)

    def create_users_table(self):
        q = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            ad VARCHAR(100),
            email VARCHAR(100) UNIQUE,
            sifre VARCHAR(255),
            rol VARCHAR(50), -- admin / koordinator
            bolum VARCHAR(100)
        );
        """
        self.execute(q)

    def execute(self, query, params=None, fetchone=False, fetchall=False):
        try:
            self.cur.execute(query, params)
            if fetchone:
                return self.cur.fetchone()
            if fetchall:
                return self.cur.fetchall()
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise

    # --- User helpers ---
    def add_user(self, ad, email, sifre_plain, rol="koordinator", bolum=""):
        # hash password
        hashed = bcrypt.hash(sifre_plain)
        q = "INSERT INTO users (ad, email, sifre, rol, bolum) VALUES (%s, %s, %s, %s, %s)"
        try:
            self.execute(q, (ad, email, hashed, rol, bolum))
            return True
        except Exception as e:
            # likely unique constraint failed etc.
            raise

    def list_users(self, filter_text=None):
        if filter_text:
            q = "SELECT id, ad, email, rol, bolum FROM users WHERE email ILIKE %s OR ad ILIKE %s ORDER BY id"
            s = f"%{filter_text}%"
            return self.execute(q, (s, s), fetchall=True)
        else:
            q = "SELECT id, ad, email, rol, bolum FROM users ORDER BY id"
            return self.execute(q, fetchall=True)

    def delete_user_by_email(self, email):
        q = "DELETE FROM users WHERE email=%s"
        self.execute(q, (email,))

    def update_password(self, email, new_plain):
        new_hash = bcrypt.hash(new_plain)
        q = "UPDATE users SET sifre=%s WHERE email=%s"
        self.execute(q, (new_hash, email))

    def get_user_by_email(self, email):
        q = "SELECT id, ad, email, rol, bolum, sifre FROM users WHERE email=%s"
        return self.execute(q, (email,), fetchone=True)

    def close(self):
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()