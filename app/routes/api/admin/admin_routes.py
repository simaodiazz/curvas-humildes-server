from flask import current_app, jsonify, request, Blueprint
from logging import getLogger

admin_blueprint = Blueprint(
    name="admin",
    import_name=__name__,
    template_folder="pages/templates",
    static_folder="pages/static",
)

logger = getLogger(__name__)
