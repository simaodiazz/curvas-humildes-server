from os import path

from flask import current_app, jsonify, send_from_directory
from flask_jwt_extended import jwt_required

from .authentication_routes import get_role
from .main_routes import logger, main_blueprint


@main_blueprint.route("/driver-app/")
@main_blueprint.route("/driver-app/<path:filename>")
@jwt_required()
def motorista_app_files(filename="index.html"):
    if get_role() != "driver":
        return jsonify({"error": "Acesso negado."}), 403
    """Serve os ficheiros estáticos da aplicação do motorista (Capacitor www)."""
    driver_app_folder = path.join(
        current_app.root_path, "app", "driver_frontend", "www"
    )
    logger.info(
        f"Tentando servir '{filename}' da app do motorista a partir de {driver_app_folder}"
    )
    if not path.exists(path.join(driver_app_folder, filename)):
        if path.exists(path.join(driver_app_folder, "index.html")):
            logger.info(
                f"Ficheiro '{filename}' não encontrado, servindo 'index.html' da app do motorista."
            )
            return send_from_directory(driver_app_folder, "index.html")
        else:
            logger.error(
                f"Nem '{filename}' nem 'index.html' encontrados em {driver_app_folder}"
            )
            return (
                jsonify(
                    {"error": "Ficheiro da aplicação do motorista não encontrado."}
                ),
                404,
            )
    return send_from_directory(driver_app_folder, filename)
