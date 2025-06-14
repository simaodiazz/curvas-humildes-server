from datetime import date
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from ..db import sqlAlchemy
from app.models.voucher import Voucher
from app.models.user import User
from ..cache import flaskCaching

# ----------------------------------------------------------
# Função auxiliar para chave de cache
def _voucher_cache_key(voucher_id):
    return f"admin_get_voucher_{voucher_id}"

# ====================
# Métodos de Consulta
# ====================

@flaskCaching.cached(timeout=60, key_prefix="admin_get_all_vouchers")
def get_all_vouchers():
    """
    Retorna todos os vouchers cadastrados.
    """
    return sqlAlchemy.session.query(Voucher).all()

@flaskCaching.cached(timeout=60, key_prefix=lambda voucher_id: _voucher_cache_key(voucher_id))
def get_voucher_by_id(voucher_id):
    """
    Retorna voucher pelo ID.
    """
    return sqlAlchemy.session.query(Voucher).get(voucher_id)

def get_voucher_by_code(voucher_code: str):
    """
    Retorna voucher pelo código (deve ser lowercase e strip fora daqui se necessário).
    """
    return sqlAlchemy.session.query(Voucher).filter_by(code=voucher_code.strip()).first()

# ====================
# CRUD Voucher
# ====================

import datetime
from sqlalchemy.exc import IntegrityError

def create_voucher(data):
    # Corrigir expiration_date: converter string -> date
    expiration_date = data.get("expiration_date")
    if expiration_date:
        try:
            expiration_date = datetime.date.fromisoformat(expiration_date)
        except Exception:
            raise ValueError("Formato de data de validade inválido. Use AAAA-MM-DD.")

    voucher = Voucher(
        code=data["code"],
        description=data.get("description"),
        discount_type=data["discount_type"],
        discount_value=data["discount_value"],
        expiration_date=expiration_date,  # já é date ou None
        max_uses=data.get("max_uses", 1),
        min_booking_value=data.get("min_booking_value"),
        is_active=data.get("is_active", True),
        user_id=data.get("user_id", None),
    )
    sqlAlchemy.session.add(voucher)
    try:
        sqlAlchemy.session.commit()
        flaskCaching.delete("admin_get_all_vouchers")
        return voucher
    except IntegrityError:
        sqlAlchemy.session.rollback()
        raise ValueError("Código de voucher já existente.")
    except Exception:
        sqlAlchemy.session.rollback()
        raise


def update_voucher(voucher_id, data):
    voucher = get_voucher_by_id.__wrapped__(voucher_id)  # Usa sem cache
    if not voucher:
        return None
    for field in [
        "description",
        "discount_type",
        "discount_value",
        "expiration_date",
        "max_uses",
        "min_booking_value",
        "is_active",
    ]:
        if field in data:
            setattr(voucher, field, data[field])
    try:
        sqlAlchemy.session.commit()
        flaskCaching.delete("admin_get_all_vouchers")
        flaskCaching.delete(_voucher_cache_key(voucher_id))
        return voucher
    except Exception:
        sqlAlchemy.session.rollback()
        raise

def delete_voucher(voucher_id):
    voucher = get_voucher_by_id.__wrapped__(voucher_id)
    if not voucher:
        return False
    sqlAlchemy.session.delete(voucher)
    try:
        sqlAlchemy.session.commit()
        flaskCaching.delete("admin_get_all_vouchers")
        flaskCaching.delete(_voucher_cache_key(voucher_id))
        return True
    except Exception:
        sqlAlchemy.session.rollback()
        raise

# ================================================
# Validação e aplicação de voucher ao orçamento
# ================================================

def validate_voucher_for_use(voucher_code: str, booking_value: float) -> Voucher:
    """
    Valida se o voucher pode ser usado para o valor da reserva fornecido.
    Retorna o objeto Voucher se válido.
    Lança ValueError em caso de voucher inválido.
    """
    if not voucher_code or not voucher_code.strip():
        raise ValueError("Código de voucher não informado.")
    voucher = sqlAlchemy.session.query(Voucher).filter_by(code=voucher_code.strip(), is_active=True).first()
    if not voucher:
        raise ValueError("Voucher não encontrado ou inativo.")
    if voucher.expiration_date and voucher.expiration_date < date.today():
        raise ValueError("O voucher está expirado.")
    if voucher.max_uses is not None and voucher.current_uses is not None:
        if voucher.current_uses >= voucher.max_uses:
            raise ValueError("O voucher já atingiu o número máximo de utilizações.")
    if voucher.min_booking_value and booking_value < voucher.min_booking_value:
        raise ValueError(
            f"O valor mínimo da reserva para usar este voucher é {voucher.min_booking_value:.2f} EUR."
        )
    return voucher

def apply_voucher_to_budget(original_budget_pre_vat: float, voucher: Voucher) -> tuple[float, float]:
    """
    Aplica o voucher ao orçamento bruto (sem IVA) e retorna uma tupla:
    (final_budget_pre_vat, discount_amount)
    """
    if not voucher:
        raise ValueError("Voucher não fornecido.")
    if voucher.discount_type == "percent":
        discount = original_budget_pre_vat * (voucher.discount_value / 100.0)
    else:  # "fixed"
        discount = voucher.discount_value
    discount = min(discount, original_budget_pre_vat)
    final_budget = round(original_budget_pre_vat - discount, 2)
    discount = round(discount, 2)
    return final_budget, discount

def record_voucher_usage(voucher_code: str):
    """
    Registra o uso do voucher (incrementa current_uses).
    """
    from logging import getLogger
    logger = getLogger(__name__)
    voucher = sqlAlchemy.session.query(Voucher).filter_by(code=voucher_code).first()
    if not voucher:
        logger.warning("Voucher %s não encontrado para registrar uso.", voucher_code)
        return
    voucher.current_uses = (voucher.current_uses or 0) + 1
    try:
        sqlAlchemy.session.commit()
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error("Erro ao incrementar uso do voucher %s: %s", voucher_code, e, exc_info=True)
        raise ValueError("Erro na base de dados ao contabilizar uso do voucher.") from e


def get_all_vouchers_with_user():
    """
    Retorna todos os vouchers que possuem um usuário associado.
    """
    return sqlAlchemy.session.query(Voucher).filter(Voucher.user_id.isnot(None)).all()
