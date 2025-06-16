import logging
import os

from app import create_app

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

profile = os.environ.get("FLASK_PROFILE", "config.Development")
app = create_app(config_object_name=profile)

if profile == "config.Development":
    logger.warning("Modo Desenvolvimento ativado.")

if __name__ == "__main__":
    host = app.config.get("HOST", "127.0.0.1")
    port = app.config.get("PORT", 5000)
    debug_mode = app.config.get("DEBUG", False)

    logger.info(f"A iniciar o servidor Flask em http://{host}:{port}/")
    logger.info(f"Modo Debug: {'Ativado' if debug_mode else 'Desativado'}")

    app.run(host=host, port=port, debug=debug_mode)
