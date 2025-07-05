from logging import getLogger
from flask import Blueprint, render_template, jsonify, redirect, url_for
from flask_jwt_extended import jwt_required, verify_jwt_in_request
from ..authentication_routes import get_role

pages_blueprint = Blueprint(
    name="pages",
    import_name=__name__,
    template_folder="templates",
    static_folder="static",
)
logger = getLogger(__name__)


@pages_blueprint.route("/reserve", methods=["GET"])
def reserve_page():
    return render_template("reserve.html")


@pages_blueprint.route("/login", methods=["GET"])
def login_page():
    try:
        verify_jwt_in_request()
        return redirect(url_for("pages.painel_dashboard"))
    except Exception:
        return render_template("login.html")


@pages_blueprint.route("/dashboard")
@jwt_required()
def painel_dashboard():
    role = get_role()
    if role == "admin":
        return redirect(url_for("pages.painel_admin"))
    if role == "user":
        return redirect(url_for("pages.painel_client"))
    elif role == "partner":
        return redirect(url_for("pages.painel_partner"))
    return jsonify({"error": "Acesso negado."}), 403


@pages_blueprint.route("/dashboard/client")
@jwt_required()
def painel_client():
    role = get_role()
    if role == "user":
        return render_template("client.html")
    return jsonify({"error": "Acesso negado."}), 403


@pages_blueprint.route("/dashboard/partner")
@jwt_required()
def painel_partner():
    role = get_role()
    if role == "partner" or role == "admin":
        return render_template("partner.html")
    return jsonify({"error": "Acesso negado."}), 403


@pages_blueprint.route("/register", methods=["GET"])
def pagina_register():
    return render_template("register.html")


@pages_blueprint.route("/dashboard/admin")
@jwt_required()
def painel_admin():
    role = get_role()
    if role == "admin":
        return render_template("admin/index.html")
    return jsonify({"error": "Acesso negado."}), 403


@pages_blueprint.route("/dashboard/admin/bookings")
@jwt_required()
def admin_bookings():
    role = get_role()
    if role == "admin":
        return render_template("admin/bookings.html")
    return jsonify({"error": "Acesso negado."}), 403


@pages_blueprint.route("/dashboard/admin/drivers")
@jwt_required()
def admin_drivers():
    role = get_role()
    if role == "admin":
        return render_template("admin/drivers.html")
    return jsonify({"error": "Acesso negado."}), 403


@pages_blueprint.route("/dashboard/admin/vehicles")
@jwt_required()
def admin_vehicles():
    role = get_role()
    if role == "admin":
        return render_template("admin/vehicles.html")
    return jsonify({"error": "Acesso negado."}), 403


@pages_blueprint.route("/dashboard/admin/tariffs")
@jwt_required()
def admin_tariffs():
    role = get_role()
    if role == "admin":
        return render_template("admin/tariffs.html")
    return jsonify({"error": "Acesso negado."}), 403


@pages_blueprint.route("/dashboard/admin/vouchers")
@jwt_required()
def admin_vouchers():
    """
    Painel apenas para admin.
    """
    role = get_role()
    if role == "admin":
        return render_template("admin/vouchers.html")
    return jsonify({"error": "Acesso negado."}), 403


@pages_blueprint.route("/dashboard/admin/users")
@jwt_required()
def admin_users():
    """
    Painel apenas para admin.
    """
    role = get_role()
    if role == "admin":
        return render_template("admin/users.html")
    return jsonify({"error": "Acesso negado."}), 403

