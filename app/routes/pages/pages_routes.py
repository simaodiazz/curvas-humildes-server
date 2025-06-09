from logging import getLogger

from flask import Blueprint, render_template
from flask_login import login_required


pages_blueprint = Blueprint(
    name="pages",
    import_name=__name__,
    template_folder="templates",
    static_folder="static",
)

logger = getLogger(__name__)


@pages_blueprint.route("/")
@login_required
def pagina_de_reservas():
    """Serve a página do formulário de reservas como a página principal."""
    logger.info(
        "A servir o formulário de reservas (reservas_form.html) como página principal."
    )
    return render_template("reservas_form.html")


@pages_blueprint.route("/admin")
@login_required
def painel_admin():
    """Serve a página de administração."""
    logger.info("A servir o painel de administração (admin.html).")
    return render_template("admin.html")
