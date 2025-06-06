from flask import jsonify, request
from .admin_routes import admin_blueprint, logger
from ....models.vehicle import Vehicle

from ....services import drivers_service


def _serialize_vehicle_details(vehicle: Vehicle):
    return {
        "id": vehicle.id,
        "license_plate": vehicle.license_plate,
        "make": vehicle.make,
        "model": vehicle.model,
        "year": vehicle.year,
        "capacity_passengers": vehicle.capacity_passengers,
        "capacity_bags": vehicle.capacity_bags,
        "status": vehicle.status,
        "created_at": vehicle.created_at.isoformat() if vehicle.created_at else None,
    }


@admin_blueprint.route("/admin/vehicles", methods=["POST"])
def admin_create_vehicle_ep():
    if not request.is_json:
        return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json()
    if not data.get("license_plate") or not str(data["license_plate"]).strip():
        return jsonify({"error": "Matrícula obrigatória."}), 400
    try:
        new_vehicle = drivers_service.create_vehicle(data)
        return jsonify(_serialize_vehicle_details(new_vehicle)), 201
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro criar veículo: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/vehicles", methods=["GET"])
def admin_get_all_vehicles_ep():
    status_filter = request.args.get("status", default=None, type=str)
    try:
        all_vehicles_orm = drivers_service.get_all_vehicles(status_filter=status_filter)
        return jsonify([_serialize_vehicle_details(v) for v in all_vehicles_orm]), 200
    except Exception as e:
        logger.error(f"Admin: Erro obter veículos: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/vehicles/<int:vehicle_id>", methods=["GET"])
def admin_get_vehicle_ep(vehicle_id):
    try:
        vehicle = drivers_service.get_vehicle_by_id(vehicle_id)
        if vehicle:
            return jsonify(_serialize_vehicle_details(vehicle)), 200
        else:
            return jsonify({"error": f"Veículo ID {vehicle_id} não encontrado."}), 404
    except Exception as e:
        logger.error(f"Admin: Erro obter veículo {vehicle_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/vehicles/<int:vehicle_id>", methods=["PATCH"])
def admin_update_vehicle_ep(vehicle_id):
    if not request.is_json:
        return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json()
    valid_fields = [
        "license_plate",
        "make",
        "model",
        "year",
        "capacity_passengers",
        "capacity_bags",
        "status",
    ]
    if not any(f in data for f in valid_fields):
        return jsonify({"error": "Nenhum campo válido."}), 400
    try:
        updated_vehicle = drivers_service.update_vehicle(vehicle_id, data)
        if updated_vehicle:
            return jsonify(_serialize_vehicle_details(updated_vehicle)), 200
        else:
            return jsonify({"error": f"Veículo ID {vehicle_id} não encontrado."}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro update veículo {vehicle_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/vehicles/<int:vehicle_id>", methods=["DELETE"])
def admin_delete_vehicle_ep(vehicle_id):
    try:
        success = drivers_service.delete_vehicle_by_id(vehicle_id)
        if success:
            return "", 204
        else:
            return jsonify({"error": f"Veículo ID {vehicle_id} não encontrado."}), 404
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro excluir veículo {vehicle_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500
