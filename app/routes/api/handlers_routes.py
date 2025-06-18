import datetime
from logging import getLogger

from flask import Blueprint, current_app, jsonify, request

from app.routes.main_routes import logger
from ..authentication_routes import get_role
from flask_jwt_extended import jwt_required

from ...services import bookings_service, budget_service, vouchers_service

handlers_blueprint = Blueprint(
    name="handlers",
    import_name=__name__,
)

logger = getLogger(__name__)


from flask import Blueprint, request, jsonify
import datetime
import logging

handlers_blueprint = Blueprint("handlers", __name__)
logger = logging.getLogger(__name__)

@handlers_blueprint.route("/calculate-budget", methods=["POST"])
@jwt_required()
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
        budget_details = budget_service.calculate_estimated_budget(data, request_time_obj=current_server_time)
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


from flask import request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import datetime
import logging

# Já deve ter seu blueprint e logger definidos em outro lugar:
# handlers_blueprint = Blueprint(...)
logger = logging.getLogger(__name__)

@handlers_blueprint.route("/submit-booking", methods=["POST"])
@jwt_required()
def handle_submit_booking():
    if not request.is_json:
        return jsonify({"error": "O pedido deve ser em formato JSON"}), 400
    data = request.get_json()
    logger.info(f"Dados recebidos para /submit-booking: {data}")

    # Obter o user_id e role do JWT (conforme definição do teu /login)
    user_id = get_jwt_identity()   # <- o .identity no login é só o id
    claims = get_jwt()
    role = claims.get("role")

    if role not in ["user", "partner", "admin"]:
        return jsonify({"error": "Sem permissão para submeter reservas."}), 403

    required_fields = [
        "date",
        "time",
        "passengerName",
        "passengers",
        "bags",
        "pickupLocation",
        "dropoffLocation",
        "duration_minutes",
    ]
    missing_or_empty_fields = []
    for field in required_fields:
        value = data.get(field)
        if value is None or (
            isinstance(value, str)
            and not value.strip()
            and field not in ["instructions", "voucher_code", "passengerPhone"]
        ):
            missing_or_empty_fields.append(field)
        elif field == "passengers" and (not isinstance(value, int) or value < 1):
            missing_or_empty_fields.append(f"{field} (>= 1)")
        elif field == "bags" and (not isinstance(value, int) or value < 0):
            missing_or_empty_fields.append(f"{field} (>= 0)")
        elif field == "duration_minutes" and (not isinstance(value, int) or value <= 0):
            missing_or_empty_fields.append(f"{field} (> 0)")

    if missing_or_empty_fields:
        return (
            jsonify({
                "error": f"Campos obrigatórios em falta ou inválidos: {', '.join(missing_or_empty_fields)}"
            }), 400,
        )

    try:
        booking_date_obj = datetime.datetime.strptime(data["date"], "%Y-%m-%d").date()
        booking_time_obj = datetime.datetime.strptime(data["time"], "%H:%M").time()
        current_datetime = datetime.datetime.now()
        booking_datetime = datetime.datetime.combine(booking_date_obj, booking_time_obj)
        if booking_datetime < (current_datetime - datetime.timedelta(minutes=5)):
            raise ValueError("Data e hora da reserva não podem estar no passado.")

        is_available = bookings_service.check_availability(
            booking_date_obj, booking_time_obj, int(data["duration_minutes"])
        )
        if not is_available:
            return (
                jsonify({"error": "O horário solicitado já não está disponível."}),
                409,
            )

        # Insere o user_id do JWT no booking
        data["user_id"] = user_id

        new_booking = bookings_service.create_booking_record(data)

        mail_instance = current_app.extensions.get("mail")
        if mail_instance:
            try:
                bookings_service.send_new_booking_notification_email(
                    mail_instance, new_booking
                )
            except Exception as email_error:
                logger.error(
                    f"Erro ao enviar email (reserva ID {new_booking.id}): {email_error}",
                    exc_info=True,
                )

        return (
            jsonify(
                {
                    "message": "Pedido de reserva submetido com sucesso!",
                    "bookingId": new_booking.id,
                    "status": new_booking.status,
                    "total_with_vat": new_booking.total_with_vat,
                    "appliedVoucher": new_booking.applied_voucher_code,
                }
            ),
            201,
        )
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        logger.error(f"Erro inesperado em /submit-booking: {e}", exc_info=True)
        return jsonify({"error": "Erro interno inesperado."}), 500  


@handlers_blueprint.route('/validate-voucher', methods=['POST'])
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
        valid_voucher = vouchers_service.validate_voucher_for_use(voucher_code, original_budget_pre_vat)
        final_budget_pre_vat, discount_amount = vouchers_service.apply_voucher_to_budget(original_budget_pre_vat, valid_voucher)
        
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
