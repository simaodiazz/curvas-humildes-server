# CurvasSistema/app/__init__.py
import logging
import os

from flask import Flask, make_response, redirect
from flask_cors import CORS
from flask_mail import Mail
from flask_jwt_extended import JWTManager

from .db import init_db_engine_with_context, sqlAlchemy
from .cache import flaskCaching

app = Flask(__name__, instance_relative_config=True)

cors = CORS()
mail = Mail()
jwt = JWTManager()


def create_app(config_object_name="config"):
    """
    App factory: cria e configura a instância da aplicação Flask.
    """

    app.config.from_object(config_object_name)

    if not os.path.exists(app.instance_path):
        try:
            os.makedirs(app.instance_path)
        except OSError:
            logging.getLogger(__name__).error(
                f"Não foi possível criar a pasta instance em {app.instance_path}"
            )

    app.config.from_object("config.Development")

    if not app.debug and not app.testing:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        app.logger.addHandler(stream_handler)

    app.logger.setLevel(logging.INFO)
    app.logger.info("Aplicação Curvas Humildes a iniciar...")

    cors.init_app(app)
    mail.init_app(app)
    sqlAlchemy.init_app(app)
    flaskCaching.init_app(app)
    jwt.init_app(app)

    from .routes.api.admin.admin_routes import admin_blueprint
    from .routes.api.handlers_routes import handlers_blueprint
    from .routes.main_routes import main_blueprint
    from .routes.pages.pages_routes import pages_blueprint

    with app.app_context():
        app.register_blueprint(main_blueprint)
        app.register_blueprint(pages_blueprint)
        app.register_blueprint(admin_blueprint)
        app.register_blueprint(handlers_blueprint)

        try:
            app.logger.info(
                "A inicializar o motor da base de dados e tabelas a partir de app factory..."
            )
            init_db_engine_with_context(app)
            app.logger.info(
                "Motor da base de dados e tabelas inicializados com sucesso."
            )
        except Exception as e:
            app.logger.error(
                f"Falha CRÍTICA ao inicializar a base de dados na app factory: {e}",
                exc_info=True,
            )

    app.logger.info("Aplicação criada e configurada com sucesso.")
    return app


PUBLIC_ENDPOINTS = ["/", "/login", "/login/", "/register", "/register/", "/api/login", "/api/login/", "/api/register", "/api/register/"]


@app.before_request
def require_jwt_for_all_requests():
    from flask import request
    from flask_jwt_extended import (
        verify_jwt_in_request,
        get_jwt_identity,
        exceptions as jwt_exceptions,
    )
    from .models.user import User

    # Tira a barra final se tiver, para padronizar
    path = request.path.rstrip("/")

    if path in (p.rstrip("/") for p in PUBLIC_ENDPOINTS):
        return

    # Arquivos estáticos, favicon, etc
    if request.path.startswith("/static/"):
        return

    # Exige JWT!
    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.filter_by(id=user_id).first()
        if not user:
            return {"msg": "Token inválido"}, 401
    except jwt_exceptions.NoAuthorizationError:
        return {"msg": "Token de autenticação ausente"}, 401
    except jwt_exceptions.JWTDecodeError:
        return {"msg": "Token inválido"}, 401


@jwt.invalid_token_loader
def invalid_token_callback(error):
    return redirect("/login")


@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    response = make_response('', 401)  # Corpo vazio, apenas status 401
    response.delete_cookie(app.config.get('JWT_ACCESS_COOKIE_NAME'))  # Nome do teu cookie
    return redirect('/login')


@jwt.unauthorized_loader
def missing_token_callback(error_string):
    return redirect('/login')


@jwt.needs_fresh_token_loader
def needs_fresh_token_callback(jwt_header, jwt_payload):
    return redirect('/login')


@jwt.revoked_token_loader
def revoked_token_callback(jwt_header, jwt_payload):
    return redirect('/login')

# Dica: trate outras situações também:
