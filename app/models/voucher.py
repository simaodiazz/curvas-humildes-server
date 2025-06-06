from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    Time,
    DateTime,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from .entity import Entity
import datetime


class Voucher(Entity):
    __tablename__ = "vouchers"
    code = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    discount_type = Column(String(20), nullable=False)
    discount_value = Column(Float, nullable=False)
    expiration_date = Column(Date, nullable=True)
    max_uses = Column(Integer, default=1)
    current_uses = Column(Integer, default=0)
    min_booking_value = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<Voucher(id={self.id}, code='{self.code}', type='{self.discount_type}', active={self.is_active})>"
