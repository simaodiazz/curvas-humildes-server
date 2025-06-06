from ..models.tariff_settings import TariffSettings
from flask import current_app, request
from ..db import sqlAlchemy
from logging import getLogger
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from .tariff_settings_service import get_active_tariff_settings

import re
import requests
import datetime

logger = getLogger(__name__)


def _normalize_location_string(location_str: str) -> str:
    if not location_str:
        return ""
    s = location_str.lower()
    s = re.sub(r"[áàâãä]", "a", s)
    s = re.sub(r"[éèêë]", "e", s)
    s = re.sub(r"[íìîï]", "i", s)
    s = re.sub(r"[óòôõö]", "o", s)
    s = re.sub(r"[úùûü]", "u", s)
    s = re.sub(r"[ç]", "c", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _geocode_location_ors(location_name: str) -> tuple | None:
    if not location_name:
        return None
    api_key = current_app.config.get("MAPS_API_KEY")
    if not api_key:
        logger.error("MAPS_API_KEY não configurada para OpenRouteService.")
        return None
    geocode_url = "https://api.openrouteservice.org/geocode/search"
    params = {
        "api_key": api_key,
        "text": location_name,
        "size": 1,
        "boundary.country": "PRT",
    }
    try:
        response = requests.get(geocode_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and data.get("features") and len(data["features"]) > 0:
            return tuple(data["features"][0]["geometry"]["coordinates"])
        logger.warning(f"Nenhum resultado de geocodificação para: {location_name}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na API de Geocodificação ORS para '{location_name}': {e}")
        return None
    except Exception as e_unexp:
        logger.error(
            f"Erro inesperado na Geocodificação ORS para '{location_name}': {e_unexp}",
            exc_info=True,
        )
        return None


def _get_route_details_from_maps_api(
    pickup_location_name: str, dropoff_location_name: str
) -> dict:
    if current_app.config.get("MAPS_API_PROVIDER") != "OPENROUTESERVICE":
        logger.warning("MAPS_API_PROVIDER não está configurado para OPENROUTESERVICE.")
        return {
            "distance_km": 20.0,
            "duration_minutes": 30.0,
            "error": "API de mapas não configurada corretamente para ORS.",
        }

    pickup_coords = _geocode_location_ors(pickup_location_name)
    if not pickup_coords:
        return {
            "distance_km": 0,
            "duration_minutes": 0,
            "error": f"Não foi possível geocodificar o local de partida: '{pickup_location_name}'.",
        }

    dropoff_coords = _geocode_location_ors(dropoff_location_name)
    if not dropoff_coords:
        return {
            "distance_km": 0,
            "duration_minutes": 0,
            "error": f"Não foi possível geocodificar o local de destino: '{dropoff_location_name}'.",
        }

    api_key = current_app.config.get("MAPS_API_KEY")
    if not api_key:
        logger.error("MAPS_API_KEY não configurada para direções ORS.")
        return {
            "distance_km": 0,
            "duration_minutes": 0,
            "error": "Chave API de mapas não configurada.",
        }

    directions_url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    body = {"coordinates": [list(pickup_coords), list(dropoff_coords)], "units": "km"}

    try:
        response = requests.post(directions_url, json=body, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data and data.get("routes") and len(data["routes"]) > 0:
            summary = data["routes"][0].get("summary")
            if summary:
                distance_km = summary.get("distance", 0)
                duration_seconds = summary.get("duration", 0)
                duration_minutes = round(duration_seconds / 60)
                return {
                    "distance_km": round(distance_km, 2),
                    "duration_minutes": duration_minutes,
                }

        api_error_msg = data.get("error", {}).get(
            "message", "Nenhuma rota encontrada ou erro na API de direções."
        )
        logger.warning(
            f"Erro da API de Direções ORS: {api_error_msg} para rota {pickup_location_name} -> {dropoff_location_name}"
        )
        return {"distance_km": 0, "duration_minutes": 0, "error": api_error_msg}

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na API de Direções ORS: {e}")
        return {
            "distance_km": 0,
            "duration_minutes": 0,
            "error": f"Erro de comunicação com a API de direções: {e}",
        }
    except Exception as e_unexp:
        logger.error(
            f"Erro inesperado na API de Direções ORS: {e_unexp}", exc_info=True
        )
        return {
            "distance_km": 0,
            "duration_minutes": 0,
            "error": f"Erro inesperado ao obter direções: {e_unexp}",
        }


def calculate_estimated_budget(
    data: dict, request_time_obj: datetime.time = None
) -> dict:
    try:
        tariff_settings = get_active_tariff_settings()
        if not tariff_settings:
            raise ValueError("Configurações de tarifa não disponíveis.")

        num_passengers = int(data.get("passengers", 1))
        num_bags = int(data.get("bags", 0))
        pickup_location_raw = str(data.get("pickupLocation", ""))
        dropoff_location_raw = str(data.get("dropoffLocation", ""))

        if num_passengers < 1:
            raise ValueError("Número de passageiros deve ser pelo menos 1.")
        if num_bags < 0:
            raise ValueError("Número de malas não pode ser negativo.")
        if not pickup_location_raw.strip():
            raise ValueError("Local de partida é obrigatório.")
        if not dropoff_location_raw.strip():
            raise ValueError("Local de destino é obrigatório.")

        norm_pickup = _normalize_location_string(pickup_location_raw)
        norm_dropoff = _normalize_location_string(dropoff_location_raw)
        route_key = f"{norm_pickup}#{norm_dropoff}"

        budget_pre_vat = 0.0
        duration_minutes = 0

        predefined_routes_config = current_app.config.get("PREDEFINED_ROUTES", {})
        if route_key in predefined_routes_config:
            budget_pre_vat = predefined_routes_config[route_key]
            route_details_for_duration = _get_route_details_from_maps_api(
                pickup_location_raw, dropoff_location_raw
            )
            duration_minutes = route_details_for_duration.get("duration_minutes", 60)
        else:
            route_details = _get_route_details_from_maps_api(
                pickup_location_raw, dropoff_location_raw
            )
            if route_details.get("error"):
                raise ValueError(
                    f"Erro ao calcular orçamento: {route_details['error']}"
                )

            distance_km = route_details["distance_km"]
            duration_minutes = route_details["duration_minutes"]

            if distance_km <= 0 and not (norm_pickup == norm_dropoff):
                raise ValueError("Distância inválida calculada pela API de mapas.")

            budget_pre_vat = tariff_settings.base_rate_eur + (
                distance_km * tariff_settings.rate_per_km_eur
            )

        if num_passengers > 1:
            budget_pre_vat += (
                num_passengers - 1
            ) * tariff_settings.rate_per_passenger_eur
        if num_bags > 0:
            budget_pre_vat += num_bags * tariff_settings.rate_per_bag_eur

        if tariff_settings.night_surcharge_applies:
            current_time_for_fare = (
                request_time_obj if request_time_obj else datetime.datetime.now().time()
            )
            is_night_fare = False
            start_night = datetime.time(tariff_settings.night_surcharge_start_hour, 0)
            end_night = datetime.time(tariff_settings.night_surcharge_end_hour, 0)

            if start_night > end_night:
                if (
                    current_time_for_fare >= start_night
                    or current_time_for_fare < end_night
                ):
                    is_night_fare = True
            else:
                if start_night <= current_time_for_fare < end_night:
                    is_night_fare = True

            if is_night_fare:
                budget_pre_vat += (
                    budget_pre_vat * tariff_settings.night_surcharge_percentage
                ) / 100.0

        original_budget_pre_vat = round(budget_pre_vat, 2)

        vat_percentage = current_app.config.get("VAT_RATE", 23.0)
        vat_amount = round(original_budget_pre_vat * (vat_percentage / 100.0), 2)
        total_with_vat = round(original_budget_pre_vat + vat_amount, 2)

        logger.info(
            f"Orçamento Calculado: Base (s/IVA) {original_budget_pre_vat:.2f}, IVA ({vat_percentage}%) {vat_amount:.2f}, Total {total_with_vat:.2f}, Duração {duration_minutes} min"
        )

        return {
            "original_budget_pre_vat": original_budget_pre_vat,
            "final_budget_pre_vat": original_budget_pre_vat,
            "vat_percentage": vat_percentage,
            "vat_amount": vat_amount,
            "total_with_vat": total_with_vat,
            "duration_minutes": duration_minutes,
            "discount_amount": 0.0,
            "applied_voucher_code": None,
        }

    except ValueError as ve:
        logger.error(f"Erro de valor ao calcular orçamento: {ve}")
        raise
    except Exception as e_unexp:
        logger.error(f"Erro inesperado ao calcular orçamento: {e_unexp}", exc_info=True)
        raise ValueError("Erro interno inesperado ao calcular o orçamento.")
