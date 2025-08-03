# app/db.py
import os
import psycopg2

# Variables de entorno (definidas en docker-compose o con valores por defecto)
DB_HOST = os.environ.get('POSTGRES_HOST', 'db')
DB_PORT = os.environ.get('POSTGRES_PORT', '5432')
DB_NAME = os.environ.get('POSTGRES_DB', 'corebank')
DB_USER = os.environ.get('POSTGRES_USER', 'postgres')
DB_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'postgres')

def get_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    
    # Crear la tabla de usuarios
    cur.execute("""
    CREATE SCHEMA IF NOT EXISTS bank AUTHORIZATION postgres;
    
    CREATE TABLE IF NOT EXISTS bank.users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password BYTEA NOT NULL,
        role TEXT NOT NULL,
        full_name TEXT,
        email TEXT
    );
    """)
    conn.commit()
    
    # Crear la tabla de cuentas
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bank.accounts (
        id SERIAL PRIMARY KEY,
        balance NUMERIC NOT NULL DEFAULT 0,
        user_id INTEGER REFERENCES bank.users(id)
    );
    """)
    conn.commit()
    
    # Crear la tabla de tarjetas de crédito
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bank.credit_cards (
        id SERIAL PRIMARY KEY,
        limit_credit NUMERIC NOT NULL DEFAULT 1,
        balance NUMERIC NOT NULL DEFAULT 0,
        user_id INTEGER REFERENCES bank.users(id)
    );
    """)
    
    # Nota: La tabla de tokens se removió porque JWT es stateless
    # Si se necesita revocación de tokens, implementar blacklist o usar Redis
    
    # Crear tabla clients para el registro de nuevos clientes
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bank.clients (
        id SERIAL PRIMARY KEY,
        user_id INTEGER UNIQUE NOT NULL REFERENCES bank.users(id) ON DELETE CASCADE,
        nombres TEXT NOT NULL,
        apellidos TEXT NOT NULL,
        direccion TEXT,
        cedula TEXT UNIQUE NOT NULL,
        celular TEXT,
        ip_registro VARCHAR(45)
    );
    """)
    
    conn.commit()
    
    # Insertar datos de ejemplo si no existen usuarios
    cur.execute("SELECT COUNT(*) FROM bank.users;")
    count = cur.fetchone()[0]
    if count == 0:
        import bcrypt
        sample_users = [
            ('user1', 'pass1', 'cliente', 'Usuario Uno', 'user1@example.com'),
            ('user2', 'pass2', 'cliente', 'Usuario Dos', 'user2@example.com'),
            ('user3', 'pass3', 'cajero',  'Usuario Tres', 'user3@example.com')
        ]
        for username, password, role, full_name, email in sample_users:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            cur.execute("""
                INSERT INTO bank.users (username, password, role, full_name, email)
                VALUES (%s, %s, %s, %s, %s) RETURNING id;
            """, (username, hashed_password, role, full_name, email))
            user_id = cur.fetchone()[0]
            # Crear una cuenta con saldo inicial 1000
            cur.execute("""
                INSERT INTO bank.accounts (balance, user_id)
                VALUES (%s, %s);
            """, (1000, user_id))
            # Crear una tarjeta de crédito con límite 5000 y deuda 0
            cur.execute("""
                INSERT INTO bank.credit_cards (limit_credit, balance, user_id)
                VALUES (%s, %s, %s);
            """, (5000, 0, user_id))
        conn.commit()
    cur.close()
    conn.close()
