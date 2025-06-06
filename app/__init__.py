# CurvasSistema/app/__init__.py
from flask import Flask
from flask_cors import CORS
from flask_mail import Mail
import logging
import os

from .models import db, init_db_engine_with_context

cors = CORS()
mail = Mail()

def create_app(config_object_name='config_main'):
    """
    App factory: cria e configura a instância da aplicação Flask.
    """
    from . import routes

    app = Flask(__name__, instance_relative_config=True)

    app.config.from_object(config_object_name)

    if not os.path.exists(app.instance_path):
        try:
            os.makedirs(app.instance_path)
        except OSError:
            logging.getLogger(__name__).error(f"Não foi possível criar a pasta instance em {app.instance_path}")

    app.config.from_pyfile('config.py', silent=True)

    if not app.debug and not app.testing:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        app.logger.addHandler(stream_handler)

    app.logger.setLevel(logging.INFO)
    app.logger.info('Aplicação Curvas Humildes a iniciar...')

    cors.init_app(app)
    mail.init_app(app)
    db.init_app(app)

    with app.app_context():
        from . import routes
        app.register_blueprint(routes.main_bp)

        try:
            app.logger.info("A inicializar o motor da base de dados e tabelas a partir de app factory...")
            init_db_engine_with_context(app)
            app.logger.info("Motor da base de dados e tabelas inicializados com sucesso.")
        except Exception as e:
            app.logger.error(f"Falha CRÍTICA ao inicializar a base de dados na app factory: {e}", exc_info=True)

    app.logger.info("Aplicação criada e configurada com sucesso.")
    return app
