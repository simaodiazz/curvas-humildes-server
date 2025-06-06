# CurvasSistema/app/services.py

from .models import db, Booking, Driver, Vehicle, TariffSettings, Voucher
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import joinedload
import datetime
import re
import requests
import logging
from flask_mail import Message
from flask import current_app

logger = logging.getLogger(__name__)

# --- Funções de Gestão de Tarifas ---
def get_active_tariff_settings() -> TariffSettings:
    try:
        settings = db.session.query(TariffSettings).filter(TariffSettings.id == 1).first()
        if not settings:
            logger.warning("Nenhuma config. tarifa (id=1). A criar padrão a partir de current_app.config.")
            try:
                default_settings = TariffSettings(
                    id=1,
                    base_rate_eur=current_app.config.get('BASE_RATE_EUR', 10.0),
                    rate_per_km_eur=current_app.config.get('RATE_PER_KM_EUR', 0.85),
                    rate_per_passenger_eur=current_app.config.get('RATE_PER_PASSENGER_EUR', 2.5),
                    rate_per_bag_eur=current_app.config.get('RATE_PER_BAG_EUR', 1.0),
                    night_surcharge_applies=current_app.config.get('NIGHT_SURCHARGE_APPLIES', True),
                    night_surcharge_percentage=current_app.config.get('NIGHT_SURCHARGE_PERCENTAGE', 20.0),
                    night_surcharge_start_hour=current_app.config.get('NIGHT_SURCHARGE_START_HOUR', 22),
                    night_surcharge_end_hour=current_app.config.get('NIGHT_SURCHARGE_END_HOUR', 6),
                    booking_slot_overlap_minutes=current_app.config.get('BOOKING_SLOT_OVERLAP_MINUTES', 30)
                )
                db.session.add(default_settings)
                db.session.commit()
                logger.info("Config. tarifa padrão criada.")
                return default_settings
            except IntegrityError as ie:
                db.session.rollback()
                logger.warning(f"Erro integridade criar tarifa padrão (provavelmente já existe): {ie}. Obtendo novamente.")
                settings = db.session.query(TariffSettings).filter(TariffSettings.id == 1).first()
                if settings: return settings
                else:
                    logger.error("Falha obter tarifa mesmo após erro integridade.")
                    raise ValueError("Não foi possível carregar/criar config. tarifa.")
            except SQLAlchemyError as e_inner:
                db.session.rollback()
                logger.error(f"Erro BD criar tarifa padrão: {e_inner}", exc_info=True)
                raise ValueError("Erro BD criar config. tarifa.")
        return settings
    except SQLAlchemyError as e_outer:
        logger.error(f"Erro BD geral obter tarifa: {e_outer}", exc_info=True)
        raise ValueError("Erro BD carregar config. tarifa.")
    except Exception as e_fatal:
        logger.error(f"Erro inesperado fatal obter tarifa: {e_fatal}", exc_info=True)
        raise ValueError("Erro inesperado carregar config. tarifa.")

def update_tariff_settings(settings_data: dict) -> TariffSettings:
    try:
        settings_to_update = db.session.query(TariffSettings).filter(TariffSettings.id == 1).first()
        if not settings_to_update:
            raise ValueError("Config. tarifa base (id=1) não encontrada para atualização.")
        
        logger.info(f"Atualizando config. tarifa. Dados recebidos: {settings_data}")
        
        field_map = {
            'base_rate_eur': (float, 'base_rate_eur'),
            'rate_per_km_eur': (float, 'rate_per_km_eur'),
            'rate_per_passenger_eur': (float, 'rate_per_passenger_eur'),
            'rate_per_bag_eur': (float, 'rate_per_bag_eur'),
            'night_surcharge_applies': (bool, 'night_surcharge_applies'),
            'night_surcharge_percentage': (float, 'night_surcharge_percentage'),
            'night_surcharge_start_hour': (int, 'night_surcharge_start_hour'),
            'night_surcharge_end_hour': (int, 'night_surcharge_end_hour'),
            'booking_slot_overlap_minutes': (int, 'booking_slot_overlap_minutes')
        }

        updated_fields = False
        for key, (value_type, model_attr) in field_map.items():
            if key in settings_data:
                try:
                    raw_value = settings_data[key]
                    if value_type == bool:
                        converted_value = str(raw_value).lower() in ['true', 'on', '1', 'yes']
                    else:
                        converted_value = value_type(raw_value)
                    
                    if model_attr in ['night_surcharge_start_hour', 'night_surcharge_end_hour'] and not (0 <= converted_value <= 23):
                        raise ValueError(f"{key} deve estar entre 0 e 23.")
                    if model_attr == 'night_surcharge_percentage' and not (0 <= converted_value <= 100):
                         raise ValueError(f"{key} deve estar entre 0 e 100.")

                    setattr(settings_to_update, model_attr, converted_value)
                    updated_fields = True
                except (ValueError, TypeError) as e_conv:
                    logger.warning(f"Erro ao converter o valor para '{key}': {raw_value} -> {value_type}. Erro: {e_conv}")
                    raise ValueError(f"Valor inválido para '{key}': {raw_value}.")

        if updated_fields:
            settings_to_update.updated_at = datetime.datetime.utcnow()
            db.session.commit()
            db.session.refresh(settings_to_update)
            logger.info(f"Config. tarifa atualizada: {settings_to_update}")
        else:
            logger.info("Nenhum campo de tarifa foi atualizado.")
            
        return settings_to_update
        
    except ValueError as ve:
        db.session.rollback()
        logger.warning(f"Erro de valor ao atualizar tarifas: {ve}")
        raise
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao atualizar tarifas: {e}", exc_info=True)
        raise ValueError("Erro de BD ao atualizar configurações de tarifa.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao atualizar tarifas: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao atualizar configurações de tarifa.")

# --- Funções de Gestão de Vouchers ---
def create_voucher(voucher_data: dict) -> Voucher:
    try:
        code = str(voucher_data.get('code', '')).strip().upper()
        if not code: raise ValueError("Código do voucher é obrigatório.")

        discount_type = str(voucher_data.get('discount_type', '')).upper()
        if discount_type not in ['PERCENTAGE', 'FIXED_AMOUNT']:
            raise ValueError("Tipo de desconto inválido. Deve ser 'PERCENTAGE' ou 'FIXED_AMOUNT'.")

        discount_value = float(voucher_data.get('discount_value', 0))
        if discount_value <= 0:
            raise ValueError("Valor do desconto deve ser maior que zero.")
        if discount_type == 'PERCENTAGE' and not (0 < discount_value <= 100):
            raise ValueError("Desconto em percentagem deve ser entre 0 (exclusivo) e 100 (inclusivo).")

        expiration_date_str = voucher_data.get('expiration_date')
        expiration_date = None
        if expiration_date_str and str(expiration_date_str).strip():
            try:
                expiration_date = datetime.datetime.strptime(expiration_date_str, '%Y-%m-%d').date()
            except ValueError:
                raise ValueError("Formato da data de validade inválido. Use AAAA-MM-DD.")

        max_uses = int(voucher_data.get('max_uses', 1))
        if max_uses < 0:
            raise ValueError("Máximo de usos deve ser 0 (ilimitado) ou maior.")

        min_booking_value_str = voucher_data.get('min_booking_value')
        min_booking_value = None
        if min_booking_value_str is not None and str(min_booking_value_str).strip() != "":
            try:
                min_booking_value = float(min_booking_value_str)
                if min_booking_value < 0:
                    raise ValueError("Valor mínimo da reserva não pode ser negativo.")
            except ValueError:
                raise ValueError("Valor mínimo da reserva deve ser um número válido.")

        new_voucher = Voucher(
            code=code,
            description=voucher_data.get('description'),
            discount_type=discount_type,
            discount_value=discount_value,
            expiration_date=expiration_date,
            max_uses=max_uses,
            min_booking_value=min_booking_value,
            is_active=voucher_data.get('is_active', True)
        )
        db.session.add(new_voucher)
        db.session.commit()
        db.session.refresh(new_voucher)
        return new_voucher
    except IntegrityError:
        db.session.rollback()
        raise ValueError(f"Voucher com o código '{code}' já existe.")
    except ValueError as ve:
        db.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao criar voucher: {e}", exc_info=True)
        raise ValueError("Erro de base de dados ao criar o voucher.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao criar voucher: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao criar o voucher.")


def get_voucher_by_id(voucher_id: int) -> Voucher | None:
    try:
        return db.session.query(Voucher).filter(Voucher.id == voucher_id).first()
    except SQLAlchemyError as e:
        logger.error(f"Erro de BD ao obter voucher por ID {voucher_id}: {e}", exc_info=True)
        raise ValueError(f"Erro de BD ao obter voucher ID {voucher_id}.")

def get_voucher_by_code(code: str) -> Voucher | None:
    try:
        return db.session.query(Voucher).filter(Voucher.code == code.upper()).first()
    except SQLAlchemyError as e:
        logger.error(f"Erro de BD ao obter voucher por código {code}: {e}", exc_info=True)
        raise ValueError(f"Erro de BD ao obter voucher '{code}'.")

def get_all_vouchers() -> list[Voucher]:
    try:
        return db.session.query(Voucher).order_by(Voucher.created_at.desc()).all()
    except SQLAlchemyError as e:
        logger.error(f"Erro de BD ao obter todos os vouchers: {e}", exc_info=True)
        raise ValueError("Erro de BD ao obter todos os vouchers.")

def update_voucher(voucher_id: int, voucher_data: dict) -> Voucher | None:
    try:
        voucher_to_update = get_voucher_by_id(voucher_id)
        if not voucher_to_update:
            return None

        updated_fields = False
        if 'description' in voucher_data:
            voucher_to_update.description = voucher_data['description']
            updated_fields = True
        if 'discount_type' in voucher_data:
            discount_type = str(voucher_data['discount_type']).upper()
            if discount_type not in ['PERCENTAGE', 'FIXED_AMOUNT']:
                raise ValueError("Tipo de desconto inválido.")
            voucher_to_update.discount_type = discount_type
            updated_fields = True
        if 'discount_value' in voucher_data:
            discount_value = float(voucher_data['discount_value'])
            if discount_value <= 0: raise ValueError("Valor do desconto deve ser > 0.")
            if voucher_to_update.discount_type == 'PERCENTAGE' and not (0 < discount_value <= 100):
                 raise ValueError("Desconto em percentagem deve ser > 0 e <= 100.")
            voucher_to_update.discount_value = discount_value
            updated_fields = True
        if 'expiration_date' in voucher_data:
            exp_date_str = voucher_data['expiration_date']
            if exp_date_str and str(exp_date_str).strip():
                try:
                    voucher_to_update.expiration_date = datetime.datetime.strptime(exp_date_str, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError("Formato da data de validade inválido. Use AAAA-MM-DD.")
            else:
                voucher_to_update.expiration_date = None
            updated_fields = True
        if 'max_uses' in voucher_data:
            max_uses = int(voucher_data['max_uses'])
            if max_uses < 0: raise ValueError("Máximo de usos deve ser >= 0.")
            voucher_to_update.max_uses = max_uses
            updated_fields = True
        if 'min_booking_value' in voucher_data:
            min_val_str = voucher_data['min_booking_value']
            if min_val_str is not None and str(min_val_str).strip() != "":
                try:
                    min_val = float(min_val_str)
                    if min_val < 0: raise ValueError("Valor mínimo da reserva não pode ser negativo.")
                    voucher_to_update.min_booking_value = min_val
                except ValueError:
                    raise ValueError("Valor mínimo da reserva inválido.")
            else:
                voucher_to_update.min_booking_value = None
            updated_fields = True
        if 'is_active' in voucher_data:
            voucher_to_update.is_active = bool(voucher_data['is_active'])
            updated_fields = True
        
        if updated_fields:
            voucher_to_update.updated_at = datetime.datetime.utcnow()
            db.session.commit()
            db.session.refresh(voucher_to_update)
        return voucher_to_update
    except ValueError as ve:
        db.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao atualizar voucher {voucher_id}: {e}", exc_info=True)
        raise ValueError("Erro de BD ao atualizar o voucher.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao atualizar voucher {voucher_id}: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao atualizar o voucher.")

def delete_voucher(voucher_id: int) -> bool:
    try:
        voucher_to_delete = get_voucher_by_id(voucher_id)
        if voucher_to_delete:
            db.session.delete(voucher_to_delete)
            db.session.commit()
            return True
        return False
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao excluir voucher {voucher_id}: {e}", exc_info=True)
        if "FOREIGN KEY constraint failed" in str(e).lower():
             raise ValueError(f"Não é possível excluir o voucher ID {voucher_id} pois está referenciado noutros registos (ex: reservas).")
        raise ValueError("Erro de BD ao excluir o voucher.")
    except ValueError:
        db.session.rollback()
        raise
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao excluir voucher {voucher_id}: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao excluir o voucher.")


def validate_voucher_for_use(code: str, booking_budget_pre_vat: float | None = None) -> Voucher:
    if not code:
        raise ValueError("Código do voucher não pode ser vazio.")
    voucher = get_voucher_by_code(code)
    if not voucher:
        raise ValueError(f"Voucher '{code.upper()}' não encontrado.")
    if not voucher.is_active:
        raise ValueError(f"Voucher '{code.upper()}' não está ativo.")
    if voucher.expiration_date and voucher.expiration_date < datetime.date.today():
        raise ValueError(f"Voucher '{code.upper()}' expirou em {voucher.expiration_date.strftime('%d/%m/%Y')}.")
    if voucher.max_uses > 0 and voucher.current_uses >= voucher.max_uses:
        raise ValueError(f"Voucher '{code.upper()}' atingiu o limite máximo de utilizações.")
    if booking_budget_pre_vat is not None and voucher.min_booking_value is not None and booking_budget_pre_vat < voucher.min_booking_value:
        raise ValueError(f"Voucher '{code.upper()}' requer um valor mínimo de reserva (antes de IVA) de {voucher.min_booking_value:.2f} EUR.")
    return voucher

def apply_voucher_to_budget(original_budget_pre_vat: float, voucher: Voucher) -> tuple[float, float]:
    discount_amount = 0.0
    if voucher.discount_type == 'PERCENTAGE':
        discount_amount = (original_budget_pre_vat * voucher.discount_value) / 100.0
    elif voucher.discount_type == 'FIXED_AMOUNT':
        discount_amount = voucher.discount_value
    
    discount_amount = min(discount_amount, original_budget_pre_vat)
    
    new_budget_pre_vat = original_budget_pre_vat - discount_amount
    return round(new_budget_pre_vat, 2), round(discount_amount, 2)

def record_voucher_usage(voucher_code: str):
    try:
        voucher = get_voucher_by_code(voucher_code)
        if voucher:
            voucher.current_uses += 1
            voucher.updated_at = datetime.datetime.utcnow()
            db.session.commit()
            logger.info(f"Utilização do voucher '{voucher.code}' registada. Usos atuais: {voucher.current_uses}")
        else:
            logger.error(f"Tentativa de registar uso para voucher inexistente: {voucher_code}")
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao registar uso do voucher {voucher_code}: {e}", exc_info=True)
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao registar uso do voucher {voucher_code}: {e_unexp}", exc_info=True)


# --- Funções de Cálculo de Orçamento e API de Mapas ---
def _normalize_location_string(location_str: str) -> str:
    if not location_str: return ""
    s = location_str.lower()
    s = re.sub(r'[áàâãä]', 'a', s); s = re.sub(r'[éèêë]', 'e', s)
    s = re.sub(r'[íìîï]', 'i', s); s = re.sub(r'[óòôõö]', 'o', s)
    s = re.sub(r'[úùûü]', 'u', s); s = re.sub(r'[ç]', 'c', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def _geocode_location_ors(location_name: str) -> tuple | None:
    if not location_name: return None
    api_key = current_app.config.get('MAPS_API_KEY')
    if not api_key:
        logger.error("MAPS_API_KEY não configurada para OpenRouteService.")
        return None
    geocode_url = "https://api.openrouteservice.org/geocode/search"
    params = {"api_key": api_key, "text": location_name, "size": 1, "boundary.country": "PRT"}
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
        logger.error(f"Erro inesperado na Geocodificação ORS para '{location_name}': {e_unexp}", exc_info=True)
        return None


def _get_route_details_from_maps_api(pickup_location_name: str, dropoff_location_name: str) -> dict:
    if current_app.config.get("MAPS_API_PROVIDER") != "OPENROUTESERVICE":
        logger.warning("MAPS_API_PROVIDER não está configurado para OPENROUTESERVICE.")
        return {"distance_km": 20.0, "duration_minutes": 30.0, "error": "API de mapas não configurada corretamente para ORS."}

    pickup_coords = _geocode_location_ors(pickup_location_name)
    if not pickup_coords:
        return {"distance_km": 0, "duration_minutes": 0, "error": f"Não foi possível geocodificar o local de partida: '{pickup_location_name}'."}

    dropoff_coords = _geocode_location_ors(dropoff_location_name)
    if not dropoff_coords:
        return {"distance_km": 0, "duration_minutes": 0, "error": f"Não foi possível geocodificar o local de destino: '{dropoff_location_name}'."}

    api_key = current_app.config.get('MAPS_API_KEY')
    if not api_key:
        logger.error("MAPS_API_KEY não configurada para direções ORS.")
        return {"distance_km": 0, "duration_minutes": 0, "error": "Chave API de mapas não configurada."}

    directions_url = "https://api.openrouteservice.org/v2/directions/driving-car"
    headers = {'Authorization': api_key, 'Content-Type': 'application/json'}
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
                return {"distance_km": round(distance_km, 2), "duration_minutes": duration_minutes}
        
        api_error_msg = data.get("error", {}).get("message", "Nenhuma rota encontrada ou erro na API de direções.")
        logger.warning(f"Erro da API de Direções ORS: {api_error_msg} para rota {pickup_location_name} -> {dropoff_location_name}")
        return {"distance_km": 0, "duration_minutes": 0, "error": api_error_msg}

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro na API de Direções ORS: {e}")
        return {"distance_km": 0, "duration_minutes": 0, "error": f"Erro de comunicação com a API de direções: {e}"}
    except Exception as e_unexp:
        logger.error(f"Erro inesperado na API de Direções ORS: {e_unexp}", exc_info=True)
        return {"distance_km": 0, "duration_minutes": 0, "error": f"Erro inesperado ao obter direções: {e_unexp}"}


def calculate_estimated_budget(data: dict, request_time_obj: datetime.time = None) -> dict:
    try:
        tariff_settings = get_active_tariff_settings()
        if not tariff_settings:
            raise ValueError("Configurações de tarifa não disponíveis.")

        num_passengers = int(data.get('passengers', 1))
        num_bags = int(data.get('bags', 0))
        pickup_location_raw = str(data.get('pickupLocation', ''))
        dropoff_location_raw = str(data.get('dropoffLocation', ''))

        if num_passengers < 1: raise ValueError("Número de passageiros deve ser pelo menos 1.")
        if num_bags < 0: raise ValueError("Número de malas não pode ser negativo.")
        if not pickup_location_raw.strip(): raise ValueError("Local de partida é obrigatório.")
        if not dropoff_location_raw.strip(): raise ValueError("Local de destino é obrigatório.")

        norm_pickup = _normalize_location_string(pickup_location_raw)
        norm_dropoff = _normalize_location_string(dropoff_location_raw)
        route_key = f"{norm_pickup}#{norm_dropoff}"
        
        budget_pre_vat = 0.0
        duration_minutes = 0

        predefined_routes_config = current_app.config.get('PREDEFINED_ROUTES', {})
        if route_key in predefined_routes_config:
            budget_pre_vat = predefined_routes_config[route_key]
            route_details_for_duration = _get_route_details_from_maps_api(pickup_location_raw, dropoff_location_raw)
            duration_minutes = route_details_for_duration.get("duration_minutes", 60)
        else:
            route_details = _get_route_details_from_maps_api(pickup_location_raw, dropoff_location_raw)
            if route_details.get("error"):
                raise ValueError(f"Erro ao calcular orçamento: {route_details['error']}")
            
            distance_km = route_details["distance_km"]
            duration_minutes = route_details["duration_minutes"]

            if distance_km <= 0 and not (norm_pickup == norm_dropoff):
                raise ValueError("Distância inválida calculada pela API de mapas.")
            
            budget_pre_vat = tariff_settings.base_rate_eur + (distance_km * tariff_settings.rate_per_km_eur)

        if num_passengers > 1:
            budget_pre_vat += (num_passengers - 1) * tariff_settings.rate_per_passenger_eur
        if num_bags > 0:
            budget_pre_vat += num_bags * tariff_settings.rate_per_bag_eur

        if tariff_settings.night_surcharge_applies:
            current_time_for_fare = request_time_obj if request_time_obj else datetime.datetime.now().time()
            is_night_fare = False
            start_night = datetime.time(tariff_settings.night_surcharge_start_hour, 0)
            end_night = datetime.time(tariff_settings.night_surcharge_end_hour, 0)

            if start_night > end_night:
                if current_time_for_fare >= start_night or current_time_for_fare < end_night:
                    is_night_fare = True
            else:
                if start_night <= current_time_for_fare < end_night:
                    is_night_fare = True
            
            if is_night_fare:
                budget_pre_vat += (budget_pre_vat * tariff_settings.night_surcharge_percentage) / 100.0

        original_budget_pre_vat = round(budget_pre_vat, 2)

        vat_percentage = current_app.config.get('VAT_RATE', 23.0)
        vat_amount = round(original_budget_pre_vat * (vat_percentage / 100.0), 2)
        total_with_vat = round(original_budget_pre_vat + vat_amount, 2)

        logger.info(f"Orçamento Calculado: Base (s/IVA) {original_budget_pre_vat:.2f}, IVA ({vat_percentage}%) {vat_amount:.2f}, Total {total_with_vat:.2f}, Duração {duration_minutes} min")

        return {
            "original_budget_pre_vat": original_budget_pre_vat,
            "final_budget_pre_vat": original_budget_pre_vat,
            "vat_percentage": vat_percentage,
            "vat_amount": vat_amount,
            "total_with_vat": total_with_vat,
            "duration_minutes": duration_minutes,
            "discount_amount": 0.0,
            "applied_voucher_code": None
        }

    except ValueError as ve:
        logger.error(f"Erro de valor ao calcular orçamento: {ve}")
        raise
    except Exception as e_unexp:
        logger.error(f"Erro inesperado ao calcular orçamento: {e_unexp}", exc_info=True)
        raise ValueError("Erro interno inesperado ao calcular o orçamento.")


# --- Funções de Gestão de Reservas ---
def check_availability(booking_date_obj: datetime.date, booking_time_obj: datetime.time, booking_duration_minutes: int) -> bool:
    try:
        tariff_settings = get_active_tariff_settings()
        if not tariff_settings:
            raise ValueError("Configurações de tarifa indisponíveis para verificar disponibilidade.")

        active_drivers = get_all_drivers(only_active=True) 
        num_active_drivers = len(active_drivers)
        if num_active_drivers == 0:
            logger.info("Nenhum motorista ativo, disponibilidade é false.")
            return False

        new_booking_start_dt = datetime.datetime.combine(booking_date_obj, booking_time_obj)
        slot_overlap_delta = datetime.timedelta(minutes=tariff_settings.booking_slot_overlap_minutes)
        
        new_slot_start = new_booking_start_dt - slot_overlap_delta
        new_slot_end = new_booking_start_dt + datetime.timedelta(minutes=booking_duration_minutes) + slot_overlap_delta

        relevant_statuses = {'PENDING_CONFIRMATION', 'CONFIRMED', 'DRIVER_ASSIGNED', 'ON_ROUTE_PICKUP', 'PASSENGER_ON_BOARD'}
        existing_bookings_on_date = db.session.query(Booking)\
            .filter(Booking.date == booking_date_obj)\
            .filter(Booking.status.in_(relevant_statuses))\
            .all()

        conflicting_bookings_count = 0
        for existing_booking in existing_bookings_on_date:
            if existing_booking.duration_minutes is None:
                logger.warning(f"Reserva existente ID {existing_booking.id} sem duração, ignorando para disponibilidade.")
                continue

            existing_booking_start_dt = datetime.datetime.combine(existing_booking.date, existing_booking.time)
            actual_existing_end = existing_booking_start_dt + datetime.timedelta(minutes=existing_booking.duration_minutes)
            
            overlap = (new_slot_start < actual_existing_end) and \
                      (new_slot_end > existing_booking_start_dt)
            
            if overlap:
                conflicting_bookings_count += 1
        
        logger.info(f"Disponibilidade: {conflicting_bookings_count} conflitos vs {num_active_drivers} motoristas ativos.")
        return conflicting_bookings_count < num_active_drivers

    except SQLAlchemyError as e:
        logger.error(f"Erro de BD ao verificar disponibilidade: {e}", exc_info=True)
        raise ValueError("Erro de base de dados ao verificar disponibilidade.")
    except ValueError as ve:
        logger.error(f"Erro de valor ao verificar disponibilidade: {ve}")
        raise
    except Exception as e_unexp:
        logger.error(f"Erro inesperado ao verificar disponibilidade: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao verificar disponibilidade.")


def create_booking_record(booking_data: dict) -> Booking:
    try:
        passenger_name = booking_data['passengerName']
        passenger_phone = booking_data.get('passengerPhone')
        date_str = booking_data['date']
        time_str = booking_data['time']
        duration_minutes_str = booking_data.get('duration_minutes')
        pickup_location = booking_data['pickupLocation']
        dropoff_location = booking_data['dropoffLocation']
        passengers_str = booking_data['passengers']
        bags_str = booking_data['bags']
        instructions = booking_data.get('instructions')
        voucher_code_from_frontend = booking_data.get('voucher_code')

        if not passenger_name.strip(): raise ValueError("Nome do passageiro é obrigatório.")
        try:
            date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            time_obj = datetime.datetime.strptime(time_str, '%H:%M').time()
            passengers = int(passengers_str)
            bags = int(bags_str)
            duration_minutes = int(duration_minutes_str)
        except (TypeError, ValueError) as e_conv:
            raise ValueError(f"Dados de reserva inválidos (data, hora, passageiros, malas ou duração): {e_conv}")

        if duration_minutes <= 0: raise ValueError("Duração da reserva deve ser positiva.")
        if passengers < 1: raise ValueError("Número de passageiros deve ser pelo menos 1.")
        if bags < 0: raise ValueError("Número de malas não pode ser negativo.")

        budget_calc_data = {
            'passengers': passengers, 'bags': bags,
            'pickupLocation': pickup_location, 'dropoffLocation': dropoff_location,
        }
        base_budget_details = calculate_estimated_budget(budget_calc_data, request_time_obj=time_obj)
        original_budget_pre_vat_calc = base_budget_details['original_budget_pre_vat']

        final_budget_pre_vat_calc = original_budget_pre_vat_calc
        discount_amount_calc = 0.0
        applied_voucher_code_final = None
        validated_voucher_obj = None
        if voucher_code_from_frontend and voucher_code_from_frontend.strip():
            try:
                validated_voucher_obj = validate_voucher_for_use(voucher_code_from_frontend, original_budget_pre_vat_calc)
                final_budget_pre_vat_calc, discount_amount_calc = apply_voucher_to_budget(original_budget_pre_vat_calc, validated_voucher_obj)
                applied_voucher_code_final = validated_voucher_obj.code
                logger.info(f"Voucher '{applied_voucher_code_final}' validado e aplicado no backend para a reserva.")
            except ValueError as ve_voucher:
                logger.warning(f"Voucher '{voucher_code_from_frontend}' falhou validação no backend durante criação de reserva: {ve_voucher}. Ignorando voucher.")

        vat_percentage_calc = current_app.config.get('VAT_RATE', 23.0)
        vat_amount_calc = round(final_budget_pre_vat_calc * (vat_percentage_calc / 100.0), 2)
        total_with_vat_calc = round(final_budget_pre_vat_calc + vat_amount_calc, 2)

        new_booking = Booking(
            passenger_name=passenger_name,
            passenger_phone=passenger_phone,
            date=date_obj, time=time_obj,
            duration_minutes=duration_minutes,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            passengers=passengers,
            bags=bags,
            instructions=instructions,
            original_budget_pre_vat=original_budget_pre_vat_calc,
            discount_amount=discount_amount_calc if discount_amount_calc > 0 else None,
            final_budget_pre_vat=final_budget_pre_vat_calc,
            vat_percentage=vat_percentage_calc,
            vat_amount=vat_amount_calc,
            total_with_vat=total_with_vat_calc,
            applied_voucher_code=applied_voucher_code_final,
            status='PENDING_CONFIRMATION'
        )
        db.session.add(new_booking)
        db.session.commit()

        if new_booking.applied_voucher_code:
            record_voucher_usage(new_booking.applied_voucher_code)

        db.session.refresh(new_booking)
        logger.info(f"Reserva criada na BD com ID: {new_booking.id}, Total c/IVA: {new_booking.total_with_vat}, Voucher: {new_booking.applied_voucher_code}")
        return new_booking

    except ValueError as ve:
        db.session.rollback()
        logger.error(f"Erro de valor ao criar reserva: {ve}")
        raise
    except KeyError as ke:
        db.session.rollback()
        logger.error(f"Erro de dados em falta ao criar reserva: {ke}")
        raise ValueError(f"Dados de reserva incompletos: falta o campo {ke}.")
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao criar reserva: {e}", exc_info=True)
        raise ValueError("Erro de base de dados ao criar a reserva.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao criar reserva: {e_unexp}", exc_info=True)
        raise ValueError("Erro interno inesperado ao criar a reserva.")


def update_booking_status(booking_id: int, new_status: str) -> Booking | None:
    allowed_statuses = current_app.config.get('ALLOWED_BOOKING_STATUSES', [])
    if new_status not in allowed_statuses:
        raise ValueError(f"Status inválido: '{new_status}'. Status permitidos: {', '.join(allowed_statuses)}")
    try:
        booking_to_update = db.session.query(Booking).filter(Booking.id == booking_id).first()
        if booking_to_update:
            booking_to_update.status = new_status
            db.session.commit()
            db.session.refresh(booking_to_update)
            return booking_to_update
        return None
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao atualizar status da reserva {booking_id}: {e}", exc_info=True)
        raise ValueError("Erro de BD ao atualizar status da reserva.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao atualizar status da reserva {booking_id}: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao atualizar status da reserva.")

def assign_driver_to_booking(booking_id: int, driver_id: int | None) -> Booking | None:
    mail_instance = current_app.extensions.get('mail')
    if not mail_instance:
        logger.error("Instância Flask-Mail não encontrada em current_app.extensions. Emails não serão enviados.")

    try:
        booking_to_update = db.session.query(Booking).options(joinedload(Booking.assigned_driver)).filter(Booking.id == booking_id).first()
        if not booking_to_update:
            return None

        driver_to_assign = None
        if driver_id is not None:
            driver_to_assign = get_driver_by_id(driver_id)
            if not driver_to_assign:
                raise ValueError(f"Motorista com ID {driver_id} não encontrado.")
            if not driver_to_assign.is_active:
                raise ValueError(f"Motorista ID {driver_id} está inativo e não pode ser atribuído.")

        previous_driver_id = booking_to_update.assigned_driver_id
        booking_to_update.assigned_driver_id = driver_id

        if driver_id is not None and booking_to_update.status == 'CONFIRMED':
            booking_to_update.status = 'DRIVER_ASSIGNED'
        elif driver_id is None and booking_to_update.status == 'DRIVER_ASSIGNED':
            booking_to_update.status = 'CONFIRMED'
        
        db.session.commit()
        db.session.refresh(booking_to_update)

        if mail_instance and driver_id is not None and driver_id != previous_driver_id and driver_to_assign and driver_to_assign.email:
            try:
                send_driver_assignment_email(mail_instance, driver_to_assign, booking_to_update)
            except Exception as email_error:
                logger.error(f"Erro ao enviar email de atribuição para motorista ID {driver_id} (reserva {booking_id}): {email_error}", exc_info=True)
        
        return booking_to_update
    except ValueError as ve:
        raise ve
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao atribuir motorista à reserva {booking_id}: {e}", exc_info=True)
        raise ValueError("Erro de base de dados ao atribuir motorista.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao atribuir motorista à reserva {booking_id}: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao atribuir motorista.")

def get_all_bookings() -> list[Booking]:
    try:
        return db.session.query(Booking).options(joinedload(Booking.assigned_driver)).order_by(Booking.date.desc(), Booking.time.desc()).all()
    except SQLAlchemyError as e:
        logger.error(f"Erro de BD ao obter todas as reservas: {e}", exc_info=True)
        raise ValueError("Erro de BD ao obter todas as reservas.")
    except Exception as e_unexp:
        logger.error(f"Erro inesperado ao obter todas as reservas: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao obter todas as reservas.")

def delete_booking_by_id(booking_id: int) -> bool:
    try:
        booking_to_delete = db.session.query(Booking).filter(Booking.id == booking_id).first()
        if booking_to_delete:
            db.session.delete(booking_to_delete)
            db.session.commit()
            return True
        return False
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao excluir reserva {booking_id}: {e}", exc_info=True)
        raise ValueError("Erro de BD ao excluir reserva.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao excluir reserva {booking_id}: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao excluir reserva.")

# --- Secção CRUD para Motoristas ---
def create_driver(driver_data: dict) -> Driver:
    try:
        first_name = str(driver_data.get('first_name', '')).strip()
        last_name = str(driver_data.get('last_name', '')).strip()
        if not first_name: raise ValueError("Nome próprio do motorista é obrigatório.")
        if not last_name: raise ValueError("Apelido do motorista é obrigatório.")
        
        email = driver_data.get('email')
        email = str(email).strip().lower() if email and str(email).strip() else None
        
        phone_number = driver_data.get('phone_number')
        phone_number = str(phone_number).strip() if phone_number and str(phone_number).strip() else None

        new_driver = Driver(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            is_active=driver_data.get('is_active', True)
        )
        db.session.add(new_driver)
        db.session.commit()
        db.session.refresh(new_driver)
        return new_driver
    except IntegrityError:
        db.session.rollback()
        raise ValueError(f"Email '{email}' já está registado para outro motorista.")
    except ValueError as ve:
        db.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao criar motorista: {e}", exc_info=True)
        raise ValueError("Erro de base de dados ao criar motorista.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao criar motorista: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao criar motorista.")

def get_driver_by_id(driver_id: int) -> Driver | None:
    try:
        return db.session.query(Driver).filter(Driver.id == driver_id).first()
    except SQLAlchemyError as e:
        logger.error(f"Erro de BD ao obter motorista por ID {driver_id}: {e}", exc_info=True)
        raise ValueError(f"Erro de BD ao obter motorista ID {driver_id}.")

def get_all_drivers(only_active: bool = False) -> list[Driver]:
    try:
        query = db.session.query(Driver)
        if only_active:
            query = query.filter(Driver.is_active == True)
        return query.order_by(Driver.last_name, Driver.first_name).all()
    except SQLAlchemyError as e:
        logger.error(f"Erro de BD ao obter todos os motoristas: {e}", exc_info=True)
        raise ValueError("Erro de BD ao obter todos os motoristas.")

def update_driver(driver_id: int, driver_data: dict) -> Driver | None:
    try:
        driver_to_update = get_driver_by_id(driver_id)
        if not driver_to_update:
            return None

        updated = False
        if 'first_name' in driver_data and str(driver_data['first_name']).strip():
            driver_to_update.first_name = str(driver_data['first_name']).strip()
            updated = True
        if 'last_name' in driver_data and str(driver_data['last_name']).strip():
            driver_to_update.last_name = str(driver_data['last_name']).strip()
            updated = True
        if 'email' in driver_data: 
            email_val = driver_data['email']
            driver_to_update.email = str(email_val).strip().lower() if email_val and str(email_val).strip() else None
            updated = True
        if 'phone_number' in driver_data:
            phone_val = driver_data['phone_number']
            driver_to_update.phone_number = str(phone_val).strip() if phone_val and str(phone_val).strip() else None
            updated = True
        if 'is_active' in driver_data and isinstance(driver_data['is_active'], bool):
            driver_to_update.is_active = driver_data['is_active']
            updated = True
        
        if not updated:
            return driver_to_update 
            
        db.session.commit()
        db.session.refresh(driver_to_update)
        return driver_to_update
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Email fornecido já está registado para outro motorista.")
    except ValueError as ve:
        db.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao atualizar motorista {driver_id}: {e}", exc_info=True)
        raise ValueError("Erro de base de dados ao atualizar motorista.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao atualizar motorista {driver_id}: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao atualizar motorista.")

def delete_driver_by_id(driver_id: int) -> bool:
    try:
        driver_to_delete = get_driver_by_id(driver_id)
        if driver_to_delete:
            if driver_to_delete.bookings:
                 raise ValueError(f"Não é possível excluir o motorista ID {driver_id} pois está associado a reservas.")
            db.session.delete(driver_to_delete)
            db.session.commit()
            return True
        return False
    except ValueError as ve:
        db.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao excluir motorista {driver_id}: {e}", exc_info=True)
        if "FOREIGN KEY constraint failed" in str(e).lower(): 
             raise ValueError(f"Não é possível excluir o motorista ID {driver_id} pois está associado a reservas (FK).")
        raise ValueError("Erro de BD ao excluir motorista.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao excluir motorista {driver_id}: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao excluir motorista.")


# --- Funções CRUD para Veículos ---
def create_vehicle(vehicle_data: dict) -> Vehicle:
    try:
        license_plate = str(vehicle_data.get('license_plate', '')).strip().upper()
        if not license_plate:
            raise ValueError("Matrícula do veículo é obrigatória.")

        capacity_passengers_str = vehicle_data.get('capacity_passengers')
        capacity_passengers = int(capacity_passengers_str) if capacity_passengers_str is not None else 4
        if capacity_passengers < 1: raise ValueError("Capacidade de passageiros deve ser >= 1.")

        capacity_bags_str = vehicle_data.get('capacity_bags')
        capacity_bags = int(capacity_bags_str) if capacity_bags_str is not None else 3
        if capacity_bags < 0: raise ValueError("Capacidade de malas deve ser >= 0.")
        
        year_str = vehicle_data.get('year')
        year = int(year_str) if year_str and str(year_str).strip() else None
        if year is not None and not (1900 <= year <= datetime.date.today().year + 2) :
            raise ValueError(f"Ano do veículo inválido: {year}.")

        new_vehicle = Vehicle(
            license_plate=license_plate,
            make=vehicle_data.get('make'),
            model=vehicle_data.get('model'),
            year=year,
            capacity_passengers=capacity_passengers,
            capacity_bags=capacity_bags,
            status=str(vehicle_data.get('status', 'ACTIVE')).upper()
        )
        db.session.add(new_vehicle)
        db.session.commit()
        db.session.refresh(new_vehicle)
        return new_vehicle
    except IntegrityError:
        db.session.rollback()
        raise ValueError(f"Veículo com a matrícula '{license_plate}' já existe.")
    except ValueError as ve:
        db.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao criar veículo: {e}", exc_info=True)
        raise ValueError("Erro de base de dados ao criar veículo.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao criar veículo: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao criar veículo.")

def get_vehicle_by_id(vehicle_id: int) -> Vehicle | None:
    try:
        return db.session.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    except SQLAlchemyError as e:
        logger.error(f"Erro de BD ao obter veículo por ID {vehicle_id}: {e}", exc_info=True)
        raise ValueError(f"Erro de BD ao obter veículo ID {vehicle_id}.")

def get_all_vehicles(status_filter: str | None = None) -> list[Vehicle]:
    try:
        query = db.session.query(Vehicle)
        if status_filter and status_filter.strip():
            query = query.filter(Vehicle.status == status_filter.strip().upper())
        return query.order_by(Vehicle.make, Vehicle.model, Vehicle.license_plate).all()
    except SQLAlchemyError as e:
        logger.error(f"Erro de BD ao obter todos os veículos: {e}", exc_info=True)
        raise ValueError("Erro de BD ao obter todos os veículos.")

def update_vehicle(vehicle_id: int, vehicle_data: dict) -> Vehicle | None:
    try:
        vehicle_to_update = get_vehicle_by_id(vehicle_id)
        if not vehicle_to_update:
            return None

        updated = False
        if 'license_plate' in vehicle_data and str(vehicle_data['license_plate']).strip():
            lp = str(vehicle_data['license_plate']).strip().upper()
            if not lp: raise ValueError("Matrícula não pode ser vazia.")
            vehicle_to_update.license_plate = lp
            updated = True
        if 'make' in vehicle_data:
            vehicle_to_update.make = vehicle_data['make'] if vehicle_data['make'] and str(vehicle_data['make']).strip() else None
            updated = True
        if 'model' in vehicle_data:
            vehicle_to_update.model = vehicle_data['model'] if vehicle_data['model'] and str(vehicle_data['model']).strip() else None
            updated = True
        if 'year' in vehicle_data:
            year_str = vehicle_data['year']
            if year_str and str(year_str).strip():
                year_val = int(year_str)
                if not (1900 <= year_val <= datetime.date.today().year + 2): raise ValueError(f"Ano do veículo inválido: {year_val}.")
                vehicle_to_update.year = year_val
            else:
                vehicle_to_update.year = None
            updated = True
        if 'capacity_passengers' in vehicle_data and vehicle_data['capacity_passengers'] is not None:
            cap_pass = int(vehicle_data['capacity_passengers'])
            if cap_pass < 1: raise ValueError("Capacidade de passageiros deve ser >= 1.")
            vehicle_to_update.capacity_passengers = cap_pass
            updated = True
        if 'capacity_bags' in vehicle_data:
            cap_bags_str = vehicle_data['capacity_bags']
            if cap_bags_str is not None and str(cap_bags_str).strip() != "":
                cap_bags = int(cap_bags_str)
                if cap_bags < 0: raise ValueError("Capacidade de malas deve ser >= 0.")
                vehicle_to_update.capacity_bags = cap_bags
            else:
                vehicle_to_update.capacity_bags = None
            updated = True
        if 'status' in vehicle_data and str(vehicle_data['status']).strip():
            status_val = str(vehicle_data['status']).strip().upper()
            vehicle_to_update.status = status_val
            updated = True
        
        if not updated: return vehicle_to_update

        db.session.commit()
        db.session.refresh(vehicle_to_update)
        return vehicle_to_update
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Matrícula fornecida já está registada para outro veículo.")
    except ValueError as ve:
        db.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao atualizar veículo {vehicle_id}: {e}", exc_info=True)
        raise ValueError("Erro de base de dados ao atualizar veículo.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao atualizar veículo {vehicle_id}: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao atualizar veículo.")


def delete_vehicle_by_id(vehicle_id: int) -> bool:
    try:
        vehicle_to_delete = get_vehicle_by_id(vehicle_id)
        if vehicle_to_delete:
            db.session.delete(vehicle_to_delete)
            db.session.commit()
            return True
        return False
    except ValueError as ve:
        db.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Erro de BD ao excluir veículo {vehicle_id}: {e}", exc_info=True)
        if "FOREIGN KEY constraint failed" in str(e).lower():
            raise ValueError("Veículo não pode ser excluído pois está associado a outros registos (ex: reservas).")
        raise ValueError("Erro de BD ao excluir veículo.")
    except Exception as e_unexp:
        db.session.rollback()
        logger.error(f"Erro inesperado ao excluir veículo {vehicle_id}: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao excluir veículo.")


# --- Funções de Envio de Email ---
def send_new_booking_notification_email(mail_instance, booking: Booking):
    admin_recipients = current_app.config.get('ADMIN_EMAIL_RECIPIENTS')
    if not admin_recipients:
        logger.warning("ADMIN_EMAIL_RECIPIENTS não configurado. Email de notificação de nova reserva não enviado.")
        return
    try:
        subject = f"Nova Reserva TVDE Recebida - ID: {booking.id}"
        html_body = f"""
        <h1>Nova Reserva Recebida</h1>
        <p>Detalhes:</p>
        <ul>
            <li>ID da Reserva: {booking.id}</li>
            <li>Passageiro: {booking.passenger_name}</li>
            <li>Telefone: {booking.passenger_phone or 'N/A'}</li>
            <li>Data e Hora: {booking.date.strftime('%d/%m/%Y')} às {booking.time.strftime('%H:%M')}</li>
            <li>Duração Estimada: {booking.duration_minutes} minutos</li>
            <li>Local de Partida: {booking.pickup_location}</li>
            <li>Local de Destino: {booking.dropoff_location}</li>
            <li>Nº Passageiros: {booking.passengers}</li>
            <li>Nº Malas: {booking.bags}</li>
            {"<li>Orçamento Base (s/IVA): " + str(round(booking.original_budget_pre_vat, 2)) + " EUR</li>" if booking.original_budget_pre_vat is not None else ""}
            {"<li>Voucher Aplicado: " + booking.applied_voucher_code + "</li>" if booking.applied_voucher_code else ""}
            {"<li>Valor do Desconto: " + str(round(booking.discount_amount, 2)) + " EUR</li>" if booking.discount_amount is not None and booking.discount_amount > 0 else ""}
            {"<li>Subtotal (s/IVA, após desconto): " + str(round(booking.final_budget_pre_vat, 2)) + " EUR</li>" if booking.final_budget_pre_vat is not None else ""}
            {"<li>IVA ({:.1f}%): ".format(booking.vat_percentage if booking.vat_percentage is not None else 0) + str(round(booking.vat_amount, 2)) + " EUR</li>" if booking.vat_amount is not None else ""}
            <li><strong>Total a Pagar (c/IVA): {booking.total_with_vat:.2f} EUR</strong></li>
            <li>Instruções Especiais: {booking.instructions or 'Nenhuma'}</li>
            <li>Status Atual: {booking.status.replace('_', ' ').title()}</li>
        </ul>
        <p>Por favor, aceda ao painel de administração para gerir esta reserva.</p>
        """
        msg = Message(subject=subject, recipients=admin_recipients, html=html_body)
        mail_instance.send(msg)
        logger.info(f"Email de notificação para admin enviado para {', '.join(admin_recipients)} para a reserva ID {booking.id}")
    except Exception as e:
        logger.error(f"Falha ao enviar email de notificação para admin (reserva ID {booking.id}): {e}", exc_info=True)

def send_driver_assignment_email(mail_instance, driver: Driver, booking: Booking):
    if not driver or not driver.email:
        logger.warning(f"Motorista ID {driver.id if driver else 'N/A'} sem email. Email de atribuição para reserva {booking.id} não enviado.")
        return
    try:
        subject = f"Novo Serviço TVDE Atribuído - Reserva ID: {booking.id}"
        html_body = f"""
        <h1>Novo Serviço Atribuído</h1>
        <p>Olá {driver.first_name},</p>
        <p>Foi-lhe atribuído um novo serviço. Detalhes:</p>
        <ul>
            <li>ID da Reserva: {booking.id}</li>
            <li>Data e Hora: {booking.date.strftime('%d/%m/%Y')} às {booking.time.strftime('%H:%M')}</li>
            <li>Passageiro: {booking.passenger_name}</li>
            <li>Telefone do Passageiro: {booking.passenger_phone or 'N/A'}</li>
            <li>Local de Partida: {booking.pickup_location}</li>
            <li>Local de Destino: {booking.dropoff_location}</li>
            <li>Nº Passageiros / Malas: {booking.passengers} / {booking.bags}</li>
            <li>Duração Estimada: {booking.duration_minutes} minutos</li>
            <li><strong>Valor Total do Cliente (c/IVA): {booking.total_with_vat:.2f} EUR</strong></li>
            <li>Instruções Especiais: {booking.instructions or 'Nenhuma'}</li>
        </ul>
        <p>Obrigado,<br>A Gerência - Curvas Humildes</p>
        """
        msg = Message(subject=subject, recipients=[driver.email], html=html_body)
        mail_instance.send(msg)
        logger.info(f"Email de atribuição de serviço enviado para {driver.email} (Motorista ID {driver.id}) para a reserva ID {booking.id}")
    except Exception as e:
        logger.error(f"Falha ao enviar email de atribuição para motorista ID {driver.id} (reserva {booking.id}): {e}", exc_info=True)