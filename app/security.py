# app/security.py
import jwt
import datetime
import bcrypt
from functools import wraps
from flask import request, g, current_app

def hash_password(password):
    """Genera un hash seguro de la contraseña usando bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def check_password(hashed_password_bytes, password):
    """Verifica una contraseña contra su hash de bcrypt."""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password_bytes)

def create_jwt(user_id, role, username=None):
    """Crea un nuevo token JWT."""
    try:
        payload = {
            'sub': user_id,
            'role': role,
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        }
        if username:
            payload['username'] = username
        secret_key = current_app.config.get('SECRET_KEY')
        return jwt.encode(payload, secret_key, algorithm='HS256')
    except Exception as e:
        print(f"Error creating JWT: {e}")
        return None

def token_required(f):
    """Decorador que protege endpoints verificando el JWT."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask_restx import abort
        
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            abort(401, "Token de autorización ausente o en formato incorrecto (se espera 'Bearer <token>')")
        
        token = auth_header.split(" ")[1]
        try:
            secret_key = current_app.config.get('SECRET_KEY')
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            g.user = {
                'id': payload['sub'], 
                'role': payload['role'],
                'username': payload.get('username')
            }
        except jwt.ExpiredSignatureError:
            abort(401, "El token ha expirado. Por favor, inicie sesión de nuevo.")
        except jwt.InvalidTokenError:
            abort(401, "Token inválido. No se pudo autenticar.")
        
        return f(*args, **kwargs)
    return decorated

def requires_role(*allowed_roles):
    """Decorador que valida si el usuario tiene uno de los roles permitidos."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask_restx import abort
            
            # El usuario debe estar autenticado primero (token_required debe ejecutarse antes)
            if not hasattr(g, 'user') or not g.user:
                abort(401, "Usuario no autenticado")
            
            role = g.user.get('role')
            if role not in allowed_roles:
                abort(403, f"Rol '{role}' no autorizado para esta operación. Roles permitidos: {', '.join(allowed_roles)}")
            
            return f(*args, **kwargs)
        return wrapper
    return decorator