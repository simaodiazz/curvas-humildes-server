from flask import jsonify, request

from ....models.booking import Booking
from ....services import bookings_service
from .admin_routes import admin_blueprint, logger
from ....cache import flaskCaching


def _serialize_booking_details(booking: Booking):
    driver_info = None
    if booking.assigned_driver:
        driver_info = {
            "id": booking.assigned_driver.id,
            "name": f"{booking.assigned_driver.first_name} {booking.assigned_driver.last_name}",
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
