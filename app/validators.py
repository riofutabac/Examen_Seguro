# app/validators.py
import re

def validar_cedula(cedula: str) -> bool:
    """Valida una cédula ecuatoriana usando el algoritmo de módulo 10."""
    if not (isinstance(cedula, str) and len(cedula) == 10 and cedula.isdigit()):
        return False
    
    prov = int(cedula[0:2])
    if not (1 <= prov <= 24):
        return False
    
    tercer_digito = int(cedula[2])
    if tercer_digito >= 6:
        return False
    
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    suma = 0
    for i in range(9):
        producto = int(cedula[i]) * coeficientes[i]
        if producto >= 10:
            producto -= 9
        suma += producto
    
    residuo = suma % 10
    digito_verificador = 0 if residuo == 0 else 10 - residuo
    return digito_verificador == int(cedula[9])

def validar_celular(celular: str) -> bool:
    """Valida un número de celular ecuatoriano (10 dígitos, empieza con 09)."""
    return isinstance(celular, str) and len(celular) == 10 and celular.startswith('09') and celular.isdigit()

def validar_username(username: str, nombres: str, apellidos: str) -> bool:
    """Valida que el username sea alfanumérico y no contenga información personal."""
    if not username.isalnum():
        return False
    
    partes_prohibidas = nombres.lower().split() + apellidos.lower().split()
    username_lower = username.lower()
    
    for parte in partes_prohibidas:
        # Solo prohibir si la parte completa aparece como palabra completa o al inicio/final
        if len(parte) > 4:
            if (username_lower == parte or 
                username_lower.startswith(parte) or 
                username_lower.endswith(parte)):
                return False
    
    return True

def validar_password(password: str, info_personal: dict) -> bool:
    """Valida la robustez de la contraseña y que no contenga información personal."""
    if len(password) < 8: 
        return False
    if not re.search(r'[A-Z]', password): 
        return False
    if not re.search(r'[a-z]', password): 
        return False
    if not re.search(r'\d', password): 
        return False
    if not re.search(r'[^A-Za-z0-9]', password): 
        return False
    
    for key, value in info_personal.items():
        if isinstance(value, str):
            partes_prohibidas = value.lower().split()
            for parte in partes_prohibidas:
                if len(parte) > 2 and parte in password.lower():
                    return False
    
    return True