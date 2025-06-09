from flask import jsonify, request
from ....models.tariff_settings import TariffSettings
from ....services import tariff_settings_service
from .admin_routes import admin_blueprint, logger
from ....cache import flaskCaching
from flask_login import login_required


@admin_blueprint.route("/admin/settings/tariffs", methods=["GET"])
@flaskCaching.cached(
    timeout=60, key_prefix="admin_get_tariff_settings"
)  # cache por 60s
@login_required
def admin_get_tariff_settings_ep():
    try:
        current_settings = tariff_settings_service.get_active_tariff_settings()
        return jsonify(_serialize_tariff_settings_details(current_settings)), 200
    except ValueError as ve:
        logger.error(f"Admin: Erro obter tarifas: {ve}", exc_info=True)
        return jsonify({"error": str(ve)}), 500
    except Exception as e:
        logger.error(f"Admin: Erro inesperado obter tarifas: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


@admin_blueprint.route("/admin/settings/tariffs", methods=["PUT"])
@login_required
def admin_update_tariff_settings_ep():
    if not request.is_json:
        return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json()
    try:
        updated_settings = tariff_settings_service.update_tariff_settings(data)
        # Limpa o cache da rota GET após update
        flaskCaching.delete("admin_get_tariff_settings")
        return jsonify(_serialize_tariff_settings_details(updated_settings)), 200
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Admin: Erro update tarifas: {e}", exc_info=True)
        return jsonify({"error": "Erro interno."}), 500


def _serialize_tariff_settings_details(settings: TariffSettings):
    if not settings:
        return {}
    return {
        "id": settings.id,
        "base_rate_eur": settings.base_rate_eur,
        "rate_per_km_eur": settings.rate_per_km_eur,
        "rate_per_passenger_eur": settings.rate_per_passenger_eur,
        "rate_per_bag_eur": settings.rate_per_bag_eur,
        "night_surcharge_applies": settings.night_surcharge_applies,
        "night_surcharge_percentage": settings.night_surcharge_percentage,
        "night_surcharge_start_hour": settings.night_surcharge_start_hour,
        "night_surcharge_end_hour": settings.night_surcharge_end_hour,
        "booking_slot_overlap_minutes": settings.booking_slot_overlap_minutes,
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    }
