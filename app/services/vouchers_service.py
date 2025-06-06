from ..models.voucher import Voucher
from ..db import sqlAlchemy
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from logging import getLogger

import datetime

logger = getLogger(__name__)


def create_voucher(voucher_data: dict) -> Voucher:
    try:
        code = str(voucher_data.get("code", "")).strip().upper()
        if not code:
            raise ValueError("Código do voucher é obrigatório.")

        discount_type = str(voucher_data.get("discount_type", "")).upper()
        if discount_type not in ["PERCENTAGE", "FIXED_AMOUNT"]:
            raise ValueError(
                "Tipo de desconto inválido. Deve ser 'PERCENTAGE' ou 'FIXED_AMOUNT'."
            )

        discount_value = float(voucher_data.get("discount_value", 0))
        if discount_value <= 0:
            raise ValueError("Valor do desconto deve ser maior que zero.")
        if discount_type == "PERCENTAGE" and not (0 < discount_value <= 100):
            raise ValueError(
                "Desconto em percentagem deve ser entre 0 (exclusivo) e 100 (inclusivo)."
            )

        expiration_date_str = voucher_data.get("expiration_date")
        expiration_date = None
        if expiration_date_str and str(expiration_date_str).strip():
            try:
                expiration_date = datetime.datetime.strptime(
                    expiration_date_str, "%Y-%m-%d"
                ).date()
            except ValueError:
                raise ValueError(
                    "Formato da data de validade inválido. Use AAAA-MM-DD."
                )

        max_uses = int(voucher_data.get("max_uses", 1))
        if max_uses < 0:
            raise ValueError("Máximo de usos deve ser 0 (ilimitado) ou maior.")

        min_booking_value_str = voucher_data.get("min_booking_value")
        min_booking_value = None
        if (
            min_booking_value_str is not None
            and str(min_booking_value_str).strip() != ""
        ):
            try:
                min_booking_value = float(min_booking_value_str)
                if min_booking_value < 0:
                    raise ValueError("Valor mínimo da reserva não pode ser negativo.")
            except ValueError:
                raise ValueError("Valor mínimo da reserva deve ser um número válido.")

        new_voucher = Voucher(
            code=code,
            description=voucher_data.get("description"),
            discount_type=discount_type,
            discount_value=discount_value,
            expiration_date=expiration_date,
            max_uses=max_uses,
            min_booking_value=min_booking_value,
            is_active=voucher_data.get("is_active", True),
        )
        sqlAlchemy.session.add(new_voucher)
        sqlAlchemy.session.commit()
        sqlAlchemy.session.refresh(new_voucher)
        return new_voucher
    except IntegrityError:
        sqlAlchemy.session.rollback()
        raise ValueError(f"Voucher com o código '{code}' já existe.")
    except ValueError as ve:
        sqlAlchemy.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(f"Erro de BD ao criar voucher: {e}", exc_info=True)
        raise ValueError("Erro de base de dados ao criar o voucher.")
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(f"Erro inesperado ao criar voucher: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao criar o voucher.")


def get_voucher_by_id(voucher_id: int) -> Voucher | None:
    try:
        return (
            sqlAlchemy.session.query(Voucher).filter(Voucher.id == voucher_id).first()
        )
    except SQLAlchemyError as e:
        logger.error(
            f"Erro de BD ao obter voucher por ID {voucher_id}: {e}", exc_info=True
        )
        raise ValueError(f"Erro de BD ao obter voucher ID {voucher_id}.")


def get_voucher_by_code(code: str) -> Voucher | None:
    try:
        return (
            sqlAlchemy.session.query(Voucher)
            .filter(Voucher.code == code.upper())
            .first()
        )
    except SQLAlchemyError as e:
        logger.error(
            f"Erro de BD ao obter voucher por código {code}: {e}", exc_info=True
        )
        raise ValueError(f"Erro de BD ao obter voucher '{code}'.")


def get_all_vouchers() -> list[Voucher]:
    try:
        return (
            sqlAlchemy.session.query(Voucher).order_by(Voucher.created_at.desc()).all()
        )
    except SQLAlchemyError as e:
        logger.error(f"Erro de BD ao obter todos os vouchers: {e}", exc_info=True)
        raise ValueError("Erro de BD ao obter todos os vouchers.")


def update_voucher(voucher_id: int, voucher_data: dict) -> Voucher | None:
    try:
        voucher_to_update = get_voucher_by_id(voucher_id)
        if not voucher_to_update:
            return None

        updated_fields = False
        if "description" in voucher_data:
            voucher_to_update.description = voucher_data["description"]
            updated_fields = True
        if "discount_type" in voucher_data:
            discount_type = str(voucher_data["discount_type"]).upper()
            if discount_type not in ["PERCENTAGE", "FIXED_AMOUNT"]:
                raise ValueError("Tipo de desconto inválido.")
            voucher_to_update.discount_type = discount_type
            updated_fields = True
        if "discount_value" in voucher_data:
            discount_value = float(voucher_data["discount_value"])
            if discount_value <= 0:
                raise ValueError("Valor do desconto deve ser > 0.")
            if voucher_to_update.discount_type == "PERCENTAGE" and not (
                0 < discount_value <= 100
            ):
                raise ValueError("Desconto em percentagem deve ser > 0 e <= 100.")
            voucher_to_update.discount_value = discount_value
            updated_fields = True
        if "expiration_date" in voucher_data:
            exp_date_str = voucher_data["expiration_date"]
            if exp_date_str and str(exp_date_str).strip():
                try:
                    voucher_to_update.expiration_date = datetime.datetime.strptime(
                        exp_date_str, "%Y-%m-%d"
                    ).date()
                except ValueError:
                    raise ValueError(
                        "Formato da data de validade inválido. Use AAAA-MM-DD."
                    )
            else:
                voucher_to_update.expiration_date = None
            updated_fields = True
        if "max_uses" in voucher_data:
            max_uses = int(voucher_data["max_uses"])
            if max_uses < 0:
                raise ValueError("Máximo de usos deve ser >= 0.")
            voucher_to_update.max_uses = max_uses
            updated_fields = True
        if "min_booking_value" in voucher_data:
            min_val_str = voucher_data["min_booking_value"]
            if min_val_str is not None and str(min_val_str).strip() != "":
                try:
                    min_val = float(min_val_str)
                    if min_val < 0:
                        raise ValueError(
                            "Valor mínimo da reserva não pode ser negativo."
                        )
                    voucher_to_update.min_booking_value = min_val
                except ValueError:
                    raise ValueError("Valor mínimo da reserva inválido.")
            else:
                voucher_to_update.min_booking_value = None
            updated_fields = True
        if "is_active" in voucher_data:
            voucher_to_update.is_active = bool(voucher_data["is_active"])
            updated_fields = True

        if updated_fields:
            voucher_to_update.updated_at = datetime.datetime.utcnow()
            sqlAlchemy.session.commit()
            sqlAlchemy.session.refresh(voucher_to_update)
        return voucher_to_update
    except ValueError as ve:
        sqlAlchemy.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(
            f"Erro de BD ao atualizar voucher {voucher_id}: {e}", exc_info=True
        )
        raise ValueError("Erro de BD ao atualizar o voucher.")
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            f"Erro inesperado ao atualizar voucher {voucher_id}: {e_unexp}",
            exc_info=True,
        )
        raise ValueError("Erro inesperado ao atualizar o voucher.")


def delete_voucher(voucher_id: int) -> bool:
    try:
        voucher_to_delete = get_voucher_by_id(voucher_id)
        if voucher_to_delete:
            sqlAlchemy.session.delete(voucher_to_delete)
            sqlAlchemy.session.commit()
            return True
        return False
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(f"Erro de BD ao excluir voucher {voucher_id}: {e}", exc_info=True)
        if "FOREIGN KEY constraint failed" in str(e).lower():
            raise ValueError(
                f"Não é possível excluir o voucher ID {voucher_id} pois está referenciado noutros registos (ex: reservas)."
            )
        raise ValueError("Erro de BD ao excluir o voucher.")
    except ValueError:
        sqlAlchemy.session.rollback()
        raise
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            f"Erro inesperado ao excluir voucher {voucher_id}: {e_unexp}", exc_info=True
        )
        raise ValueError("Erro inesperado ao excluir o voucher.")


def validate_voucher_for_use(
    code: str, booking_budget_pre_vat: float | None = None
) -> Voucher:
    if not code:
        raise ValueError("Código do voucher não pode ser vazio.")
    voucher = get_voucher_by_code(code)
    if not voucher:
        raise ValueError(f"Voucher '{code.upper()}' não encontrado.")
    if not voucher.is_active:
        raise ValueError(f"Voucher '{code.upper()}' não está ativo.")
    if voucher.expiration_date and voucher.expiration_date < datetime.date.today():
        raise ValueError(
            f"Voucher '{code.upper()}' expirou em {voucher.expiration_date.strftime('%d/%m/%Y')}."
        )
    if voucher.max_uses > 0 and voucher.current_uses >= voucher.max_uses:
        raise ValueError(
            f"Voucher '{code.upper()}' atingiu o limite máximo de utilizações."
        )
    if (
        booking_budget_pre_vat is not None
        and voucher.min_booking_value is not None
        and booking_budget_pre_vat < voucher.min_booking_value
    ):
        raise ValueError(
            f"Voucher '{code.upper()}' requer um valor mínimo de reserva (antes de IVA) de {voucher.min_booking_value:.2f} EUR."
        )
    return voucher


def apply_voucher_to_budget(
    original_budget_pre_vat: float, voucher: Voucher
) -> tuple[float, float]:
    discount_amount = 0.0
    if voucher.discount_type == "PERCENTAGE":
        discount_amount = (original_budget_pre_vat * voucher.discount_value) / 100.0
    elif voucher.discount_type == "FIXED_AMOUNT":
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
            sqlAlchemy.session.commit()
            logger.info(
                f"Utilização do voucher '{voucher.code}' registada. Usos atuais: {voucher.current_uses}"
            )
        else:
            logger.error(
                f"Tentativa de registar uso para voucher inexistente: {voucher_code}"
            )
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(
            f"Erro de BD ao registar uso do voucher {voucher_code}: {e}", exc_info=True
        )
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            f"Erro inesperado ao registar uso do voucher {voucher_code}: {e_unexp}",
            exc_info=True,
        )
