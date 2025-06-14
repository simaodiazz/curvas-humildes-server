from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

sqlAlchemy = SQLAlchemy()
Model = sqlAlchemy.Model


def init_db_engine_with_context(app_instance):
    """
    Inicializa a base de dados e cria tabelas se não existirem.
    """
    from .models.tariff_settings import TariffSettings
    from .models.user import User

    sqlAlchemy.create_all()

    # Cria admin só se não existir
    name = app_instance.config.get("ADMINSTRATOR_NAME")
    if not User.query.filter_by(name=name).first():
        user = User()
        user.name = name
        user.set_password(app_instance.config.get("ADMINSTRATOR_PASSWORD"))
        user.email = app_instance.config.get("ADMINSTRATOR_EMAIL")
        user.phone_number = app_instance.config.get("ADMINSTRATOR_PHONE_NUMBER")
        user.role = "admin"
        sqlAlchemy.session.add(user)
        sqlAlchemy.session.commit()
        app_instance.logger.info(f"User `{user.name}` created.")

    try:
        sqlAlchemy.create_all()

        app_instance.logger.info(
            f"Base de dados verificada/tabelas criadas em {app_instance.config.get('DATABASE_URI')}"
        )

        existing_settings = (
            sqlAlchemy.session.query(TariffSettings)
            .filter(TariffSettings.id == 1)
            .first()
        )
        if not existing_settings:
            app_instance.logger.info("Nenhuma config. tarifa (id=1). A criar padrão...")
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
                app_instance.logger.info("Config. tarifa padrão criada com sucesso.")
            except IntegrityError:
                sqlAlchemy.session.rollback()
                app_instance.logger.warning(
                    "Erro de integridade ao criar config. tarifa padrão (provavelmente já existe). Ignorando."
                )
            except Exception as seed_error:
                sqlAlchemy.session.rollback()
                app_instance.logger.error(
                    f"Erro inesperado ao criar config. tarifa padrão: {seed_error}",
                    exc_info=True,
                )
    except Exception as e:
        app_instance.logger.error(
            f"Erro durante init_db_engine_with_context: {e}", exc_info=True
        )
