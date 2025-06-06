import datetime

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from ..db import sqlAlchemy
from ..models.booking import Booking
from ..models.driver import Driver
from ..models.tariff_settings import TariffSettings

from .tariff_settings_service import get_active_tariff_settings
from .drivers_service import get_all_drivers, get_driver_by_id
from .budget_service import calculate_estimated_budget
from .vouchers_service import (
    validate_voucher_for_use,
    apply_voucher_to_budget,
    record_voucher_usage,
)
from .emails_service import send_driver_assignment_email

from logging import getLogger
from sqlalchemy.orm import joinedload

logger = getLogger(__name__)


def check_availability(
    booking_date_obj: datetime.date,
    booking_time_obj: datetime.time,
    booking_duration_minutes: int,
) -> bool:
    try:
        tariff_settings = get_active_tariff_settings()
        if not tariff_settings:
            raise ValueError(
                "Configurações de tarifa indisponíveis para verificar disponibilidade."
            )

        active_drivers = get_all_drivers(only_active=True)
        num_active_drivers = len(active_drivers)
        if num_active_drivers == 0:
            logger.info("Nenhum motorista ativo, disponibilidade é false.")
            return False

        new_booking_start_dt = datetime.datetime.combine(
            booking_date_obj, booking_time_obj
        )
        slot_overlap_delta = datetime.timedelta(
            minutes=tariff_settings.booking_slot_overlap_minutes
        )

        new_slot_start = new_booking_start_dt - slot_overlap_delta
        new_slot_end = (
            new_booking_start_dt
            + datetime.timedelta(minutes=booking_duration_minutes)
            + slot_overlap_delta
        )

        relevant_statuses = {
            "PENDING_CONFIRMATION",
            "CONFIRMED",
            "DRIVER_ASSIGNED",
            "ON_ROUTE_PICKUP",
            "PASSENGER_ON_BOARD",
        }
        existing_bookings_on_date = (
            sqlAlchemy.session.query(Booking)
            .filter(Booking.date == booking_date_obj)
            .filter(Booking.status.in_(relevant_statuses))
            .all()
        )

        conflicting_bookings_count = 0
        for existing_booking in existing_bookings_on_date:
            if existing_booking.duration_minutes is None:
                logger.warning(
                    f"Reserva existente ID {existing_booking.id} sem duração, ignorando para disponibilidade."
                )
                continue

            existing_booking_start_dt = datetime.datetime.combine(
                existing_booking.date, existing_booking.time
            )
            actual_existing_end = existing_booking_start_dt + datetime.timedelta(
                minutes=existing_booking.duration_minutes
            )

            overlap = (new_slot_start < actual_existing_end) and (
                new_slot_end > existing_booking_start_dt
            )

            if overlap:
                conflicting_bookings_count += 1

        logger.info(
            f"Disponibilidade: {conflicting_bookings_count} conflitos vs {num_active_drivers} motoristas ativos."
        )
        return conflicting_bookings_count < num_active_drivers

    except SQLAlchemyError as e:
        logger.error(f"Erro de BD ao verificar disponibilidade: {e}", exc_info=True)
        raise ValueError("Erro de base de dados ao verificar disponibilidade.")
    except ValueError as ve:
        logger.error(f"Erro de valor ao verificar disponibilidade: {ve}")
        raise
    except Exception as e_unexp:
        logger.error(
            f"Erro inesperado ao verificar disponibilidade: {e_unexp}", exc_info=True
        )
        raise ValueError("Erro inesperado ao verificar disponibilidade.")


def create_booking_record(booking_data: dict) -> Booking:
    try:
        passenger_name = booking_data["passengerName"]
        passenger_phone = booking_data.get("passengerPhone")
        date_str = booking_data["date"]
        time_str = booking_data["time"]
        duration_minutes_str = booking_data.get("duration_minutes")
        pickup_location = booking_data["pickupLocation"]
        dropoff_location = booking_data["dropoffLocation"]
        passengers_str = booking_data["passengers"]
        bags_str = booking_data["bags"]
        instructions = booking_data.get("instructions")
        voucher_code_from_frontend = booking_data.get("voucher_code")

        if not passenger_name.strip():
            raise ValueError("Nome do passageiro é obrigatório.")
        try:
            date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            time_obj = datetime.datetime.strptime(time_str, "%H:%M").time()
            passengers = int(passengers_str)
            bags = int(bags_str)
            duration_minutes = int(duration_minutes_str)
        except (TypeError, ValueError) as e_conv:
            raise ValueError(
                f"Dados de reserva inválidos (data, hora, passageiros, malas ou duração): {e_conv}"
            )

        if duration_minutes <= 0:
            raise ValueError("Duração da reserva deve ser positiva.")
        if passengers < 1:
            raise ValueError("Número de passageiros deve ser pelo menos 1.")
        if bags < 0:
            raise ValueError("Número de malas não pode ser negativo.")

        budget_calc_data = {
            "passengers": passengers,
            "bags": bags,
            "pickupLocation": pickup_location,
            "dropoffLocation": dropoff_location,
        }
        base_budget_details = calculate_estimated_budget(
            budget_calc_data, request_time_obj=time_obj
        )
        original_budget_pre_vat_calc = base_budget_details["original_budget_pre_vat"]

        final_budget_pre_vat_calc = original_budget_pre_vat_calc
        discount_amount_calc = 0.0
        applied_voucher_code_final = None
        validated_voucher_obj = None
        if voucher_code_from_frontend and voucher_code_from_frontend.strip():
            try:
                validated_voucher_obj = validate_voucher_for_use(
                    voucher_code_from_frontend, original_budget_pre_vat_calc
                )
                (
                    final_budget_pre_vat_calc,
                    discount_amount_calc,
                ) = apply_voucher_to_budget(
                    original_budget_pre_vat_calc, validated_voucher_obj
                )
                applied_voucher_code_final = validated_voucher_obj.code
                logger.info(
                    f"Voucher '{applied_voucher_code_final}' validado e aplicado no backend para a reserva."
                )
            except ValueError as ve_voucher:
                logger.warning(
                    f"Voucher '{voucher_code_from_frontend}' falhou validação no backend durante criação de reserva: {ve_voucher}. Ignorando voucher."
                )

        vat_percentage_calc = current_app.config.get("VAT_RATE", 23.0)
        vat_amount_calc = round(
            final_budget_pre_vat_calc * (vat_percentage_calc / 100.0), 2
        )
        total_with_vat_calc = round(final_budget_pre_vat_calc + vat_amount_calc, 2)

        new_booking = Booking(
            passenger_name=passenger_name,
            passenger_phone=passenger_phone,
            date=date_obj,
            time=time_obj,
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
            status="PENDING_CONFIRMATION",
        )
        sqlAlchemy.session.add(new_booking)
        sqlAlchemy.session.commit()

        if new_booking.applied_voucher_code:
            record_voucher_usage(new_booking.applied_voucher_code)

        sqlAlchemy.session.refresh(new_booking)
        logger.info(
            f"Reserva criada na BD com ID: {new_booking.id}, Total c/IVA: {new_booking.total_with_vat}, Voucher: {new_booking.applied_voucher_code}"
        )
        return new_booking

    except ValueError as ve:
        sqlAlchemy.session.rollback()
        logger.error(f"Erro de valor ao criar reserva: {ve}")
        raise
    except KeyError as ke:
        sqlAlchemy.session.rollback()
        logger.error(f"Erro de dados em falta ao criar reserva: {ke}")
        raise ValueError(f"Dados de reserva incompletos: falta o campo {ke}.")
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(f"Erro de BD ao criar reserva: {e}", exc_info=True)
        raise ValueError("Erro de base de dados ao criar a reserva.")
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(f"Erro inesperado ao criar reserva: {e_unexp}", exc_info=True)
        raise ValueError("Erro interno inesperado ao criar a reserva.")


def update_booking_status(booking_id: int, new_status: str) -> Booking | None:
    allowed_statuses = current_app.config.get("ALLOWED_BOOKING_STATUSES", [])
    if new_status not in allowed_statuses:
        raise ValueError(
            f"Status inválido: '{new_status}'. Status permitidos: {', '.join(allowed_statuses)}"
        )
    try:
        booking_to_update = (
            sqlAlchemy.session.query(Booking).filter(Booking.id == booking_id).first()
        )
        if booking_to_update:
            booking_to_update.status = new_status
            sqlAlchemy.session.commit()
            sqlAlchemy.session.refresh(booking_to_update)
            return booking_to_update
        return None
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(
            f"Erro de BD ao atualizar status da reserva {booking_id}: {e}",
            exc_info=True,
        )
        raise ValueError("Erro de BD ao atualizar status da reserva.")
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            f"Erro inesperado ao atualizar status da reserva {booking_id}: {e_unexp}",
            exc_info=True,
        )
        raise ValueError("Erro inesperado ao atualizar status da reserva.")


def assign_driver_to_booking(booking_id: int, driver_id: int | None) -> Booking | None:
    mail_instance = current_app.extensions.get("mail")
    if not mail_instance:
        logger.error(
            "Instância Flask-Mail não encontrada em current_app.extensions. Emails não serão enviados."
        )

    try:
        booking_to_update = (
            sqlAlchemy.session.query(Booking)
            .options(joinedload(Booking.assigned_driver))
            .filter(Booking.id == booking_id)
            .first()
        )
        if not booking_to_update:
            return None

        driver_to_assign = None
        if driver_id is not None:
            driver_to_assign = get_driver_by_id(driver_id)
            if not driver_to_assign:
                raise ValueError(f"Motorista com ID {driver_id} não encontrado.")
            if not driver_to_assign.is_active:
                raise ValueError(
                    f"Motorista ID {driver_id} está inativo e não pode ser atribuído."
                )

        previous_driver_id = booking_to_update.assigned_driver_id
        booking_to_update.assigned_driver_id = driver_id

        if driver_id is not None and booking_to_update.status == "CONFIRMED":
            booking_to_update.status = "DRIVER_ASSIGNED"
        elif driver_id is None and booking_to_update.status == "DRIVER_ASSIGNED":
            booking_to_update.status = "CONFIRMED"

        sqlAlchemy.session.commit()
        sqlAlchemy.session.refresh(booking_to_update)

        if (
            mail_instance
            and driver_id is not None
            and driver_id != previous_driver_id
            and driver_to_assign
            and driver_to_assign.email
        ):
            try:
                send_driver_assignment_email(
                    mail_instance, driver_to_assign, booking_to_update
                )
            except Exception as email_error:
                logger.error(
                    f"Erro ao enviar email de atribuição para motorista ID {driver_id} (reserva {booking_id}): {email_error}",
                    exc_info=True,
                )

        return booking_to_update
    except ValueError as ve:
        raise ve
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(
            f"Erro de BD ao atribuir motorista à reserva {booking_id}: {e}",
            exc_info=True,
        )
        raise ValueError("Erro de base de dados ao atribuir motorista.")
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            f"Erro inesperado ao atribuir motorista à reserva {booking_id}: {e_unexp}",
            exc_info=True,
        )
        raise ValueError("Erro inesperado ao atribuir motorista.")


def get_all_bookings() -> list[Booking]:
    try:
        return (
            sqlAlchemy.session.query(Booking)
            .options(joinedload(Booking.assigned_driver))
            .order_by(Booking.date.desc(), Booking.time.desc())
            .all()
        )
    except SQLAlchemyError as e:
        logger.error(f"Erro de BD ao obter todas as reservas: {e}", exc_info=True)
        raise ValueError("Erro de BD ao obter todas as reservas.")
    except Exception as e_unexp:
        logger.error(
            f"Erro inesperado ao obter todas as reservas: {e_unexp}", exc_info=True
        )
        raise ValueError("Erro inesperado ao obter todas as reservas.")


def delete_booking_by_id(booking_id: int) -> bool:
    try:
        booking_to_delete = (
            sqlAlchemy.session.query(Booking).filter(Booking.id == booking_id).first()
        )
        if booking_to_delete:
            sqlAlchemy.session.delete(booking_to_delete)
            sqlAlchemy.session.commit()
            return True
        return False
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(f"Erro de BD ao excluir reserva {booking_id}: {e}", exc_info=True)
        raise ValueError("Erro de BD ao excluir reserva.")
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            f"Erro inesperado ao excluir reserva {booking_id}: {e_unexp}", exc_info=True
        )
        raise ValueError("Erro inesperado ao excluir reserva.")
