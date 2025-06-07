from logging import getLogger

from flask import Blueprint

admin_blueprint = Blueprint(
    name="admin",
    import_name=__name__,
    template_folder="pages/templates",
    static_folder="pages/static",
)

logger = getLogger(__name__)
