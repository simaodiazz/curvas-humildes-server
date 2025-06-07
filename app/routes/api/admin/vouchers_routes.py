from flask import jsonify, request

from ....models.voucher import Voucher
from ....services import vouchers_service
from .admin_routes import admin_blueprint, logger


def _serialize_voucher_details(voucher: Voucher):
    if not voucher:
        return None
    return {
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
    }


@admin_blueprint.route("/admin/vouchers", methods=["POST"])
def admin_create_voucher_ep():
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
        return jsonify(_serialize_voucher_details(new_voucher)), 201
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro criar voucher: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/vouchers", methods=["GET"])
def admin_get_all_vouchers_ep():
    try:
        all_vouchers_orm = vouchers_service.get_all_vouchers()
        return jsonify([_serialize_voucher_details(v) for v in all_vouchers_orm]), 200
    except Exception as e:
        logger.error(f"Admin: Erro obter vouchers: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/vouchers/<int:voucher_id>", methods=["GET"])
def admin_get_voucher_ep(voucher_id):
    try:
        voucher = vouchers_service.get_voucher_by_id(voucher_id)
        if voucher:
            return jsonify(_serialize_voucher_details(voucher)), 200
        else:
            return jsonify({"error": f"Voucher ID {voucher_id} não encontrado."}), 404
    except Exception as e:
        logger.error(f"Admin: Erro obter voucher {voucher_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/vouchers/<int:voucher_id>", methods=["PATCH"])
def admin_update_voucher_ep(voucher_id):
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
def admin_delete_voucher_ep(voucher_id):
    try:
        success = vouchers_service.delete_voucher(voucher_id)
        if success:
            return "", 204
        else:
            return jsonify({"error": f"Voucher ID {voucher_id} não encontrado."}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro excluir voucher {voucher_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500
