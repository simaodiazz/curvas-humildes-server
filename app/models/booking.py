import datetime
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Time,
)
from sqlalchemy.orm import relationship
import datetime
from app.db import Model as Base


class Booking(Base):
    __tablename__ = "bookings"  # <--- Corrige para __tablename__

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
    status = Column(String(50), default="PENDING_CONFIRMATION")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    assigned_driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    assigned_driver = relationship("Driver", back_populates="bookings")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user = relationship("User", back_populates="bookings")

    def __repr__(self):
        driver_name = self.assigned_driver.first_name if self.assigned_driver else "N/A"
        return f"<Booking(id={self.id}, name='{self.passenger_name}', date='{self.date}', total='{self.total_with_vat}')>"