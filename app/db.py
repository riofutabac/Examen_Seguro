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
        email TEXT UNIQUE
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
        
        # Obtener credenciales de cajero desde variables de entorno
        cajero_username = os.environ.get('DEFAULT_CAJERO_USERNAME')
        cajero_password = os.environ.get('DEFAULT_CAJERO_PASSWORD')
        cajero_email = os.environ.get('DEFAULT_CAJERO_EMAIL')
        cajero_fullname = os.environ.get('DEFAULT_CAJERO_FULLNAME', 'Cajero Principal')
        
        # Solo crear cajero si se proporcionaron las credenciales
        if cajero_username and cajero_password and cajero_email:
            hashed_password = bcrypt.hashpw(cajero_password.encode('utf-8'), bcrypt.gensalt())
            cur.execute("""
                INSERT INTO bank.users (username, password, role, full_name, email)
                VALUES (%s, %s, %s, %s, %s) RETURNING id;
            """, (cajero_username, hashed_password, 'cajero', cajero_fullname, cajero_email))
            user_id = cur.fetchone()[0]
            
            # Al cajero también se le crea una cuenta y tarjeta para mantener la consistencia
            cur.execute("""
                INSERT INTO bank.accounts (balance, user_id)
                VALUES (%s, %s);
            """, (0, user_id)) # Saldo inicial 0 para el cajero
            
            cur.execute("""
                INSERT INTO bank.credit_cards (limit_credit, balance, user_id)
                VALUES (%s, %s, %s);
            """, (100, 0, user_id)) # Límite bajo para el cajero
            
            conn.commit()
            print(f"✅ Cajero creado exitosamente: {cajero_username}")
        else:
            print("⚠️  No se creó cajero por defecto. Configure DEFAULT_CAJERO_USERNAME, DEFAULT_CAJERO_PASSWORD y DEFAULT_CAJERO_EMAIL")
    cur.close()
    conn.close()
