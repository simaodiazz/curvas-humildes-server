import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
)

import datetime
from app.db import Model as Base


class TariffSettings(Base):
    __tablename__ = "tariff_settings"
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
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    def __repr__(self):
        return f"<TariffSettings(id={self.id}, base_rate={self.base_rate_eur})>"
