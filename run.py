# CurvasSistema/run.py
from app import create_app
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = create_app()

if __name__ == '__main__':
    host = app.config.get('HOST', '127.0.0.1')
    port = app.config.get('PORT', 5000) 
    debug_mode = app.config.get('DEBUG', False)

    logger.info(f"A iniciar o servidor Flask em http://{host}:{port}/")
    logger.info(f"Modo Debug: {'Ativado' if debug_mode else 'Desativado'}")
    
    app.run(host=host, port=port, debug=debug_mode)
