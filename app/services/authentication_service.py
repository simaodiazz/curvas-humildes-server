from ..models.user import User
from ..db import sqlAlchemy as db

def register(name, email, phone_number, password):
    # Verificação básica de dados vazios
    if not name or not email or not phone_number or not password:
        return False, "Preencha todos os campos obrigatórios."

    # Verifica se nome já existe
    if User.query.filter_by(name=name).first():
        return False, "Nome de usuário já cadastrado."

    if User.query.filter_by(email=email).first():
        return False, "Email já cadastrado."

    if User.query.filter_by(phone_number=phone_number).first():
        return False, "Telefone já cadastrado."

    # Pode incluir validação de formato do email/telefone aqui se quiser

    user = User()
    user.name = name
    user.email = email
    user.phone_number = phone_number
    user.role = "user"
    user.set_password(password)
    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return False, "Erro ao cadastrar usuário."

    return True, user