import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
)

import datetime
from app.db import Model as Base
from werkzeug.security import generate_password_hash, check_password_hash


class User(Base):
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    password = Column(String(128), nullable=False)
    role = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def has_role(self, role):
        return role == self.role
