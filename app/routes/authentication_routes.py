from .main_routes import main_blueprint
from ..models.user import User
from flask import request, jsonify, render_template
from flask_jwt_extended import (
    create_access_token, set_access_cookies, get_jwt,
    jwt_required, unset_jwt_cookies
)

@main_blueprint.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    name = data.get("name")
    password = data.get("password")
    user = User.query.filter_by(name=name).first()
    if name and password and user and user.check_password(password):
        access_token = create_access_token(
            identity=str(user.id), fresh=True, additional_claims={"role": user.role}
        )
        response = jsonify({"message": "Login bem-sucedido"})
        set_access_cookies(response, access_token)
        return response, 200
    else:
        return jsonify({"message": "Credenciais inválidas"}), 401

@main_blueprint.route("/api/logout", methods=["POST"])
@jwt_required()
def logout():
    response = jsonify({"message": "Logout realizado com sucesso"})
    unset_jwt_cookies(response)
    return response, 200

def get_role():
    claims = get_jwt()
    role = claims.get("role")
    return role