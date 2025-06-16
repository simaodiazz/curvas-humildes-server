from logging import getLogger

from flask import Blueprint

main_blueprint = Blueprint(name="main", import_name=__name__)

logger = getLogger(__name__)
