from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from sqlalchemy.exc import IntegrityError
from ....services import user_services
from ....db import sqlAlchemy as db
from .admin_routes import admin_blueprint

def _serialize_user(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone_number": user.phone_number,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }

def _is_admin():
    claims = get_jwt()
    return claims.get("role") == "admin"

# Listar utilizadores
@admin_blueprint.route("/admin/users", methods=["GET"])
@jwt_required()
def list_users():
    if not _is_admin():
        return jsonify({"error": "Acesso negado"}), 403
    users = user_services.get_all_users()
    return jsonify([_serialize_user(u) for u in users]), 200

# Criar utilizador
@admin_blueprint.route("/admin/users", methods=["POST"])
@jwt_required()
def create_user():
    if not _is_admin():
        return jsonify({"error": "Acesso negado"}), 403
    data = request.get_json()
    name = data.get("name")
    password = data.get("password")
    email = data.get("email")
    phone_number = data.get("phone_number")
    role = data.get("role")
    if not all([name, password, email, phone_number, role]):
        return jsonify({"error": "Preencha todos os campos obrigatórios."}), 400
    if len(password) < 6:
        return jsonify({"error": "A palavra-passe deve ter pelo menos 6 caracteres."}), 400
    try:
        user = user_services.create_user(
            name=name,
            email=email,
            phone_number=phone_number,
            password=password,
            role=role
        )
        return jsonify(_serialize_user(user)), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Nome, email ou telefone já existem no sistema."}), 409

# Detalhes de utilizador
@admin_blueprint.route("/admin/users/<int:user_id>", methods=["GET"])
@jwt_required()
def get_user(user_id):
    if not _is_admin():
        return jsonify({"error": "Acesso negado"}), 403
    user = user_services.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "Utilizador não encontrado"}), 404
    return jsonify(_serialize_user(user)), 200

# Atualizar utilizador
@admin_blueprint.route("/admin/users/<int:user_id>", methods=["PUT", "PATCH"])
@jwt_required()
def update_user(user_id):
    if not _is_admin():
        return jsonify({"error": "Acesso negado"}), 403
    data = request.get_json()
    allowed_fields = ("name", "role", "email", "phone_number")
    update_fields = {k: v for k, v in data.items() if k in allowed_fields}
    if "role" in update_fields and update_fields["role"] not in ("admin", "operador"):
        return jsonify({"error": "Perfil inválido."}), 400
    if not update_fields:
        return jsonify({"error": "Nenhum campo válido."}), 400
    try:
        user = user_services.update_user(user_id, **update_fields)
        if not user:
            return jsonify({"error": "Utilizador não encontrado"}), 404
        return jsonify(_serialize_user(user)), 200
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Nome, email ou telefone já existem."}), 409

# Excluir utilizador
@admin_blueprint.route("/admin/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def delete_user(user_id):
    if not _is_admin():
        return jsonify({"error": "Acesso negado"}), 403
    ok = user_services.delete_user(user_id)
    if not ok:
        return jsonify({"error": "Utilizador não encontrado"}), 404
    return jsonify({"msg": "Utilizador removido"}), 200

# Reset de password por admin
@admin_blueprint.route("/admin/users/<int:user_id>/password", methods=["PUT"])
@jwt_required()
def reset_user_password(user_id):
    if not _is_admin():
        return jsonify({"error": "Acesso negado"}), 403
    data = request.get_json()
    new_password = data.get("new_password")
    if not new_password or len(new_password) < 6:
        return jsonify({"error": "A palavra-passe deve ter pelo menos 6 caracteres."}), 400
    user = user_services.set_user_password(user_id, new_password)
    if not user:
        return jsonify({"error": "Utilizador não encontrado"}), 404
    return jsonify({"msg": "Palavra-passe redefinida."}), 200

# Troca própria de password
@admin_blueprint.route("/admin/users/password", methods=["PUT"])
@jwt_required()
def change_own_password():
    user_id = int(get_jwt_identity())
    data = request.get_json()
    old = data.get("old_password")
    new = data.get("new_password")
    if not old or not new or len(new) < 6:
        return jsonify({"error": "Preencha a senha antiga e uma nova válida."}), 400
    user = user_services.get_user_by_id(user_id)
    if not user or not user.check_password(old):
        return jsonify({"error": "Senha antiga incorreta."}), 400
    user_services.set_user_password(user_id, new)
    return jsonify({"msg": "Senha alterada com sucesso."}), 200
