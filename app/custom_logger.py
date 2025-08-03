# app/custom_logger.py
import datetime
import re
from flask import request

LOG_FILE = 'security_events.log'

def _mask_sensitive_data(message):
    """Función interna para enmascarar datos sensibles en un mensaje de log."""
    # Enmascarar cédulas (formato: 'cedula': '1234567890')
    message = re.sub(r"('cedula':\s*')\d{6}(\d{4})'", r"\1******\2'", message, flags=re.IGNORECASE)
    # Enmascarar contraseñas
    message = re.sub(r"('password':\s*)'.*?'", r"\1'********'", message, flags=re.IGNORECASE)
    # Enmascarar números de celular
    message = re.sub(r"('celular':\s*')\d{6}(\d{4})'", r"\1******\2'", message, flags=re.IGNORECASE)
    return message

def log_event(level, message, status_code='-', user_id='anonymous'):
    """
    Escribe una entrada de log estandarizada en el archivo de seguridad.
    Formato: AAAA-MM-DD HH:MM:SS.ssss | LEVEL | IP | USUARIO_ID | MENSAJE | HTTP STATUS
    """
    try:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        ip_address = request.remote_addr if request else 'N/A'
        safe_message = _mask_sensitive_data(str(message))
        log_entry = f"{timestamp} | {level.upper():<7} | {ip_address:<15} | {user_id:<15} | {safe_message} | HTTP {status_code}\n"
        
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"CRITICAL: Failed to write to log file: {e}")