from flask import jsonify, request
from ....models.voucher import Voucher
from ....services import vouchers_service
from .admin_routes import admin_blueprint, logger
from ....cache import flaskCaching
from ...authentication_routes import get_role
from flask_jwt_extended import jwt_required

def _serialize_voucher_details(voucher: Voucher):
    if not voucher:
        return None
    result = {
        "id": voucher.id,
        "code": voucher.code,
        "description": voucher.description,
        "discount_type": voucher.discount_type,
        "discount_value": voucher.discount_value,
        "expiration_date": (
            voucher.expiration_date.isoformat() if voucher.expiration_date else None
        ),
        "max_uses": voucher.max_uses,
        "current_uses": voucher.current_uses,
        "min_booking_value": voucher.min_booking_value,
        "is_active": voucher.is_active,
        "created_at": voucher.created_at.isoformat() if voucher.created_at else None,
        "updated_at": voucher.updated_at.isoformat() if voucher.updated_at else None,
        "user_id": voucher.user_id
    }
    # serializar partner ou user se existir (opcional)
    if hasattr(voucher, "user") and voucher.user is not None:
        result["user"] = {
            "id": voucher.user.id,
            "name": voucher.user.name,
            "email": voucher.user.email
        }
    return result

@admin_blueprint.route("/admin/vouchers", methods=["POST"])
@jwt_required()
def admin_create_voucher_ep():
    if get_role() != "admin":
        return jsonify({"error": "Acesso negado."}), 403
    if not request.is_json:
        return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json()
    if not data.get("code") or not str(data["code"]).strip():
        return jsonify({"error": "Código obrigatório."}), 400
    if data.get("discount_value") is None:
        return jsonify({"error": "Valor desconto obrigatório."}), 400
    if not data.get("discount_type"):
        return jsonify({"error": "Tipo desconto obrigatório."}), 400
    try:
        new_voucher = vouchers_service.create_voucher(data)
        flaskCaching.delete("admin_get_all_vouchers")  # Limpa cache após criar
        return jsonify(_serialize_voucher_details(new_voucher)), 201
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro criar voucher: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500

@admin_blueprint.route("/admin/vouchers", methods=["GET"])
@flaskCaching.cached(timeout=60, key_prefix="admin_get_all_vouchers")
@jwt_required()
def admin_get_all_vouchers_ep():
    if get_role() != "admin":
        return jsonify({"error": "Acesso negado."}), 403
    try:
        all_vouchers_orm = vouchers_service.get_all_vouchers()
        return jsonify([_serialize_voucher_details(v) for v in all_vouchers_orm]), 200
    except Exception as e:
        logger.error(f"Admin: Erro obter vouchers: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500

@admin_blueprint.route("/admin/vouchers/<int:voucher_id>", methods=["GET"])
@flaskCaching.cached(
    timeout=60,
    key_prefix=lambda: f"admin_get_voucher_{request.view_args['voucher_id']}",
)
@jwt_required()
def admin_get_voucher_ep(voucher_id):
    if get_role() != "admin":
        return jsonify({"error": "Acesso negado."}), 403
    try:
        voucher = vouchers_service.get_voucher_by_id(voucher_id)
        if voucher:
            return jsonify(_serialize_voucher_details(voucher)), 200
        else:
            return jsonify({"error": f"Voucher ID {voucher_id} não encontrado."}), 404
    except Exception as e:
        logger.error(f"Admin: Erro obter voucher {voucher_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500

@admin_blueprint.route("/admin/vouchers/<int:voucher_id>", methods=["PATCH", "PUT"])
@jwt_required()
def admin_update_voucher_ep(voucher_id):
    if get_role() != "admin":
        return jsonify({"error": "Acesso negado."}), 403
    if not request.is_json:
        return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json()
    valid_fields = [
        "description",
        "discount_type",
        "discount_value",
        "expiration_date",
        "max_uses",
        "min_booking_value",
        "is_active",
    ]
    if not any(f in data for f in valid_fields):
        return jsonify({"error": "Nenhum campo válido."}), 400
    try:
        updated_voucher = vouchers_service.update_voucher(voucher_id, data)
        flaskCaching.delete("admin_get_all_vouchers")
        flaskCaching.delete(f"admin_get_voucher_{voucher_id}")
        if updated_voucher:
            return jsonify(_serialize_voucher_details(updated_voucher)), 200
        else:
            return jsonify({"error": f"Voucher ID {voucher_id} não encontrado."}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro update voucher {voucher_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500

@admin_blueprint.route("/admin/vouchers/<int:voucher_id>", methods=["DELETE"])
@jwt_required()
def admin_delete_voucher_ep(voucher_id):
    if get_role() != "admin":
        return jsonify({"error": "Acesso negado."}), 403
    try:
        success = vouchers_service.delete_voucher(voucher_id)
        flaskCaching.delete("admin_get_all_vouchers")
        flaskCaching.delete(f"admin_get_voucher_{voucher_id}")
        if success:
            return "", 204
        else:
            return jsonify({"error": f"Voucher ID {voucher_id} não encontrado."}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro excluir voucher {voucher_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500

@admin_blueprint.route("/admin/vouchers/with_user", methods=["GET"])
@jwt_required()
def admin_get_all_vouchers_with_user_ep():
    if get_role() != "admin":
        return jsonify({"error": "Acesso negado."}), 403
    try:
        vouchers_with_user = vouchers_service.get_all_vouchers_with_user()
        return jsonify([_serialize_voucher_details(v) for v in vouchers_with_user]), 200
    except Exception as e:
        logger.error(f"Admin: Erro obter vouchers com user associado: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


from flask_jwt_extended import jwt_required, get_jwt_identity

from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

@admin_blueprint.route("/admin/vouchers/with_user/me", methods=["GET"])
@jwt_required()
def admin_get_all_vouchers_for_current_user():
    role = get_role()
    if role not in ("admin", "partner"):
        return jsonify({"error": "Acesso negado."}), 403

    user_id = get_jwt_identity()
    
    try:
        vouchers = vouchers_service.get_all_vouchers_by_user_id(user_id)
        return jsonify([_serialize_voucher_details(v) for v in vouchers]), 200
    except Exception as e:
        logger.error(f"Admin: Erro obter vouchers com user associado: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500