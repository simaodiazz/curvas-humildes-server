import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
)

import datetime
from app.db import Model as Base


class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    license_plate = Column(String(15), nullable=False, unique=True)
    make = Column(String(50), nullable=True)
    model = Column(String(50), nullable=True)
    year = Column(Integer, nullable=True)
    capacity_passengers = Column(Integer, nullable=False, default=4)
    capacity_bags = Column(Integer, nullable=True, default=3)
    status = Column(String(50), default="ACTIVE", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Vehicle(id={self.id}, plate='{self.license_plate}', make='{self.make}', model='{self.model}')>"
