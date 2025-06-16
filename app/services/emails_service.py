import logging
from flask import current_app
from flask_mail import Message
from ..models.booking import Booking
from ..models.driver import Driver
from ..cache import flaskCaching

logger = logging.getLogger(__name__)

_BOOKING_NOTIFY_CACHE_TIMEOUT = 300
_BOOKING_ASSIGNMENT_CACHE_TIMEOUT = 300


def send_new_booking_notification_email(mail_instance, booking: Booking):
    cache_key = f"booking_notify_sent:{booking.id}"
    if flaskCaching.get(cache_key):
        logger.info(
            f"Email de notificação admin para reserva {booking.id} já enviado recentemente, ignorando."
        )
        return

    admin_recipients = current_app.config.get("ADMIN_EMAIL_RECIPIENTS")
    if not admin_recipients:
        logger.warning(
            "ADMIN_EMAIL_RECIPIENTS não configurado. Email de notificação de nova reserva não enviado."
        )
        return
    try:
        subject = f"Nova Reserva TVDE Recebida - ID: {booking.id}"
        html_body = f"""
        <h1>Nova Reserva Recebida</h1>
        <p>Detalhes:</p>
        <ul>
            <li>ID da Reserva: {booking.id}</li>
            <li>Passageiro: {booking.passenger_name}</li>
            <li>Telefone: {booking.passenger_phone or "N/A"}</li>
            <li>Data e Hora: {booking.date.strftime("%d/%m/%Y")} às {booking.time.strftime("%H:%M")}</li>
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
            <li>Instruções Especiais: {booking.instructions or "Nenhuma"}</li>
            <li>Status Atual: {booking.status.replace("_", " ").title()}</li>
        </ul>
        <p>Por favor, aceda ao painel de administração para gerir esta reserva.</p>
        """
        msg = Message(subject=subject, recipients=admin_recipients, html=html_body)
        mail_instance.send(msg)
        logger.info(
            f"Email de notificação para admin enviado para {', '.join(admin_recipients)} para a reserva ID {booking.id}"
        )
        flaskCaching.set(cache_key, True, timeout=_BOOKING_NOTIFY_CACHE_TIMEOUT)
    except Exception as e:
        logger.error(
            f"Falha ao enviar email de notificação para admin (reserva ID {booking.id}): {e}",
            exc_info=True,
        )


def send_driver_assignment_email(mail_instance, driver: Driver, booking: Booking):
    cache_key = f"booking_driver_assignment_sent:{booking.id}:{driver.id}"
    if flaskCaching.get(cache_key):
        logger.info(
            f"Email de atribuição para motorista {driver.id} (reserva {booking.id}) já enviado recentemente, ignorando."
        )
        return

    if not driver or not driver.email:
        logger.warning(
            f"Motorista ID {driver.id if driver else 'N/A'} sem email. Email de atribuição para reserva {booking.id} não enviado."
        )
        return
    try:
        subject = f"Novo Serviço TVDE Atribuído - Reserva ID: {booking.id}"
        html_body = f"""
        <h1>Novo Serviço Atribuído</h1>
        <p>Olá {driver.first_name},</p>
        <p>Foi-lhe atribuído um novo serviço. Detalhes:</p>
        <ul>
            <li>ID da Reserva: {booking.id}</li>
            <li>Data e Hora: {booking.date.strftime("%d/%m/%Y")} às {booking.time.strftime("%H:%M")}</li>
            <li>Passageiro: {booking.passenger_name}</li>
            <li>Telefone do Passageiro: {booking.passenger_phone or "N/A"}</li>
            <li>Local de Partida: {booking.pickup_location}</li>
            <li>Local de Destino: {booking.dropoff_location}</li>
            <li>Nº Passageiros / Malas: {booking.passengers} / {booking.bags}</li>
            <li>Duração Estimada: {booking.duration_minutes} minutos</li>
            <li><strong>Valor Total do Cliente (c/IVA): {booking.total_with_vat:.2f} EUR</strong></li>
            <li>Instruções Especiais: {booking.instructions or "Nenhuma"}</li>
        </ul>
        <p>Obrigado,<br>A Gerência - Curvas Humildes</p>
        """
        msg = Message(subject=subject, recipients=[driver.email], html=html_body)
        mail_instance.send(msg)
        logger.info(
            f"Email de atribuição de serviço enviado para {driver.email} (Motorista ID {driver.id}) para a reserva ID {booking.id}"
        )
        flaskCaching.set(cache_key, True, timeout=_BOOKING_ASSIGNMENT_CACHE_TIMEOUT)
    except Exception as e:
        logger.error(
            f"Falha ao enviar email de atribuição para motorista ID {driver.id} (reserva {booking.id}): {e}",
            exc_info=True,
        )
