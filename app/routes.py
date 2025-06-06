# CurvasSistema/app/routes.py
from flask import Blueprint, request, jsonify, send_from_directory, current_app, render_template
import datetime
import logging
import os

from . import services
from .models import Booking, Driver, Vehicle, TariffSettings, Voucher

main_bp = Blueprint('main', __name__, template_folder='templates', static_folder='static')
logger = logging.getLogger(__name__)

# --- Rotas para servir as páginas HTML ---

@main_bp.route('/')
def pagina_de_reservas():
    """Serve a página do formulário de reservas como a página principal."""
    logger.info("A servir o formulário de reservas (reservas_form.html) como página principal.")
    return render_template('reservas_form.html')

@main_bp.route('/admin')
def painel_admin():
    """Serve a página de administração."""
    logger.info("A servir o painel de administração (admin.html).")
    return render_template('admin.html')

# --- Rota para servir ficheiros da App do Motorista (Capacitor www) ---
@main_bp.route('/driver-app/')
@main_bp.route('/driver-app/<path:filename>')
def motorista_app_files(filename='index.html'):
    """Serve os ficheiros estáticos da aplicação do motorista (Capacitor www)."""
    driver_app_folder = os.path.join(current_app.root_path, 'app', 'driver_frontend', 'www')
    logger.info(f"Tentando servir '{filename}' da app do motorista a partir de {driver_app_folder}")
    if not os.path.exists(os.path.join(driver_app_folder, filename)):
        if os.path.exists(os.path.join(driver_app_folder, 'index.html')):
            logger.info(f"Ficheiro '{filename}' não encontrado, servindo 'index.html' da app do motorista.")
            return send_from_directory(driver_app_folder, 'index.html')
        else:
            logger.error(f"Nem '{filename}' nem 'index.html' encontrados em {driver_app_folder}")
            return jsonify({"error": "Ficheiro da aplicação do motorista não encontrado."}), 404
    return send_from_directory(driver_app_folder, filename)

# --- Endpoints da API Pública (Sistema de Reservas Principal) ---
@main_bp.route('/calculate-budget', methods=['POST'])
def handle_calculate_budget():
    if not request.is_json:
        return jsonify({"error": "O pedido deve ser em formato JSON"}), 400
    data = request.get_json()
    logger.info(f"Dados recebidos para /calculate-budget: {data}")

    required_fields = ['passengers', 'pickupLocation', 'dropoffLocation']
    missing_fields = [f for f in required_fields if data.get(f) is None or (isinstance(data.get(f), str) and not str(data.get(f)).strip())]
    
    if data.get('bags') is None: data['bags'] = 0
    elif not isinstance(data.get('bags'), int) or data.get('bags') < 0 :
         missing_fields.append('bags (deve ser um número >= 0)')

    if missing_fields:
        return jsonify({"error": f"Campos em falta ou inválidos: {', '.join(missing_fields)}"}), 400
    
    try:
        current_server_time = datetime.datetime.now().time()
        budget_details = services.calculate_estimated_budget(data, request_time_obj=current_server_time)
        return jsonify({
            "message": "Orçamento calculado com sucesso.",
            "original_budget_pre_vat": budget_details['original_budget_pre_vat'],
            "vat_percentage": budget_details['vat_percentage'],
            "vat_amount": budget_details['vat_amount'],
            "total_with_vat": budget_details['total_with_vat'],
            "duration_minutes": budget_details['duration_minutes'],
            "currency": "EUR"
        }), 200
    except ValueError as ve:
        logger.error(f"Erro de valor em /calculate-budget: {ve}")
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Erro inesperado em /calculate-budget: {e}", exc_info=True)
        return jsonify({"error": "Erro interno ao calcular o orçamento."}), 500

@main_bp.route('/validate-voucher', methods=['POST'])
def handle_validate_voucher():
    if not request.is_json:
        return jsonify({"error": "O pedido deve ser em formato JSON"}), 400
    data = request.get_json()
    voucher_code = data.get('voucher_code')
    original_budget_pre_vat_str = data.get('original_budget_pre_vat')

    if not voucher_code or original_budget_pre_vat_str is None:
        return jsonify({"error": "Campos 'voucher_code' e 'original_budget_pre_vat' são obrigatórios."}), 400
    
    try:
        original_budget_pre_vat = float(original_budget_pre_vat_str)
        if original_budget_pre_vat < 0:
             raise ValueError("Orçamento original (s/IVA) não pode ser negativo.")
    except ValueError:
        return jsonify({"error": "Valor de 'original_budget_pre_vat' inválido."}), 400

    try:
        valid_voucher = services.validate_voucher_for_use(voucher_code, original_budget_pre_vat)
        final_budget_pre_vat, discount_amount = services.apply_voucher_to_budget(original_budget_pre_vat, valid_voucher)
        
        vat_percentage = current_app.config.get('VAT_RATE', 23.0)
        vat_amount_final = round(final_budget_pre_vat * (vat_percentage / 100.0), 2)
        total_with_vat_final = round(final_budget_pre_vat + vat_amount_final, 2)

        return jsonify({
            "message": f"Voucher '{valid_voucher.code}' válido e aplicado!", "valid": True,
            "voucher_code": valid_voucher.code,
            "original_budget_pre_vat": original_budget_pre_vat, "discount_amount": discount_amount,
            "final_budget_pre_vat": final_budget_pre_vat, "vat_percentage": vat_percentage,
            "vat_amount": vat_amount_final, "total_with_vat": total_with_vat_final,
            "description": f"Desconto de {valid_voucher.discount_value}{'%' if valid_voucher.discount_type == 'PERCENTAGE' else ' EUR'} aplicado."
        }), 200
    except ValueError as ve:
        logger.warning(f"Falha na validação do voucher '{voucher_code}': {ve}")
        return jsonify({"error": str(ve), "valid": False}), 400
    except Exception as e:
        logger.error(f"Erro inesperado ao validar voucher '{voucher_code}': {e}", exc_info=True)
        return jsonify({"error": "Erro interno ao validar o voucher."}), 500

@main_bp.route('/submit-booking', methods=['POST'])
def handle_submit_booking():
    if not request.is_json:
        return jsonify({"error": "O pedido deve ser em formato JSON"}), 400
    data = request.get_json()
    logger.info(f"Dados recebidos para /submit-booking: {data}")

    required_fields = ['date', 'time', 'passengerName', 'passengers', 'bags', 
                       'pickupLocation', 'dropoffLocation', 'duration_minutes']
    missing_or_empty_fields = []
    for field in required_fields:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip() and field not in ['instructions', 'voucher_code', 'passengerPhone']):
            missing_or_empty_fields.append(field)
        elif field == 'passengers' and (not isinstance(value, int) or value < 1): missing_or_empty_fields.append(f"{field} (>= 1)")
        elif field == 'bags' and (not isinstance(value, int) or value < 0): missing_or_empty_fields.append(f"{field} (>= 0)")
        elif field == 'duration_minutes' and (not isinstance(value, int) or value <= 0): missing_or_empty_fields.append(f"{field} (> 0)")
    
    if missing_or_empty_fields:
        return jsonify({"error": f"Campos obrigatórios em falta ou inválidos: {', '.join(missing_or_empty_fields)}"}), 400

    try:
        booking_date_obj = datetime.datetime.strptime(data['date'], '%Y-%m-%d').date()
        booking_time_obj = datetime.datetime.strptime(data['time'], '%H:%M').time()
        current_datetime = datetime.datetime.now()
        booking_datetime = datetime.datetime.combine(booking_date_obj, booking_time_obj)
        if booking_datetime < (current_datetime - datetime.timedelta(minutes=5)):
            raise ValueError("Data e hora da reserva não podem estar no passado.")

        is_available = services.check_availability(booking_date_obj, booking_time_obj, int(data['duration_minutes']))
        if not is_available:
            return jsonify({"error": "O horário solicitado já não está disponível."}), 409

        new_booking = services.create_booking_record(data)
        mail_instance = current_app.extensions.get('mail')
        if mail_instance:
            try:
                services.send_new_booking_notification_email(mail_instance, new_booking)
            except Exception as email_error:
                logger.error(f"Erro ao enviar email (reserva ID {new_booking.id}): {email_error}", exc_info=True)
        
        return jsonify({
            "message": "Pedido de reserva submetido com sucesso!", "bookingId": new_booking.id,
            "status": new_booking.status, "total_with_vat": new_booking.total_with_vat,
            "appliedVoucher": new_booking.applied_voucher_code,
        }), 201
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Erro inesperado em /submit-booking: {e}", exc_info=True)
        return jsonify({"error": "Erro interno inesperado."}), 500

# --- Funções de Serialização ---
def _serialize_booking_details(booking: Booking):
    driver_info = None
    if booking.assigned_driver:
        driver_info = { "id": booking.assigned_driver.id, "name": f"{booking.assigned_driver.first_name} {booking.assigned_driver.last_name}" }
    return {
        "id": booking.id, "passenger_name": booking.passenger_name, "passenger_phone": booking.passenger_phone,
        "date": booking.date.isoformat() if booking.date else None,
        "time": booking.time.isoformat() if booking.time else None,
        "duration_minutes": booking.duration_minutes, "pickup_location": booking.pickup_location,
        "dropoff_location": booking.dropoff_location, "passengers": booking.passengers, "bags": booking.bags,
        "instructions": booking.instructions, "original_budget_pre_vat": booking.original_budget_pre_vat,
        "discount_amount": booking.discount_amount, "final_budget_pre_vat": booking.final_budget_pre_vat,
        "vat_percentage": booking.vat_percentage, "vat_amount": booking.vat_amount,
        "total_with_vat": booking.total_with_vat, "applied_voucher_code": booking.applied_voucher_code,
        "status": booking.status, "assigned_driver_id": booking.assigned_driver_id,
        "assigned_driver": driver_info, "created_at": booking.created_at.isoformat() if booking.created_at else None,
    }

def _serialize_driver_details(driver: Driver):
    return { "id": driver.id, "first_name": driver.first_name, "last_name": driver.last_name, "email": driver.email, "phone_number": driver.phone_number, "is_active": driver.is_active, "created_at": driver.created_at.isoformat() if driver.created_at else None }

def _serialize_vehicle_details(vehicle: Vehicle):
    return { "id": vehicle.id, "license_plate": vehicle.license_plate, "make": vehicle.make, "model": vehicle.model, "year": vehicle.year, "capacity_passengers": vehicle.capacity_passengers, "capacity_bags": vehicle.capacity_bags, "status": vehicle.status, "created_at": vehicle.created_at.isoformat() if vehicle.created_at else None }

def _serialize_tariff_settings_details(settings: TariffSettings):
    if not settings: return {}
    return { "id": settings.id, "base_rate_eur": settings.base_rate_eur, "rate_per_km_eur": settings.rate_per_km_eur, "rate_per_passenger_eur": settings.rate_per_passenger_eur, "rate_per_bag_eur": settings.rate_per_bag_eur, "night_surcharge_applies": settings.night_surcharge_applies, "night_surcharge_percentage": settings.night_surcharge_percentage, "night_surcharge_start_hour": settings.night_surcharge_start_hour, "night_surcharge_end_hour": settings.night_surcharge_end_hour, "booking_slot_overlap_minutes": settings.booking_slot_overlap_minutes, "updated_at": settings.updated_at.isoformat() if settings.updated_at else None }

def _serialize_voucher_details(voucher: Voucher):
    if not voucher: return None
    return { "id": voucher.id, "code": voucher.code, "description": voucher.description, "discount_type": voucher.discount_type, "discount_value": voucher.discount_value, "expiration_date": voucher.expiration_date.isoformat() if voucher.expiration_date else None, "max_uses": voucher.max_uses, "current_uses": voucher.current_uses, "min_booking_value": voucher.min_booking_value, "is_active": voucher.is_active, "created_at": voucher.created_at.isoformat() if voucher.created_at else None, "updated_at": voucher.updated_at.isoformat() if voucher.updated_at else None }

# --- Endpoints da API de Administração ---

@main_bp.route('/admin/bookings', methods=['GET'])
def admin_get_all_bookings_ep():
    try:
        all_bookings_orm = services.get_all_bookings()
        return jsonify([_serialize_booking_details(b) for b in all_bookings_orm]), 200
    except Exception as e:
        logger.error(f"Admin: Erro ao obter todas as reservas: {e}", exc_info=True)
        return jsonify({"error": "Erro interno ao obter as reservas."}), 500

@main_bp.route('/admin/bookings/<int:booking_id>', methods=['DELETE'])
def admin_delete_booking_ep(booking_id):
    try:
        success = services.delete_booking_by_id(booking_id)
        if success: return jsonify({"message": f"Reserva ID {booking_id} excluída."}), 200
        else: return jsonify({"error": f"Reserva ID {booking_id} não encontrada."}), 404
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro excluir reserva {booking_id}: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/bookings/<int:booking_id>/status', methods=['PATCH'])
def admin_update_booking_status_ep(booking_id):
    if not request.is_json: return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json(); new_status = data.get('status')
    if not new_status: return jsonify({"error": "Campo 'status' obrigatório."}), 400
    try:
        updated_booking = services.update_booking_status(booking_id, new_status)
        if updated_booking: return jsonify(_serialize_booking_details(updated_booking)), 200
        else: return jsonify({"error": f"Reserva ID {booking_id} não encontrada."}), 404
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro update status {booking_id}: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/bookings/<int:booking_id>/assign', methods=['PATCH'])
def admin_assign_driver_ep(booking_id):
    if not request.is_json: return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json(); driver_id_str = data.get('driver_id')
    driver_id = None
    if driver_id_str is not None and str(driver_id_str).lower() != 'null' and str(driver_id_str).strip() != '':
        try: driver_id = int(driver_id_str)
        except (ValueError, TypeError): return jsonify({"error": "driver_id inválido."}), 400
    try:
        updated_booking = services.assign_driver_to_booking(booking_id, driver_id)
        if updated_booking: return jsonify(_serialize_booking_details(updated_booking)), 200
        else: return jsonify({"error": f"Reserva ID {booking_id} não encontrada."}), 404
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro assign driver {booking_id}: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/drivers', methods=['POST'])
def admin_create_driver_ep():
    if not request.is_json: return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json(); required = ['first_name', 'last_name']
    if any(f not in data or not str(data[f]).strip() for f in required): return jsonify({"error": "Nome/Apelido obrigatórios."}), 400
    try:
        new_driver = services.create_driver(data)
        return jsonify(_serialize_driver_details(new_driver)), 201
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro criar motorista: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/drivers', methods=['GET'])
def admin_get_all_drivers_ep():
    only_active_param = request.args.get('active', default=None, type=str)
    only_active = only_active_param.lower() == 'true' if only_active_param is not None else None
    try:
        all_drivers_orm = services.get_all_drivers(only_active=only_active)
        return jsonify([_serialize_driver_details(d) for d in all_drivers_orm]), 200
    except Exception as e: logger.error(f"Admin: Erro obter motoristas: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/drivers/<int:driver_id>', methods=['GET'])
def admin_get_driver_ep(driver_id):
     try:
         driver = services.get_driver_by_id(driver_id)
         if driver: return jsonify(_serialize_driver_details(driver)), 200
         else: return jsonify({"error": f"Motorista ID {driver_id} não encontrado."}), 404
     except Exception as e: logger.error(f"Admin: Erro obter motorista {driver_id}: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/drivers/<int:driver_id>', methods=['PATCH'])
def admin_update_driver_ep(driver_id):
    if not request.is_json: return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json(); valid_fields = ['first_name', 'last_name', 'email', 'phone_number', 'is_active']
    if not any(f in data for f in valid_fields): return jsonify({"error": "Nenhum campo válido."}), 400
    try:
        updated_driver = services.update_driver(driver_id, data)
        if updated_driver: return jsonify(_serialize_driver_details(updated_driver)), 200
        else: return jsonify({"error": f"Motorista ID {driver_id} não encontrado."}), 404
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro update motorista {driver_id}: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/drivers/<int:driver_id>', methods=['DELETE'])
def admin_delete_driver_ep(driver_id):
    try:
        success = services.delete_driver_by_id(driver_id)
        if success: return '', 204
        else: return jsonify({"error": f"Motorista ID {driver_id} não encontrado."}), 404
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro excluir motorista {driver_id}: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/vehicles', methods=['POST'])
def admin_create_vehicle_ep():
    if not request.is_json: return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json()
    if not data.get('license_plate') or not str(data['license_plate']).strip(): return jsonify({"error": "Matrícula obrigatória."}), 400
    try:
        new_vehicle = services.create_vehicle(data)
        return jsonify(_serialize_vehicle_details(new_vehicle)), 201
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro criar veículo: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/vehicles', methods=['GET'])
def admin_get_all_vehicles_ep():
    status_filter = request.args.get('status', default=None, type=str)
    try:
        all_vehicles_orm = services.get_all_vehicles(status_filter=status_filter)
        return jsonify([_serialize_vehicle_details(v) for v in all_vehicles_orm]), 200
    except Exception as e: logger.error(f"Admin: Erro obter veículos: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/vehicles/<int:vehicle_id>', methods=['GET'])
def admin_get_vehicle_ep(vehicle_id):
    try:
        vehicle = services.get_vehicle_by_id(vehicle_id)
        if vehicle: return jsonify(_serialize_vehicle_details(vehicle)), 200
        else: return jsonify({"error": f"Veículo ID {vehicle_id} não encontrado."}), 404
    except Exception as e: logger.error(f"Admin: Erro obter veículo {vehicle_id}: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/vehicles/<int:vehicle_id>', methods=['PATCH'])
def admin_update_vehicle_ep(vehicle_id):
    if not request.is_json: return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json(); valid_fields = ['license_plate', 'make', 'model', 'year', 'capacity_passengers', 'capacity_bags', 'status']
    if not any(f in data for f in valid_fields): return jsonify({"error": "Nenhum campo válido."}), 400
    try:
        updated_vehicle = services.update_vehicle(vehicle_id, data)
        if updated_vehicle: return jsonify(_serialize_vehicle_details(updated_vehicle)), 200
        else: return jsonify({"error": f"Veículo ID {vehicle_id} não encontrado."}), 404
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro update veículo {vehicle_id}: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/vehicles/<int:vehicle_id>', methods=['DELETE'])
def admin_delete_vehicle_ep(vehicle_id):
    try:
        success = services.delete_vehicle_by_id(vehicle_id)
        if success: return '', 204
        else: return jsonify({"error": f"Veículo ID {vehicle_id} não encontrado."}), 404
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro excluir veículo {vehicle_id}: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/settings/tariffs', methods=['GET'])
def admin_get_tariff_settings_ep():
    try:
        current_settings = services.get_active_tariff_settings()
        return jsonify(_serialize_tariff_settings_details(current_settings)), 200
    except ValueError as ve: logger.error(f"Admin: Erro obter tarifas: {ve}", exc_info=True); return jsonify({"error": str(ve)}), 500
    except Exception as e: logger.error(f"Admin: Erro inesperado obter tarifas: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/settings/tariffs', methods=['PUT'])
def admin_update_tariff_settings_ep():
    if not request.is_json: return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json()
    try:
        updated_settings = services.update_tariff_settings(data)
        return jsonify(_serialize_tariff_settings_details(updated_settings)), 200
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro update tarifas: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/vouchers', methods=['POST'])
def admin_create_voucher_ep():
    if not request.is_json: return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json()
    if not data.get('code') or not str(data['code']).strip(): return jsonify({"error": "Código obrigatório."}), 400
    if data.get('discount_value') is None : return jsonify({"error": "Valor desconto obrigatório."}), 400
    if not data.get('discount_type'): return jsonify({"error": "Tipo desconto obrigatório."}), 400
    try:
        new_voucher = services.create_voucher(data)
        return jsonify(_serialize_voucher_details(new_voucher)), 201
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro criar voucher: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/vouchers', methods=['GET'])
def admin_get_all_vouchers_ep():
    try:
        all_vouchers_orm = services.get_all_vouchers()
        return jsonify([_serialize_voucher_details(v) for v in all_vouchers_orm]), 200
    except Exception as e: logger.error(f"Admin: Erro obter vouchers: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/vouchers/<int:voucher_id>', methods=['GET'])
def admin_get_voucher_ep(voucher_id):
    try:
        voucher = services.get_voucher_by_id(voucher_id)
        if voucher: return jsonify(_serialize_voucher_details(voucher)), 200
        else: return jsonify({"error": f"Voucher ID {voucher_id} não encontrado."}), 404
    except Exception as e: logger.error(f"Admin: Erro obter voucher {voucher_id}: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/vouchers/<int:voucher_id>', methods=['PATCH'])
def admin_update_voucher_ep(voucher_id):
    if not request.is_json: return jsonify({"error": "Pedido deve ser JSON"}), 400
    data = request.get_json(); valid_fields = ['description', 'discount_type', 'discount_value', 'expiration_date', 'max_uses', 'min_booking_value', 'is_active']
    if not any(f in data for f in valid_fields): return jsonify({"error": "Nenhum campo válido."}), 400
    try:
        updated_voucher = services.update_voucher(voucher_id, data)
        if updated_voucher: return jsonify(_serialize_voucher_details(updated_voucher)), 200
        else: return jsonify({"error": f"Voucher ID {voucher_id} não encontrado."}), 404
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro update voucher {voucher_id}: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

@main_bp.route('/admin/vouchers/<int:voucher_id>', methods=['DELETE'])
def admin_delete_voucher_ep(voucher_id):
    try:
        success = services.delete_voucher(voucher_id)
        if success: return '', 204
        else: return jsonify({"error": f"Voucher ID {voucher_id} não encontrado."}), 404
    except ValueError as ve: return jsonify({"error": str(ve)}), 400
    except Exception as e: logger.error(f"Admin: Erro excluir voucher {voucher_id}: {e}", exc_info=True); return jsonify({"error": "Erro interno."}), 500

