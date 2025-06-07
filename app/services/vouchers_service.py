"""Serviço de gestão de vouchers, com Flask-Caching."""
import datetime
from logging import getLogger
from typing import Optional, Tuple, List
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from ..db import sqlAlchemy
from ..models.voucher import Voucher
from ..cache import flaskCaching

logger = getLogger(__name__)


def _make_id_cache_key(voucher_id):
    return f"voucher:id:{voucher_id}"


def _make_code_cache_key(code):
    return f"voucher:code:{code.upper()}"


_ALL_VOUCHERS_CACHE_KEY = "voucher:all"


def _parse_code(voucher_data: dict) -> str:
    code = str(voucher_data.get("code", "")).strip().upper()
    if not code:
        raise ValueError("Código do voucher é obrigatório.")
    return code


def _parse_discount_type(voucher_data: dict) -> str:
    discount_type = str(voucher_data.get("discount_type", "")).strip().upper()
    if discount_type not in ("PERCENTAGE", "FIXED_AMOUNT"):
        raise ValueError(
            "Tipo de desconto inválido. Deve ser 'PERCENTAGE' ou 'FIXED_AMOUNT'."
        )
    return discount_type


def _parse_discount_value(voucher_data: dict, discount_type: str) -> float:
    try:
        discount_value = float(voucher_data.get("discount_value", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("Valor do desconto deve ser um número válido.") from exc
    if discount_value <= 0:
        raise ValueError("Valor do desconto deve ser maior que zero.")
    if discount_type == "PERCENTAGE" and not (0 < discount_value <= 100):
        raise ValueError(
            "Desconto em percentagem deve ser entre 0 (exclusivo) e 100 (inclusivo)."
        )
    return discount_value


def _parse_expiration_date(date_str: Optional[str]) -> Optional[datetime.date]:
    if date_str and str(date_str).strip():
        try:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(
                "Formato da data de validade inválido. Use AAAA-MM-DD."
            ) from exc
    return None


def _parse_max_uses(voucher_data: dict) -> int:
    try:
        max_uses = int(voucher_data.get("max_uses", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError("Máximo de usos deve ser um número inteiro.") from exc
    if max_uses < 0:
        raise ValueError("Máximo de usos deve ser 0 (ilimitado) ou maior.")
    return max_uses


def _parse_min_booking_value(value) -> Optional[float]:
    if value is not None and str(value).strip() != "":
        try:
            min_booking_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Valor mínimo da reserva deve ser um número válido."
            ) from exc
        if min_booking_value < 0:
            raise ValueError("Valor mínimo da reserva não pode ser negativo.")
        return min_booking_value
    return None


# --- CRUD principal com cache ---


def create_voucher(voucher_data: dict) -> Voucher:
    """Cria um novo voucher com os dados fornecidos."""
    try:
        code = _parse_code(voucher_data)
        discount_type = _parse_discount_type(voucher_data)
        discount_value = _parse_discount_value(voucher_data, discount_type)
        expiration_date = _parse_expiration_date(voucher_data.get("expiration_date"))
        max_uses = _parse_max_uses(voucher_data)
        min_booking_value = _parse_min_booking_value(
            voucher_data.get("min_booking_value")
        )
        new_voucher = Voucher(
            code=code,
            description=voucher_data.get("description"),
            discount_type=discount_type,
            discount_value=discount_value,
            expiration_date=expiration_date,
            max_uses=max_uses,
            min_booking_value=min_booking_value,
            is_active=bool(voucher_data.get("is_active", True)),
        )
        sqlAlchemy.session.add(new_voucher)
        sqlAlchemy.session.commit()
        sqlAlchemy.session.refresh(new_voucher)
        # Invalida todos caches relevantes
        flaskCaching.delete(_ALL_VOUCHERS_CACHE_KEY)
        flaskCaching.delete(_make_code_cache_key(code))
        flaskCaching.delete(_make_id_cache_key(new_voucher.id))
        return new_voucher
    except IntegrityError as exc:
        sqlAlchemy.session.rollback()
        raise ValueError(
            f"Voucher com o código '{voucher_data.get('code')}' já existe."
        ) from exc
    except ValueError as ve:
        sqlAlchemy.session.rollback()
        raise
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error("Erro de BD ao criar voucher: %s", e, exc_info=True)
        raise ValueError("Erro de base de dados ao criar o voucher.") from e
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error("Erro inesperado ao criar voucher: %s", e_unexp, exc_info=True)
        raise ValueError("Erro inesperado ao criar o voucher.") from e_unexp


def get_voucher_by_id(voucher_id: int) -> Optional[Voucher]:
    """Obtém um voucher pelo seu ID, usando cache."""
    cache_key = _make_id_cache_key(voucher_id)
    cached = flaskCaching.get(cache_key)
    if cached:
        return cached
    try:
        voucher = sqlAlchemy.session.query(Voucher).filter_by(id=voucher_id).first()
        if voucher:
            flaskCaching.set(cache_key, voucher, timeout=120)
        return voucher
    except SQLAlchemyError as e:
        logger.error(
            "Erro de BD ao obter voucher por ID %d: %s", voucher_id, e, exc_info=True
        )
        raise ValueError(f"Erro de BD ao obter voucher ID {voucher_id}.") from e


def get_voucher_by_code(code: str) -> Optional[Voucher]:
    """Obtém um voucher pelo seu código, usando cache."""
    cache_key = _make_code_cache_key(code)
    cached = flaskCaching.get(cache_key)
    if cached:
        return cached
    try:
        voucher = (
            sqlAlchemy.session.query(Voucher)
            .filter(Voucher.code == code.upper())
            .first()
        )
        if voucher:
            flaskCaching.set(cache_key, voucher, timeout=120)
        return voucher
    except SQLAlchemyError as e:
        logger.error(
            "Erro de BD ao obter voucher por código %s: %s", code, e, exc_info=True
        )
        raise ValueError(f"Erro de BD ao obter voucher '{code}'.") from e


def get_all_vouchers() -> List[Voucher]:
    """Obtém todos os vouchers ordenados pela data de criação decrescente, usando cache."""
    cache_key = _ALL_VOUCHERS_CACHE_KEY
    cached = flaskCaching.get(cache_key)
    if cached:
        return cached
    try:
        result = (
            sqlAlchemy.session.query(Voucher).order_by(Voucher.created_at.desc()).all()
        )
        flaskCaching.set(cache_key, result, timeout=120)
        return result
    except SQLAlchemyError as e:
        logger.error("Erro de BD ao obter todos os vouchers: %s", e, exc_info=True)
        raise ValueError("Erro de BD ao obter todos os vouchers.") from e


def update_voucher(voucher_id: int, voucher_data: dict) -> Optional[Voucher]:
    """Atualiza os dados de um voucher existente (com limpeza de cache)."""
    try:
        voucher = get_voucher_by_id(voucher_id)
        if not voucher:
            return None
        updated_fields = False
        if "description" in voucher_data:
            voucher.description = voucher_data["description"]
            updated_fields = True
        if "discount_type" in voucher_data:
            discount_type = _parse_discount_type(voucher_data)
            voucher.discount_type = discount_type
            updated_fields = True
        if "discount_value" in voucher_data:
            discount_value = _parse_discount_value(voucher_data, voucher.discount_type)
            voucher.discount_value = discount_value
            updated_fields = True
        if "expiration_date" in voucher_data:
            voucher.expiration_date = _parse_expiration_date(
                voucher_data["expiration_date"]
            )
            updated_fields = True
        if "max_uses" in voucher_data:
            voucher.max_uses = _parse_max_uses(voucher_data)
            updated_fields = True
        if "min_booking_value" in voucher_data:
            voucher.min_booking_value = _parse_min_booking_value(
                voucher_data["min_booking_value"]
            )
            updated_fields = True
        if "is_active" in voucher_data:
            voucher.is_active = bool(voucher_data["is_active"])
            updated_fields = True
        if updated_fields:
            voucher.updated_at = datetime.datetime.utcnow()
            sqlAlchemy.session.commit()
            sqlAlchemy.session.refresh(voucher)
            # Limpa caches
            flaskCaching.delete(_ALL_VOUCHERS_CACHE_KEY)
            flaskCaching.delete(_make_code_cache_key(voucher.code))
            flaskCaching.delete(_make_id_cache_key(voucher.id))
        return voucher
    except ValueError:
        sqlAlchemy.session.rollback()
        raise
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro de BD ao atualizar voucher %d: %s", voucher_id, e, exc_info=True
        )
        raise ValueError("Erro de BD ao atualizar o voucher.") from e
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro inesperado ao atualizar voucher %d: %s",
            voucher_id,
            e_unexp,
            exc_info=True,
        )
        raise ValueError("Erro inesperado ao atualizar o voucher.") from e_unexp


def delete_voucher(voucher_id: int) -> bool:
    """Remove um voucher do sistema (inclusive do cache)."""
    try:
        voucher = get_voucher_by_id(voucher_id)
        if voucher:
            sqlAlchemy.session.delete(voucher)
            sqlAlchemy.session.commit()
            # Limpa caches
            flaskCaching.delete(_ALL_VOUCHERS_CACHE_KEY)
            flaskCaching.delete(_make_code_cache_key(voucher.code))
            flaskCaching.delete(_make_id_cache_key(voucher.id))
            return True
        return False
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro de BD ao excluir voucher %d: %s", voucher_id, e, exc_info=True
        )
        if "FOREIGN KEY constraint failed" in str(e).lower():
            raise ValueError(
                f"Não é possível excluir o voucher ID {voucher_id} pois está referenciado noutros registos (ex: reservas)."
            ) from e
        raise ValueError("Erro de BD ao excluir o voucher.") from e
    except ValueError:
        sqlAlchemy.session.rollback()
        raise
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro inesperado ao excluir voucher %d: %s",
            voucher_id,
            e_unexp,
            exc_info=True,
        )
        raise ValueError("Erro inesperado ao excluir o voucher.") from e_unexp


def validate_voucher_for_use(
    code: str, booking_budget_pre_vat: Optional[float] = None
) -> Voucher:
    """Valida se um voucher pode ser utilizado numa dada reserva."""
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
) -> Tuple[float, float]:
    """Aplica o desconto do voucher ao valor de orçamento."""
    discount_amount = 0.0
    if voucher.discount_type == "PERCENTAGE":
        discount_amount = (original_budget_pre_vat * voucher.discount_value) / 100.0
    elif voucher.discount_type == "FIXED_AMOUNT":
        discount_amount = voucher.discount_value
    discount_amount = min(discount_amount, original_budget_pre_vat)
    new_budget_pre_vat = original_budget_pre_vat - discount_amount
    return round(new_budget_pre_vat, 2), round(discount_amount, 2)


def record_voucher_usage(voucher_code: str):
    """Regista a utilização do voucher, incrementando o contador de usos atuais + limpa cache daquele voucher."""
    try:
        voucher = get_voucher_by_code(voucher_code)
        if voucher:
            voucher.current_uses += 1
            voucher.updated_at = datetime.datetime.utcnow()
            sqlAlchemy.session.commit()
            # Limpa caches
            flaskCaching.delete(_ALL_VOUCHERS_CACHE_KEY)
            flaskCaching.delete(_make_code_cache_key(voucher.code))
            flaskCaching.delete(_make_id_cache_key(voucher.id))
            logger.info(
                "Utilização do voucher '%s' registada. Usos atuais: %d",
                voucher.code,
                voucher.current_uses,
            )
        else:
            logger.error(
                "Tentativa de registar uso para voucher inexistente: %s", voucher_code
            )
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro de BD ao registar uso do voucher %s: %s",
            voucher_code,
            e,
            exc_info=True,
        )
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro inesperado ao registar uso do voucher %s: %s",
            voucher_code,
            e_unexp,
            exc_info=True,
        )
