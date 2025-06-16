from ..models.user import User
from ..db import sqlAlchemy as db

def create_user(name, email, phone_number, password, role):
    user = User()
    user.name = name
    user.email = email
    user.phone_number = phone_number
    user.role = role
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user

def get_all_users():
    return User.query.order_by(User.id).all()

def get_user_by_id(user_id):
    return User.query.filter_by(id=user_id).first()

def get_user_by_name(name):
    return User.query.filter_by(name=name).first()

def update_user(user_id, **kwargs):
    user = get_user_by_id(user_id)
    if not user:
        return None
    for field in ("name", "role", "email", "phone_number"):
        if field in kwargs and kwargs[field]:
            setattr(user, field, kwargs[field])
    db.session.commit()
    return user

def set_user_password(user_id, new_password):
    user = get_user_by_id(user_id)
    if not user:
        return None
    user.set_password(new_password)
    db.session.commit()
    return user

def delete_user(user_id):
    user = get_user_by_id(user_id)
    if not user:
        return False
    db.session.delete(user)
    db.session.commit()
    return True