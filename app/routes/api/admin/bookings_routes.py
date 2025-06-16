from flask import jsonify, request

from ....models.booking import Booking
from ....models.user import User
from ....services import bookings_service
from .admin_routes import admin_blueprint, logger
from ....cache import flaskCaching
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from ....db import sqlAlchemy

def _serialize_booking_details(booking: Booking):
    driver_info = None
    if booking.assigned_driver:
        driver_info = {
            "id": booking.assigned_driver.id,
            "name": f"{booking.assigned_driver.first_name} {booking.assigned_driver.last_name}",
        }

    user_info = None
    if booking.user:
        user_info = {
            "id": booking.user.id,
            "name": f"{booking.user.name}",
        }
    return {
        "id": booking.id,
        "passenger_name": booking.passenger_name,
        "passenger_phone": booking.passenger_phone,
        "date": booking.date.isoformat() if booking.date else None,
        "time": booking.time.isoformat() if booking.time else None,
        "duration_minutes": booking.duration_minutes,
        "pickup_location": booking.pickup_location,
        "dropoff_location": booking.dropoff_location,
        "passengers": booking.passengers,
        "bags": booking.bags,
        "instructions": booking.instructions,
        "original_budget_pre_vat": booking.original_budget_pre_vat,
        "discount_amount": booking.discount_amount,
        "final_budget_pre_vat": booking.final_budget_pre_vat,
        "vat_percentage": booking.vat_percentage,
        "vat_amount": booking.vat_amount,
        "total_with_vat": booking.total_with_vat,
        "applied_voucher_code": booking.applied_voucher_code,
        "status": booking.status,
        "assigned_driver_id": booking.assigned_driver_id,
        "assigned_driver": driver_info,
        "created_at": booking.created_at.isoformat() if booking.created_at else None,
        "user_id": booking.user_id,
        "user": user_info,
    }


from ....cache import flaskCaching

cache = flaskCaching


@admin_blueprint.route("/admin/bookings", methods=["GET"])
@cache.cached(timeout=60, key_prefix="admin_all_bookings")
def admin_get_all_bookings_ep():
    try:
        all_bookings_orm = bookings_service.get_all_bookings()
        return jsonify([_serialize_booking_details(b) for b in all_bookings_orm]), 200
    except Exception as e:
        logger.error(f"Admin: Erro ao obter todas as reservas: {e}", exc_info=True)
        return jsonify({"error": "Erro interno ao obter as reservas."}), 500


@admin_blueprint.route("/admin/bookings/<int:booking_id>", methods=["DELETE"])
def admin_delete_booking_ep(booking_id):
    try:
        success = bookings_service.delete_booking_by_id(booking_id)
        if success:
            cache.delete("admin_all_bookings")
            return jsonify({"message": f"Reserva ID {booking_id} excluída."}), 200
        else:
            return jsonify({"error": f"Reserva ID {booking_id} não encontrada."}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro excluir reserva {booking_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/bookings/<int:booking_id>/status", methods=["PATCH"])
def admin_update_booking_status_ep(booking_id):
    if not request.is_json:
        return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json()
    new_status = data.get("status")
    if not new_status:
        return jsonify({"error": "Campo 'status' obrigatório."}), 400
    try:
        updated_booking = bookings_service.update_booking_status(booking_id, new_status)
        if updated_booking:
            cache.delete("admin_all_bookings")
            return jsonify(_serialize_booking_details(updated_booking)), 200
        else:
            return jsonify({"error": f"Reserva ID {booking_id} não encontrada."}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro update status {booking_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/bookings/<int:booking_id>/assign", methods=["PATCH"])
def admin_assign_driver_ep(booking_id):
    if not request.is_json:
        return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json()
    driver_id_str = data.get("driver_id")
    driver_id = None
    if (
        driver_id_str is not None
        and str(driver_id_str).lower() != "null"
        and str(driver_id_str).strip() != ""
    ):
        try:
            driver_id = int(driver_id_str)
        except (ValueError, TypeError):
            return jsonify({"error": "driver_id inválido."}), 400
    try:
        updated_booking = bookings_service.assign_driver_to_booking(
            booking_id, driver_id
        )
        if updated_booking:
            cache.delete("admin_all_bookings")
            return jsonify(_serialize_booking_details(updated_booking)), 200
        else:
            return jsonify({"error": f"Reserva ID {booking_id} não encontrada."}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro assign driver {booking_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500
    
    
@admin_blueprint.route("/admin/bookings/<int:booking_id>/field", methods=["PATCH"])
@jwt_required()
def admin_patch_booking_field(booking_id):
    current_user = get_jwt_identity()
    if not current_user:
        return jsonify({"error": "Utilizador nao autenticado"}), 401
    
    if current_user.get("role", "").lower() != "admin":
        return jsonify({"error": "Acesso negado."}), 403
    
    if not request.is_json:
        return jsonify({"error": "Requisição deve ser JSON"}), 400
    data = request.get_json()
    field = data.get("field")
    value = data.get("value")
    # Validação básica
    allowed_fields = {
        "passenger_name", "passenger_phone", "date", "time", "duration_minutes",
        "pickup_location", "dropoff_location", "passengers", "bags", "instructions"
    }
    if field not in allowed_fields:
        return jsonify({"error": "Campo não editável"}), 400
    try:
        updated_booking = bookings_service.update_booking_field(booking_id, field, value)
        if updated_booking:
            cache.delete("admin_all_bookings")
            return jsonify(_serialize_booking_details(updated_booking)), 200
        else:
            return jsonify({"error": f"Reserva ID {booking_id} não encontrada."}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro ao atualizar campo {field} ({booking_id}): {e}", exc_info=True)
        return jsonify({"error": "Erro interno ao atualizar reserva."}), 500


@admin_blueprint.route('/my-bookings', methods=['GET'])
@jwt_required()
def my_bookings():
    jwt_data = get_jwt()
    identity = get_jwt_identity()
    user_role = jwt_data.get("role", None)

    if user_role != "user" and user_role != "admin" and user_role != "partner":
        return jsonify({"msg": "Acesso restrito a utilizadores"}), 403

    user_id = int(identity)

    user = sqlAlchemy.session.query(User).filter_by(id=user_id).first()
    if not user:
        return jsonify({"msg": "Utilizador não encontrado"}), 404

    bookings = bookings_service.get_bookings_for_user(user_id)

    results = [{
        "id": b.id,
        "date": b.date.isoformat(),
        "time": b.time.strftime("%H:%M"),
        "pickup_location": b.pickup_location,
        "dropoff_location": b.dropoff_location,
        "status": b.status,
        "total_with_vat": float(b.total_with_vat)
    } for b in bookings]

    return jsonify({"bookings": results}), 200