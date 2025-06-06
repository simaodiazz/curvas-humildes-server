# CurvasSistema/app/models.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float, Date, Time, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
import datetime
from flask import current_app

db = SQLAlchemy()
Base = db.Model

class Driver(Base):
    __tablename__ = 'drivers'
    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=True, unique=True)
    phone_number = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    bookings = relationship("Booking", back_populates="assigned_driver")

    def __repr__(self):
        return f"<Driver(id={self.id}, name='{self.first_name} {self.last_name}', active={self.is_active})>"

class Vehicle(Base):
    __tablename__ = 'vehicles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    license_plate = Column(String(15), nullable=False, unique=True)
    make = Column(String(50), nullable=True)
    model = Column(String(50), nullable=True)
    year = Column(Integer, nullable=True)
    capacity_passengers = Column(Integer, nullable=False, default=4)
    capacity_bags = Column(Integer, nullable=True, default=3)
    status = Column(String(50), default='ACTIVE', nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Vehicle(id={self.id}, plate='{self.license_plate}', make='{self.make}', model='{self.model}')>"

class TariffSettings(Base):
    __tablename__ = 'tariff_settings'
    id = Column(Integer, primary_key=True, default=1)
    base_rate_eur = Column(Float, nullable=False, default=10.0)
    rate_per_km_eur = Column(Float, nullable=False, default=0.85)
    rate_per_passenger_eur = Column(Float, nullable=False, default=2.5)
    rate_per_bag_eur = Column(Float, nullable=False, default=1.0)
    night_surcharge_applies = Column(Boolean, default=True)
    night_surcharge_percentage = Column(Float, nullable=False, default=20.0)
    night_surcharge_start_hour = Column(Integer, nullable=False, default=22)
    night_surcharge_end_hour = Column(Integer, nullable=False, default=6)
    booking_slot_overlap_minutes = Column(Integer, nullable=False, default=30)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<TariffSettings(id={self.id}, base_rate={self.base_rate_eur})>"

class Voucher(Base):
    __tablename__ = 'vouchers'
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    discount_type = Column(String(20), nullable=False)
    discount_value = Column(Float, nullable=False)
    expiration_date = Column(Date, nullable=True)
    max_uses = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    min_booking_value = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Voucher(id={self.id}, code='{self.code}', type='{self.discount_type}', active={self.is_active})>"

class Booking(Base):
    __tablename__ = 'bookings'
    id = Column(Integer, primary_key=True, autoincrement=True)
    passenger_name = Column(String(100), nullable=False)
    passenger_phone = Column(String(20), nullable=True)
    date = Column(Date, nullable=False)
    time = Column(Time, nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    pickup_location = Column(String(255), nullable=False)
    dropoff_location = Column(String(255), nullable=False)
    passengers = Column(Integer, nullable=False)
    bags = Column(Integer, nullable=True, default=0)
    instructions = Column(String(500), nullable=True)
    original_budget_pre_vat = Column(Float, nullable=True)
    discount_amount = Column(Float, nullable=True)
    final_budget_pre_vat = Column(Float, nullable=True)
    vat_percentage = Column(Float, nullable=True)
    vat_amount = Column(Float, nullable=True)
    total_with_vat = Column(Float, nullable=False)
    applied_voucher_code = Column(String(50), nullable=True)
    status = Column(String(50), default='PENDING_CONFIRMATION')
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    assigned_driver_id = Column(Integer, ForeignKey('drivers.id'), nullable=True)
    assigned_driver = relationship("Driver", back_populates="bookings")

    def __repr__(self):
        driver_name = self.assigned_driver.first_name if self.assigned_driver else "N/A"
        return f"<Booking(id={self.id}, name='{self.passenger_name}', date='{self.date}', total='{self.total_with_vat}')>"


def init_db_engine_with_context(app_instance):
    """
    Inicializa a base de dados e cria tabelas se não existirem.
    """
    try:
        db.create_all()
        app_instance.logger.info(f"Base de dados verificada/tabelas criadas em {app_instance.config.get('DATABASE_URI')}")

        existing_settings = db.session.query(TariffSettings).filter(TariffSettings.id == 1).first()
        if not existing_settings:
            app_instance.logger.info("Nenhuma config. tarifa (id=1). A criar padrão...")
            try:
                default_settings = TariffSettings(
                    id=1,
                    base_rate_eur=current_app.config.get('BASE_RATE_EUR', 10.0),
                    rate_per_km_eur=current_app.config.get('RATE_PER_KM_EUR', 0.85),
                    rate_per_passenger_eur=current_app.config.get('RATE_PER_PASSENGER_EUR', 2.5),
                    rate_per_bag_eur=current_app.config.get('RATE_PER_BAG_EUR', 1.0),
                    night_surcharge_applies=current_app.config.get('NIGHT_SURCHARGE_APPLIES', True),
                    night_surcharge_percentage=current_app.config.get('NIGHT_SURCHARGE_PERCENTAGE', 20.0),
                    night_surcharge_start_hour=current_app.config.get('NIGHT_SURCHARGE_START_HOUR', 22),
                    night_surcharge_end_hour=current_app.config.get('NIGHT_SURCHARGE_END_HOUR', 6),
                    booking_slot_overlap_minutes=current_app.config.get('BOOKING_SLOT_OVERLAP_MINUTES', 30)
                )
                db.session.add(default_settings)
                db.session.commit()
                app_instance.logger.info("Config. tarifa padrão criada com sucesso.")
            except IntegrityError:
                db.session.rollback()
                app_instance.logger.warning("Erro de integridade ao criar config. tarifa padrão (provavelmente já existe). Ignorando.")
            except Exception as seed_error:
                db.session.rollback()
                app_instance.logger.error(f"Erro inesperado ao criar config. tarifa padrão: {seed_error}", exc_info=True)
    except Exception as e:
        app_instance.logger.error(f"Erro durante init_db_engine_with_context: {e}", exc_info=True)

