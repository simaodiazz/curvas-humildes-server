from ..models.tariff_settings import TariffSettings
from flask import current_app
from ..db import sqlAlchemy
from logging import getLogger
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

import datetime

logger = getLogger(__name__)


def get_active_tariff_settings() -> TariffSettings:
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
                return default_settings
            except IntegrityError as ie:
                sqlAlchemy.session.rollback()
                logger.warning(
                    f"Erro integridade criar tarifa padrão (provavelmente já existe): {ie}. Obtendo novamente."
                )
                settings = (
                    sqlAlchemy.session.query(TariffSettings)
                    .filter(TariffSettings.id == 1)
                    .first()
                )
                if settings:
                    return settings
                else:
                    logger.error("Falha obter tarifa mesmo após erro integridade.")
                    raise ValueError("Não foi possível carregar/criar config. tarifa.")
            except SQLAlchemyError as e_inner:
                sqlAlchemy.session.rollback()
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
        settings_to_update = (
            sqlAlchemy.session.query(TariffSettings)
            .filter(TariffSettings.id == 1)
            .first()
        )
        if not settings_to_update:
            raise ValueError(
                "Config. tarifa base (id=1) não encontrada para atualização."
            )

        logger.info(f"Atualizando config. tarifa. Dados recebidos: {settings_data}")

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
                try:
                    raw_value = settings_data[key]
                    if value_type == bool:
                        converted_value = str(raw_value).lower() in [
                            "true",
                            "on",
                            "1",
                            "yes",
                        ]
                    else:
                        converted_value = value_type(raw_value)

                    if model_attr in [
                        "night_surcharge_start_hour",
                        "night_surcharge_end_hour",
                    ] and not (0 <= converted_value <= 23):
                        raise ValueError(f"{key} deve estar entre 0 e 23.")
                    if model_attr == "night_surcharge_percentage" and not (
                        0 <= converted_value <= 100
                    ):
                        raise ValueError(f"{key} deve estar entre 0 e 100.")

                    setattr(settings_to_update, model_attr, converted_value)
                    updated_fields = True
                except (ValueError, TypeError) as e_conv:
                    logger.warning(
                        f"Erro ao converter o valor para '{key}': {raw_value} -> {value_type}. Erro: {e_conv}"
                    )
                    raise ValueError(f"Valor inválido para '{key}': {raw_value}.")

        if updated_fields:
            settings_to_update.updated_at = datetime.datetime.utcnow()
            sqlAlchemy.session.commit()
            sqlAlchemy.session.refresh(settings_to_update)
            logger.info(f"Config. tarifa atualizada: {settings_to_update}")
        else:
            logger.info("Nenhum campo de tarifa foi atualizado.")

        return settings_to_update

    except ValueError as ve:
        sqlAlchemy.session.rollback()
        logger.warning(f"Erro de valor ao atualizar tarifas: {ve}")
        raise
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(f"Erro de BD ao atualizar tarifas: {e}", exc_info=True)
        raise ValueError("Erro de BD ao atualizar configurações de tarifa.")
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(f"Erro inesperado ao atualizar tarifas: {e_unexp}", exc_info=True)
        raise ValueError("Erro inesperado ao atualizar configurações de tarifa.")
