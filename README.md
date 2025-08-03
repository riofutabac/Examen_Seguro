# 🏦 Core Bancario - Sistema de Seguridad Completo

Sistema bancario con autenticación JWT, control de roles, logging de seguridad y validaciones robustas.

## 🚀 Inicio Rápido

### Prerrequisitos
- Docker y Docker Compose
- Variables de entorno configuradas

### Levantar el Sistema

```bash
# 1. Configurar variables de entorno
export JWT_SECRET_KEY=$(openssl rand -hex 32)  # Obligatorio para producción
export ENV=development  # o 'production'

# 2. Levantar con Docker
docker-compose up --build

# 3. La API estará disponible en http://localhost:8000
```

### Swagger UI
Accede a la documentación interactiva en: `http://localhost:8000/swagger`

## 🔐 Características de Seguridad

### ✅ Sistema de Autenticación (TCG-01)
- **JWT stateless** con expiración de 2 horas
- **Validación de roles**: `cliente`, `cajero`
- **Decoradores de seguridad**: `@token_required`, `@requires_role()`
- **Logout cliente-side**: No hay blacklist persistente; el token se descarta del cliente

### ✅ Logging de Seguridad (TCG-02)
- **Sistema propio** sin librerías externas
- **Enmascaramiento automático** de datos sensibles
- **Archivo separado**: `security_events.log`
- **Formato**: `TIMESTAMP | LEVEL | IP | USER_ID | MESSAGE | HTTP_CODE`

### ✅ Registro Seguro (TCE-07)
- **Validaciones estrictas**: cédula, celular, username, contraseña
- **Separación de datos**: `users` / `clients`
- **Registro de IP** y metadatos de seguridad

## 📖 Guía de Uso

### 1. Registrar Nuevo Cliente
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "nombres": "Juan Carlos",
    "apellidos": "Pérez García",
    "direccion": "Av. Principal 123",
    "cedula": "1234567890",
    "celular": "0987654321",
    "username": "juanperez",
    "password": "MiPassword123!",
    "email": "juan@example.com"
  }'
```

### 2. Iniciar Sesión
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "juanperez",
    "password": "MiPassword123!"
  }'
```

**Respuesta:**
```json
{
  "message": "Login exitoso",
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### 3. Usar Token en Operaciones
```bash
# Ejemplo: Retiro
curl -X POST http://localhost:8000/bank/withdraw \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{"amount": 100}'
```

## 🎯 Endpoints Disponibles

### Autenticación
- `POST /auth/register` - Registro de cliente
- `POST /auth/login` - Inicio de sesión  
- `POST /auth/logout` - Cerrar sesión (stateless - descarte del token en cliente)

### Operaciones Bancarias (Requieren Token)
- `POST /bank/deposit` - Depósito (solo `cajero`)
- `POST /bank/withdraw` - Retiro
- `POST /bank/transfer` - Transferencia
- `POST /bank/credit-payment` - Compra a crédito
- `POST /bank/pay-credit-balance` - Abono a tarjeta

## 🛡️ Control de Roles

| Endpoint | Cliente | Cajero |
|----------|---------|--------|
| `/withdraw` | ✅ | ✅ |
| `/transfer` | ✅ | ✅ |
| `/deposit` | ❌ | ✅ |
| `/credit-payment` | ✅ | ✅ |
| `/pay-credit-balance` | ✅ | ✅ |

## 📊 Monitoreo y Logs

### Ver Logs de Seguridad
```bash
# En tiempo real
docker-compose exec app tail -f security_events.log

# Últimas 50 entradas
docker-compose exec app tail -n 50 security_events.log

# Buscar errores
docker-compose exec app grep "ERROR" security_events.log
```

### Ejemplos de Logs
```
2024-01-15 14:30:25.123 | INFO    | 192.168.1.100   | 5              | Login exitoso para usuario 'juanperez' | HTTP 200
2024-01-15 14:31:10.456 | WARNING | 192.168.1.100   | 5              | Fondos insuficientes: balance=150.0, requested=200 | HTTP 400
2024-01-15 14:32:05.789 | ERROR   | 192.168.1.100   | anonymous      | HTTP error: Rol 'cliente' no autorizado para esta operación | HTTP 403
```

## 🔒 Datos Sensibles Enmascarados

El sistema automáticamente enmascara:
- **Cédulas**: `1234567890` → `1234******90`
- **Celulares**: `0987654321` → `0987******21`  
- **Contraseñas**: `MiPass123!` → `********`
- **Emails**: `user@domain.com` → `user***@domain.com`
- **Tokens JWT**: Solo primeros 10 caracteres + `***`

## ⚙️ Configuración

### Variables de Entorno Requeridas

```bash
# Obligatorio para producción
JWT_SECRET_KEY=your-super-secure-key-32-chars-min

# Opcional
ENV=production  # development | production
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=corebank
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

### Generar Secret Seguro
```bash
# Para JWT_SECRET_KEY
openssl rand -hex 32

# O con Python
python -c "import secrets; print(secrets.token_hex(32))"
```

## 🧪 Verificación del Sistema

Ejecuta el script de pruebas incluido:
```bash
chmod +x test_security_features.sh
./test_security_features.sh
```

**Pruebas Incluidas:**
- ✅ Registro con validaciones
- ✅ Login y generación JWT
- ✅ Control de acceso sin token
- ✅ Validación de roles
- ✅ Manejo de errores
- ✅ Generación de logs
- ✅ Enmascaramiento de datos

## 🚨 Códigos de Error Comunes

| Código | Descripción | Acción |
|--------|-------------|---------|
| `400` | Datos inválidos | Verificar formato de entrada |
| `401` | Token ausente/inválido | Hacer login nuevamente |
| `403` | Rol no autorizado | Verificar permisos del usuario |
| `404` | Recurso no encontrado | Verificar IDs/usernames |
| `409` | Usuario/cédula duplicados | Usar datos únicos |
| `500` | Error interno | Revisar logs del servidor |

## 📝 Validaciones de Registro

### Cédula Ecuatoriana
- ✅ 10 dígitos exactos
- ✅ Algoritmo oficial de validación
- ✅ Últimos dígitos verificadores

### Celular
- ✅ Formato: `09XXXXXXXX`
- ✅ 10 dígitos empezando con `09`

### Username
- ✅ Solo caracteres alfanuméricos
- ✅ No puede contener nombres/apellidos
- ✅ Mínimo 3 caracteres

### Contraseña
- ✅ Mínimo 8 caracteres
- ✅ Al menos 1 mayúscula, 1 minúscula, 1 número, 1 símbolo
- ✅ No puede contener información personal

## 🔧 Desarrollo

### Estructura del Proyecto
```
app/
├── main.py           # API principal con endpoints
├── security.py       # JWT y decoradores de seguridad
├── custom_logger.py  # Sistema de logging propio
├── db.py             # Conexión y inicialización DB
├── validators.py     # Validaciones de entrada
└── __init__.py
```

### Añadir Nuevo Endpoint Protegido
```python
from .security import token_required, requires_role
from .custom_logger import log_endpoint

@bank_ns.route('/new-operation')
class NewOperation(Resource):
    @token_required
    @requires_role('cliente', 'cajero')
    @log_endpoint("Nueva Operación")
    def post(self):
        # Tu lógica aquí
        return {"message": "Operación exitosa"}, 200
```

## 📚 Documentación Adicional

- **Swagger UI**: `http://localhost:8000/swagger`
- **Logs de aplicación**: `app.log`
- **Logs de seguridad**: `security_events.log`
- **Base de datos**: PostgreSQL en puerto 5432

## 🆘 Soporte

Para problemas comunes:

1. **Token expirado**: Hacer login nuevamente
2. **Conexión DB**: Verificar docker-compose up
3. **Logs no generan**: Verificar permisos de escritura
4. **Errores 500**: Revisar `docker-compose logs app`

### Revocación de Tokens

El sistema actual implementa **logout stateless**: el token sigue siendo válido hasta su expiración (2 horas), pero el cliente debe descartarlo.

**Para implementar revocación real en el futuro:**
- Agregar tabla `token_blacklist` o usar Redis
- Modificar `@token_required` para verificar blacklist
- Añadir token a blacklist en `/logout`

---

**Sistema desarrollado con enfoque en seguridad bancaria y cumplimiento de estándares.**
