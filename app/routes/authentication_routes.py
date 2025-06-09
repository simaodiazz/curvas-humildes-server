from .main_routes import main_blueprint
from ..models.user import User
from flask import request, jsonify
from flask_jwt_extended import create_access_token, set_access_cookies

@main_blueprint.route("/login", methods=["POST"])
def login():
    # Use request.json para JSON (ajuste conforme front-end)
    data = request.get_json()
    name = data.get("name")
    password = data.get("password")
    user = User.query.filter_by(name=name).first()
    if name and password and user and user.check_password(password):
        access_token = create_access_token(identity=user.id, fresh=True)
        response = jsonify({"message": "Login bem-sucedido"})
        set_access_cookies(response, access_token)
        return response, 200
    else:
        return jsonify({"message": "Credenciais inválidas"}), 401