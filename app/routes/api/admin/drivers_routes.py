from flask import jsonify, request

from ....models.driver import Driver
from ....services import drivers_service
from .admin_routes import admin_blueprint, logger
from ....cache import flaskCaching
from ...authentication_routes import get_role
from flask_jwt_extended import jwt_required


def _serialize_driver_details(driver: Driver):
    return {
        "id": driver.id,
        "first_name": driver.first_name,
        "last_name": driver.last_name,
        "email": driver.email,
        "phone_number": driver.phone_number,
        "is_active": driver.is_active,
        "created_at": driver.created_at.isoformat() if driver.created_at else None,
    }


@admin_blueprint.route("/admin/drivers", methods=["POST"])
@jwt_required()
def admin_create_driver_ep():
    if get_role() != "admin":
        return jsonify({"error": "Acesso negado."}), 403
    if not request.is_json:
        return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json()
    required = ["first_name", "last_name"]
    if any(f not in data or not str(data[f]).strip() for f in required):
        return jsonify({"error": "Nome/Apelido obrigatórios."}), 400
    try:
        new_driver = drivers_service.create_driver(data)
        flaskCaching.delete_memoized(admin_get_all_drivers_ep)
        return jsonify(_serialize_driver_details(new_driver)), 201
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro criar motorista: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/drivers", methods=["GET"])
@flaskCaching.memoize(timeout=60)
@jwt_required()
def admin_get_all_drivers_ep():
    if get_role() != "admin":
        return jsonify({"error": "Acesso negado."}), 403
    only_active_param = request.args.get("active", default=None, type=str)
    only_active = (
        only_active_param.lower() == "true" if only_active_param is not None else None
    )
    try:
        all_drivers_orm = drivers_service.get_all_drivers(only_active=only_active)
        return jsonify([_serialize_driver_details(d) for d in all_drivers_orm]), 200
    except Exception as e:
        logger.error(f"Admin: Erro obter motoristas: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/drivers/<int:driver_id>", methods=["GET"])
@flaskCaching.memoize(timeout=60)
@jwt_required()
def admin_get_driver_ep(driver_id):
    if get_role() != "admin":
        return jsonify({"error": "Acesso negado."}), 403
    try:
        driver = drivers_service.get_driver_by_id(driver_id)
        if driver:
            return jsonify(_serialize_driver_details(driver)), 200
        else:
            return jsonify({"error": f"Motorista ID {driver_id} não encontrado."}), 404
    except Exception as e:
        logger.error(f"Admin: Erro obter motorista {driver_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/drivers/<int:driver_id>", methods=["PATCH"])
@jwt_required()
def admin_update_driver_ep(driver_id):
    if get_role() != "admin":
        return jsonify({"error": "Acesso negado."}), 403
    if not request.is_json:
        return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json()
    valid_fields = ["first_name", "last_name", "email", "phone_number", "is_active"]
    if not any(f in data for f in valid_fields):
        return jsonify({"error": "Nenhum campo válido."}), 400
    try:
        updated_driver = drivers_service.update_driver(driver_id, data)
        if updated_driver:
            # Limpeza correta do cache memoize ao nível da rota
            flaskCaching.delete_memoized(admin_get_all_drivers_ep)
            flaskCaching.delete_memoized(admin_get_driver_ep, driver_id)
            return jsonify(_serialize_driver_details(updated_driver)), 200
        else:
            return jsonify({"error": f"Motorista ID {driver_id} não encontrado."}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro update motorista {driver_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/drivers/<int:driver_id>", methods=["DELETE"])
@jwt_required()
def admin_delete_driver_ep(driver_id):
    if get_role() != "admin":
        return jsonify({"error": "Acesso negado."}), 403
    try:
        success = drivers_service.delete_driver_by_id(driver_id)
        if success:
            flaskCaching.delete_memoized(admin_get_all_drivers_ep)
            flaskCaching.delete_memoized(admin_get_driver_ep, driver_id)
            return "", 204
        else:
            return jsonify({"error": f"Motorista ID {driver_id} não encontrado."}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro excluir motorista {driver_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500
