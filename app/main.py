import secrets
import os
from flask import Flask, request, g
from flask_restx import Api, Resource, fields # type: ignore
from functools import wraps
from .db import get_connection, init_db
import logging

# JWT-based authentication - no in-memory token store needed

#log = logging.getLogger(__name__)
logging.basicConfig(
     filename="app.log",
     level=logging.DEBUG,
     encoding="utf-8",
     filemode="a",
     format="{asctime} - {levelname} - {message}",
     style="{",
     datefmt="%Y-%m-%d %H:%M",
)

# Configure Swagger security scheme for Bearer tokens
authorizations = {
    'Bearer': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
        'description': "Enter your token in the format **Bearer <token>**"
    }
}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'default-super-secret-key-change-me')

api = Api(
    app,
    version='1.0',
    title='Core Bancario API',
    description='API para operaciones bancarias, incluyendo autenticación y operaciones de cuenta.',
    doc='/swagger',  # Swagger UI endpoint
    authorizations=authorizations,
    security='Bearer'
)

# Create namespaces for authentication and bank operations
auth_ns = api.namespace('auth', description='Operaciones de autenticación')
bank_ns = api.namespace('bank', description='Operaciones bancarias')

# Define the expected payload models for Swagger
login_model = auth_ns.model('Login', {
    'username': fields.String(required=True, description='Nombre de usuario', example='user1'),
    'password': fields.String(required=True, description='Contraseña', example='pass1')
})

deposit_model = bank_ns.model('Deposit', {
    'account_number': fields.Integer(required=True, description='Número de cuenta', example=123),
    'amount': fields.Float(required=True, description='Monto a depositar', example=100)
})

withdraw_model = bank_ns.model('Withdraw', {
    'amount': fields.Float(required=True, description='Monto a retirar', example=100)
})

transfer_model = bank_ns.model('Transfer', {
    'target_username': fields.String(required=True, description='Usuario destino', example='user2'),
    'amount': fields.Float(required=True, description='Monto a transferir', example=100)
})

credit_payment_model = bank_ns.model('CreditPayment', {
    'amount': fields.Float(required=True, description='Monto de la compra a crédito', example=100)
})

pay_credit_balance_model = bank_ns.model('PayCreditBalance', {
    'amount': fields.Float(required=True, description='Monto a abonar a la deuda de la tarjeta', example=50)
})

register_model = auth_ns.model('Register', {
    'nombres': fields.String(required=True, description='Nombres del cliente', example='Juan Carlos'),
    'apellidos': fields.String(required=True, description='Apellidos del cliente', example='García López'),
    'direccion': fields.String(description='Dirección del cliente', example='Av. 10 de Agosto 123'),
    'cedula': fields.String(required=True, description='Número de cédula', example='1234567890'),
    'celular': fields.String(required=True, description='Número de celular', example='0987654321'),
    'username': fields.String(required=True, description='Nombre de usuario', example='juangarcia123'),
    'password': fields.String(required=True, description='Contraseña', example='MiPassword123!'),
    'email': fields.String(required=True, description='Correo electrónico', example='juan@example.com')
})

# ---------------- Authentication Endpoints ----------------

@auth_ns.route('/login')
class Login(Resource):
    @auth_ns.expect(login_model, validate=True)
    @auth_ns.doc('login')
    def post(self):
        """Inicia sesión y devuelve un token JWT."""
        from .security import create_jwt, check_password
        
        data = api.payload
        username = data.get("username")
        password = data.get("password")
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, password, role FROM bank.users WHERE username = %s", (username,))
        user_data = cur.fetchone()
        cur.close()
        conn.close()
        
        if user_data and check_password(user_data[1].tobytes(), password):
            user_id = user_data[0]
            role = user_data[2]
            token = create_jwt(user_id, role, username)
            
            from .custom_logger import log_event
            log_event('INFO', f"Login exitoso para usuario '{username}'", status_code=200, user_id=user_id)
            return {"message": "Login successful", "token": token}, 200
        else:
            from .custom_logger import log_event
            log_event('WARNING', f"Intento de login fallido para usuario '{username}'", status_code=401)
            api.abort(401, "Credenciales inválidas.")

@auth_ns.route('/logout')
class Logout(Resource):
    @auth_ns.doc('logout')
    def post(self):
        """Cierra la sesión del lado del cliente (debe descartar el token)."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            api.abort(401, "Token de autorización ausente o en formato incorrecto")
        
        token = auth_header.split(" ")[1]
        try:
            import jwt
            secret_key = app.config.get('SECRET_KEY')
            jwt.decode(token, secret_key, algorithms=['HS256'])
            return {"message": "Logout successful. Please discard the token."}, 200
        except jwt.ExpiredSignatureError:
            api.abort(401, "El token ha expirado.")
        except jwt.InvalidTokenError:
            api.abort(401, "Token inválido.")

@auth_ns.route('/register')
class Register(Resource):
    @auth_ns.expect(register_model, validate=True)
    @auth_ns.doc('register')
    def post(self):
        """Registra un nuevo cliente con validaciones estrictas."""
        from .validators import validar_cedula, validar_celular, validar_username, validar_password
        from .security import hash_password
        from .custom_logger import log_event
        
        data = api.payload
        ip_registro = request.remote_addr
        
        # Fase de Validación
        if not validar_cedula(data['cedula']):
            api.abort(400, "El número de cédula proporcionado no es válido.")
        
        if not validar_celular(data['celular']):
            api.abort(400, "El número de celular debe tener 10 dígitos y empezar con 09.")
        
        if not validar_username(data['username'], data['nombres'], data['apellidos']):
            api.abort(400, "El nombre de usuario es inválido o contiene información personal.")
        
        info_personal_para_pass = {
            'nombres': data['nombres'], 
            'apellidos': data['apellidos'], 
            'cedula': data['cedula']
        }
        if not validar_password(data['password'], info_personal_para_pass):
            api.abort(400, "La contraseña no cumple con los requisitos de seguridad.")
        
        # Fase de Persistencia (Transaccional)
        conn = get_connection()
        cur = conn.cursor()
        try:
            # 1. Hashear contraseña
            password_hash = hash_password(data['password'])
            
            # 2. Construir full_name y validar email
            full_name = f"{data['nombres']} {data['apellidos']}"
            email = data['email']
            
            # 3. Insertar en users
            cur.execute(
                "INSERT INTO bank.users (username, password, role, full_name, email) VALUES (%s, %s, 'cliente', %s, %s) RETURNING id",
                (data['username'], password_hash, full_name, email)
            )
            user_id = cur.fetchone()[0]
            
            # 4. Insertar en clients
            cur.execute(
                """INSERT INTO bank.clients (user_id, nombres, apellidos, direccion, cedula, celular, ip_registro)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (user_id, data['nombres'], data['apellidos'], data.get('direccion'), 
                 data['cedula'], data['celular'], ip_registro)
            )
            
            # 5. Crear cuenta y tarjeta por defecto
            cur.execute("INSERT INTO bank.accounts (balance, user_id) VALUES (0, %s)", (user_id,))
            cur.execute("INSERT INTO bank.credit_cards (limit_credit, balance, user_id) VALUES (500, 0, %s)", (user_id,))
            
            conn.commit()
            log_event('INFO', f"Nuevo cliente registrado exitosamente: {data['username']}", status_code=201, user_id=user_id)
            return {"message": "Cliente registrado exitosamente."}, 201
            
        except Exception as e:
            conn.rollback()
            log_event('ERROR', f"Error en registro para {data['username']}: {e}", status_code=500)
            
            if 'duplicate key value' in str(e).lower():
                api.abort(409, "El nombre de usuario o la cédula ya existen.")
            api.abort(500, "Ocurrió un error interno durante el registro.")
        finally:
            cur.close()
            conn.close()

# ---------------- Token-Required Decorator ----------------
# Import the new JWT-based token_required decorator and role validator
from .security import token_required, requires_role

# ---------------- Banking Operation Endpoints ----------------

@bank_ns.route('/deposit')
class Deposit(Resource):
    logging.debug("Entering....")
    @bank_ns.expect(deposit_model, validate=True)
    @bank_ns.doc('deposit')
    @token_required
    @requires_role('cajero')
    def post(self):
        """
        Realiza un depósito en la cuenta especificada.
        Se requiere el número de cuenta y el monto a depositar.
        """
        from .custom_logger import log_event
        
        data = api.payload
        account_number = data.get("account_number")
        amount = data.get("amount", 0)
        user_id = g.user['id']
        
        if amount <= 0:
            log_event('WARNING', f"Intento de depósito inválido: amount={amount}", status_code=400, user_id=user_id)
            api.abort(400, "Amount must be greater than zero")
        
        conn = get_connection()
        cur = conn.cursor()
        # Update the specified account using its account number (primary key)
        cur.execute(
            "UPDATE bank.accounts SET balance = balance + %s WHERE id = %s RETURNING balance",
            (amount, account_number)
        )
        result = cur.fetchone()
        if not result:
            conn.rollback()
            cur.close()
            conn.close()
            log_event('ERROR', f"Cuenta no encontrada: {account_number}", status_code=404, user_id=user_id)
            api.abort(404, "Account not found")
        new_balance = float(result[0])
        conn.commit()
        cur.close()
        conn.close()
        log_event('INFO', f"Depósito de {amount} en cuenta {account_number}, nuevo balance: {new_balance}", status_code=200, user_id=user_id)
        return {"message": "Deposit successful", "new_balance": new_balance}, 200

@bank_ns.route('/withdraw')
class Withdraw(Resource):
    @bank_ns.expect(withdraw_model, validate=True)
    @bank_ns.doc('withdraw')
    @token_required
    def post(self):
        """Realiza un retiro de la cuenta del usuario autenticado."""
        data = api.payload
        amount = data.get("amount", 0)
        if amount <= 0:
            api.abort(400, "Amount must be greater than zero")
        user_id = g.user['id']
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT balance FROM bank.accounts WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            api.abort(404, "Account not found")
        current_balance = float(row[0])
        if current_balance < amount:
            cur.close()
            conn.close()
            api.abort(400, "Insufficient funds")
        cur.execute("UPDATE bank.accounts SET balance = balance - %s WHERE user_id = %s RETURNING balance", (amount, user_id))
        new_balance = float(cur.fetchone()[0])
        conn.commit()
        cur.close()
        conn.close()
        
        from .custom_logger import log_event
        log_event('INFO', f"Retiro de {amount} solicitado", status_code=200, user_id=user_id)
        return {"message": "Withdrawal successful", "new_balance": new_balance}, 200

@bank_ns.route('/transfer')
class Transfer(Resource):
    @bank_ns.expect(transfer_model, validate=True)
    @bank_ns.doc('transfer')
    @token_required
    def post(self):
        """Transfiere fondos desde la cuenta del usuario autenticado a otra cuenta."""
        from .custom_logger import log_event
        
        data = api.payload
        target_username = data.get("target_username")
        amount = data.get("amount", 0)
        user_id = g.user['id']
        
        if not target_username or amount <= 0:
            log_event('WARNING', f"Datos inválidos para transferencia: target={target_username}, amount={amount}", status_code=400, user_id=user_id)
            api.abort(400, "Invalid data")
        if target_username == g.user['username']:
            log_event('WARNING', f"Intento de transferencia a la misma cuenta", status_code=400, user_id=user_id)
            api.abort(400, "Cannot transfer to the same account")
        conn = get_connection()
        cur = conn.cursor()
        # Check sender's balance
        cur.execute("SELECT balance FROM bank.accounts WHERE user_id = %s", (g.user['id'],))
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            api.abort(404, "Sender account not found")
        sender_balance = float(row[0])
        if sender_balance < amount:
            cur.close()
            conn.close()
            api.abort(400, "Insufficient funds")
        # Find target user
        cur.execute("SELECT id FROM bank.users WHERE username = %s", (target_username,))
        target_user = cur.fetchone()
        if not target_user:
            cur.close()
            conn.close()
            api.abort(404, "Target user not found")
        target_user_id = target_user[0]
        try:
            cur.execute("UPDATE bank.accounts SET balance = balance - %s WHERE user_id = %s", (amount, g.user['id']))
            cur.execute("UPDATE bank.accounts SET balance = balance + %s WHERE user_id = %s", (amount, target_user_id))
            cur.execute("SELECT balance FROM bank.accounts WHERE user_id = %s", (g.user['id'],))
            new_balance = float(cur.fetchone()[0])
            conn.commit()
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            api.abort(500, f"Error during transfer: {str(e)}")
        cur.close()
        conn.close()
        log_event('INFO', f"Transferencia de {amount} a {target_username} exitosa, nuevo balance: {new_balance}", status_code=200, user_id=user_id)
        return {"message": "Transfer successful", "new_balance": new_balance}, 200

@bank_ns.route('/credit-payment')
class CreditPayment(Resource):
    @bank_ns.expect(credit_payment_model, validate=True)
    @bank_ns.doc('credit_payment')
    @token_required
    def post(self):
        """
        Realiza una compra a crédito:
        - Descuenta el monto de la cuenta.
        - Aumenta la deuda de la tarjeta de crédito.
        """
        from .custom_logger import log_event
        
        data = api.payload
        amount = data.get("amount", 0)
        user_id = g.user['id']
        
        if amount <= 0:
            log_event('WARNING', f"Monto inválido para pago a crédito: {amount}", status_code=400, user_id=user_id)
            api.abort(400, "Amount must be greater than zero")
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT balance FROM bank.accounts WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            api.abort(404, "Account not found")
        account_balance = float(row[0])
        if account_balance < amount:
            cur.close()
            conn.close()
            api.abort(400, "Insufficient funds in account")
        try:
            cur.execute("UPDATE bank.accounts SET balance = balance - %s WHERE user_id = %s", (amount, user_id))
            cur.execute("UPDATE bank.credit_cards SET balance = balance + %s WHERE user_id = %s", (amount, user_id))
            cur.execute("SELECT balance FROM bank.accounts WHERE user_id = %s", (user_id,))
            new_account_balance = float(cur.fetchone()[0])
            cur.execute("SELECT balance FROM bank.credit_cards WHERE user_id = %s", (user_id,))
            new_credit_balance = float(cur.fetchone()[0])
            conn.commit()
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            api.abort(500, f"Error processing credit card purchase: {str(e)}")
        cur.close()
        conn.close()
        log_event('INFO', f"Pago a crédito de {amount} exitoso, nuevo balance cuenta: {new_account_balance}, deuda tarjeta: {new_credit_balance}", status_code=200, user_id=user_id)
        return {
            "message": "Credit card purchase successful",
            "account_balance": new_account_balance,
            "credit_card_debt": new_credit_balance
        }, 200

@bank_ns.route('/pay-credit-balance')
class PayCreditBalance(Resource):
    @bank_ns.expect(pay_credit_balance_model, validate=True)
    @bank_ns.doc('pay_credit_balance')
    @token_required
    def post(self):
        """
        Realiza un abono a la deuda de la tarjeta:
        - Descuenta el monto (o el máximo posible) de la cuenta.
        - Reduce la deuda de la tarjeta de crédito.
        """
        from .custom_logger import log_event
        
        data = api.payload
        amount = data.get("amount", 0)
        user_id = g.user['id']
        
        if amount <= 0:
            log_event('WARNING', f"Monto inválido para abono a tarjeta: {amount}", status_code=400, user_id=user_id)
            api.abort(400, "Amount must be greater than zero")
        conn = get_connection()
        cur = conn.cursor()
        # Check account funds
        cur.execute("SELECT balance FROM bank.accounts WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            api.abort(404, "Account not found")
        account_balance = float(row[0])
        if account_balance < amount:
            cur.close()
            conn.close()
            api.abort(400, "Insufficient funds in account")
        # Get current credit card debt
        cur.execute("SELECT balance FROM bank.credit_cards WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            api.abort(404, "Credit card not found")
        credit_debt = float(row[0])
        payment = min(amount, credit_debt)
        try:
            cur.execute("UPDATE bank.accounts SET balance = balance - %s WHERE user_id = %s", (payment, user_id))
            cur.execute("UPDATE bank.credit_cards SET balance = balance - %s WHERE user_id = %s", (payment, user_id))
            cur.execute("SELECT balance FROM bank.accounts WHERE user_id = %s", (user_id,))
            new_account_balance = float(cur.fetchone()[0])
            cur.execute("SELECT balance FROM bank.credit_cards WHERE user_id = %s", (user_id,))
            new_credit_debt = float(cur.fetchone()[0])
            conn.commit()
        except Exception as e:
            conn.rollback()
            cur.close()
            conn.close()
            api.abort(500, f"Error processing credit balance payment: {str(e)}")
        cur.close()
        conn.close()
        log_event('INFO', f"Abono a tarjeta de {payment} exitoso, nuevo balance cuenta: {new_account_balance}, nueva deuda: {new_credit_debt}", status_code=200, user_id=user_id)
        return {
            "message": "Credit card debt payment successful",
            "account_balance": new_account_balance,
            "credit_card_debt": new_credit_debt
        }, 200

# ---------------- Global Exception Handler ----------------

@app.errorhandler(Exception)
def handle_uncaught_exception(e):
    """Manejador global para excepciones no capturadas."""
    from flask import jsonify
    from .custom_logger import log_event
    
    user_id = getattr(g, 'user', {}).get('id', 'anonymous') if hasattr(g, 'user') else 'anonymous'
    log_event('ERROR', f"Excepción no manejada: {str(e)}", status_code=500, user_id=user_id)
    return jsonify({"message": "Error interno del servidor"}), 500

@app.before_first_request
def initialize_db():
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

