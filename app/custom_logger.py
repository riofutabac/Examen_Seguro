# app/custom_logger.py
import datetime
import re
from flask import request

LOG_FILE = 'security_events.log'

def _mask_sensitive_data(message):
    """Función interna para enmascarar datos sensibles en un mensaje de log."""
    # Enmascarar cédulas - patrones con comillas simples y dobles
    message = re.sub(r"(['\"]cedula['\"]\s*:\s*['\"])\d{6}(\d{4})(['\"])", r"\1******\2\3", message, flags=re.IGNORECASE)
    # Enmascarar contraseñas - patrones con comillas simples y dobles
    message = re.sub(r"(['\"]password['\"]\s*:\s*['\"]).*?(['\"])", r"\1********\2", message, flags=re.IGNORECASE)
    # Enmascarar números de celular - patrones con comillas simples y dobles
    message = re.sub(r"(['\"]celular['\"]\s*:\s*['\"])\d{6}(\d{4})(['\"])", r"\1******\2\3", message, flags=re.IGNORECASE)
    # Enmascarar tokens JWT parcialmente
    message = re.sub(r"(Bearer\s+)([a-zA-Z0-9_-]{10})[a-zA-Z0-9_.-]*", r"\1\2***", message, flags=re.IGNORECASE)
    # Enmascarar emails parcialmente
    message = re.sub(r"([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", r"\1***@\2", message, flags=re.IGNORECASE)
    return message

def log_event(level, message, status_code='-', user_id='anonymous'):
    """
    Escribe una entrada de log estandarizada en el archivo de seguridad.
    Formato: AAAA-MM-DD HH:MM:SS.ssss | LEVEL | IP | USUARIO_ID | MENSAJE | HTTP STATUS
    """
    try:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        ip_address = request.remote_addr if request else 'N/A'
        safe_message = _mask_sensitive_data(str(message)).replace('\n', ' ').replace('\r', '').replace('\t', ' ')
        log_entry = f"{timestamp} | {level.upper():<7} | {ip_address:<15} | {user_id:<15} | {safe_message} | HTTP {status_code}\n"
        
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"CRITICAL: Failed to write to log file: {e}")

def log_endpoint(action_name):
    """Decorador que loguea automáticamente el inicio, éxito y errores de un endpoint."""
    from functools import wraps
    from flask import g
    
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_id = getattr(g, 'user', {}).get('id', 'anonymous') if hasattr(g, 'user') else 'anonymous'
            try:
                log_event('INFO', f"Inicio de {action_name}", status_code='-', user_id=user_id)
                response = f(*args, **kwargs)
                # response puede ser (body, code) o solo body
                status_code = response[1] if isinstance(response, tuple) else 200
                log_event('INFO', f"Éxito de {action_name}", status_code=status_code, user_id=user_id)
                return response
            except Exception as e:
                status_code = getattr(e, 'code', 500)
                log_event('ERROR', f"Error en {action_name}: {str(e)}", status_code=status_code, user_id=user_id)
                raise
        return wrapper
    return decorator