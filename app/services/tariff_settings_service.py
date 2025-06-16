"""Serviço para configuração de tarifas, com Flask-Caching."""
import datetime
from logging import getLogger
from flask import current_app
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from ..db import sqlAlchemy
from ..models.tariff_settings import TariffSettings
from ..cache import flaskCaching

logger = getLogger(__name__)

_TARIFF_SETTINGS_CACHE_KEY = "tariff_settings:active"


def get_active_tariff_settings() -> TariffSettings:
    """Obtém ou cria as configurações de tarifa ativas (id=1), com cache."""
    cached = flaskCaching.get(_TARIFF_SETTINGS_CACHE_KEY)
    if cached:
        return cached
    try:
        settings = (
            sqlAlchemy.session.query(TariffSettings)
            .filter(TariffSettings.id == 1)
            .first()
        )
        if not settings:
            logger.warning(
                "Nenhuma config. tarifa (id=1). A criar padrão a partir de current_app.config."
            )
            try:
                default_settings = TariffSettings(
                    id=1,
                    base_rate_eur=current_app.config.get("BASE_RATE_EUR", 10.0),
                    rate_per_km_eur=current_app.config.get("RATE_PER_KM_EUR", 0.85),
                    rate_per_passenger_eur=current_app.config.get(
                        "RATE_PER_PASSENGER_EUR", 2.5
                    ),
                    rate_per_bag_eur=current_app.config.get("RATE_PER_BAG_EUR", 1.0),
                    night_surcharge_applies=current_app.config.get(
                        "NIGHT_SURCHARGE_APPLIES", True
                    ),
                    night_surcharge_percentage=current_app.config.get(
                        "NIGHT_SURCHARGE_PERCENTAGE", 20.0
                    ),
                    night_surcharge_start_hour=current_app.config.get(
                        "NIGHT_SURCHARGE_START_HOUR", 22
                    ),
                    night_surcharge_end_hour=current_app.config.get(
                        "NIGHT_SURCHARGE_END_HOUR", 6
                    ),
                    booking_slot_overlap_minutes=current_app.config.get(
                        "BOOKING_SLOT_OVERLAP_MINUTES", 30
                    ),
                )
                sqlAlchemy.session.add(default_settings)
                sqlAlchemy.session.commit()
                logger.info("Config. tarifa padrão criada.")
                # Cacheia!
                flaskCaching.set(
                    _TARIFF_SETTINGS_CACHE_KEY, default_settings, timeout=300
                )
                return default_settings
            except IntegrityError as ie:
                sqlAlchemy.session.rollback()
                logger.warning(
                    "Erro integridade criar tarifa padrão (provavelmente já existe): %s. Obtendo novamente.",
                    ie,
                )
                settings = (
                    sqlAlchemy.session.query(TariffSettings)
                    .filter(TariffSettings.id == 1)
                    .first()
                )
                if settings:
                    flaskCaching.set(_TARIFF_SETTINGS_CACHE_KEY, settings, timeout=300)
                    return settings
                logger.error("Falha ao obter tarifa mesmo após erro integridade.")
                raise ValueError(
                    "Não foi possível carregar/criar config. tarifa."
                ) from ie
            except SQLAlchemyError as e_inner:
                sqlAlchemy.session.rollback()
                logger.error("Erro BD criar tarifa padrão: %s", e_inner, exc_info=True)
                raise ValueError("Erro BD criar config. tarifa.") from e_inner
        # Cacheia!
        flaskCaching.set(_TARIFF_SETTINGS_CACHE_KEY, settings, timeout=300)
        return settings
    except SQLAlchemyError as e_outer:
        logger.error("Erro BD geral obter tarifa: %s", e_outer, exc_info=True)
        raise ValueError("Erro BD carregar config. tarifa.") from e_outer
    except Exception as e_fatal:
        logger.error("Erro inesperado fatal obter tarifa: %s", e_fatal, exc_info=True)
        raise ValueError("Erro inesperado carregar config. tarifa.") from e_fatal


def update_tariff_settings(settings_data: dict) -> TariffSettings:
    """Atualiza os valores das configurações de tarifa, invalidando o cache."""
    try:
        settings_to_update = (
            sqlAlchemy.session.query(TariffSettings)
            .filter(TariffSettings.id == 1)
            .first()
        )
        if not settings_to_update:
            raise ValueError(
                "Config. tarifa base (id=1) não encontrada para atualização."
            )
        logger.info("Atualizando config. tarifa. Dados recebidos: %s", settings_data)
        field_map = {
            "base_rate_eur": (float, "base_rate_eur"),
            "rate_per_km_eur": (float, "rate_per_km_eur"),
            "rate_per_passenger_eur": (float, "rate_per_passenger_eur"),
            "rate_per_bag_eur": (float, "rate_per_bag_eur"),
            "night_surcharge_applies": (bool, "night_surcharge_applies"),
            "night_surcharge_percentage": (float, "night_surcharge_percentage"),
            "night_surcharge_start_hour": (int, "night_surcharge_start_hour"),
            "night_surcharge_end_hour": (int, "night_surcharge_end_hour"),
            "booking_slot_overlap_minutes": (int, "booking_slot_overlap_minutes"),
        }
        updated_fields = False
        for key, (value_type, model_attr) in field_map.items():
            if key in settings_data:
                raw_value = settings_data[key]
                try:
                    if value_type == bool:
                        converted_value = str(raw_value).lower() in [
                            "true",
                            "on",
                            "1",
                            "yes",
                        ]
                    else:
                        converted_value = value_type(raw_value)
                    if (
                        model_attr
                        in [
                            "night_surcharge_start_hour",
                            "night_surcharge_end_hour",
                        ]
                        and not 0 <= converted_value <= 23
                    ):
                        raise ValueError(f"{key} deve estar entre 0 e 23.")
                    if (
                        model_attr == "night_surcharge_percentage"
                        and not 0 <= converted_value <= 100
                    ):
                        raise ValueError(f"{key} deve estar entre 0 e 100.")
                    setattr(settings_to_update, model_attr, converted_value)
                    updated_fields = True
                except (ValueError, TypeError) as e_conv:
                    logger.warning(
                        "Erro ao converter o valor para '%s': %s -> %s. Erro: %s",
                        key,
                        raw_value,
                        value_type,
                        e_conv,
                    )
                    raise ValueError(
                        f"Valor inválido para '{key}': {raw_value}."
                    ) from e_conv
        if updated_fields:
            settings_to_update.updated_at = datetime.datetime.utcnow()
            sqlAlchemy.session.commit()
            sqlAlchemy.session.refresh(settings_to_update)
            logger.info("Config. tarifa atualizada: %s", settings_to_update)
            flaskCaching.delete(_TARIFF_SETTINGS_CACHE_KEY)  # <------- INVALIDA CACHE!
        else:
            logger.info("Nenhum campo de tarifa foi atualizado.")
        return settings_to_update
    except ValueError as ve:
        sqlAlchemy.session.rollback()
        logger.warning("Erro de valor ao atualizar tarifas: %s", ve)
        raise
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error("Erro de BD ao atualizar tarifas: %s", e, exc_info=True)
        raise ValueError("Erro de BD ao atualizar configurações de tarifa.") from e
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error("Erro inesperado ao atualizar tarifas: %s", e_unexp, exc_info=True)
        raise ValueError(
            "Erro inesperado ao atualizar configurações de tarifa."
        ) from e_unexp
