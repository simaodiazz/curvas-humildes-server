from logging import getLogger

from flask import Blueprint

admin_blueprint = Blueprint(
    name="admin",
    import_name=__name__,
)

logger = getLogger(__name__)
