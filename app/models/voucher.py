from sqlalchemy import Boolean, Column, Date, Float, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import datetime
from ..db import Model as Base

class Voucher(Base):
    __tablename__ = "vouchers"
    
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
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    user = relationship('User', back_populates='vouchers')

    def __repr__(self):
        return f"<Voucher(id={self.id}, code='{self.code}', type='{self.discount_type}', active={self.is_active})>"
