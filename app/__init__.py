# CurvasSistema/app/__init__.py
import logging
import os

from flask import Flask
from flask_cors import CORS
from flask_mail import Mail

from .db import init_db_engine_with_context, sqlAlchemy
from .cache import flaskCaching

cors = CORS()
mail = Mail()


def create_app(config_object_name="config"):
    """
    App factory: cria e configura a instância da aplicação Flask.
    """

    app = Flask(__name__, instance_relative_config=True)

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

    from .routes.api.admin.admin_routes import admin_blueprint
    from .routes.api.handlers_routes import handlers_blueprint
    from .routes.main_routes import main_blueprint
    from .routes.pages.pages_routes import pages_blueprint

    with app.app_context():
        app.register_blueprint(main_blueprint)
        app.register_blueprint(pages_blueprint)
        app.register_blueprint(handlers_blueprint)
        app.register_blueprint(admin_blueprint)

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
