from flask import Blueprint, render_template
from logging import getLogger

main_blueprint = Blueprint(
    name="main",
    import_name=__name__,
    template_folder="pages/templates",
    static_folder="pages/static",
)

logger = getLogger(__name__)
