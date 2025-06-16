"""Serviço para operações de motoristas e veículos, com Flask-Caching."""
import datetime
from logging import getLogger
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from ..db import sqlAlchemy
from ..models.driver import Driver
from ..models.vehicle import Vehicle

logger = getLogger(__name__)


def make_driver_cache_key(driver_id):
    return f"driver:{driver_id}"


def make_all_drivers_cache_key(only_active):
    return f"drivers:all:{only_active}"


def make_vehicle_cache_key(vehicle_id):
    return f"vehicle:{vehicle_id}"


def make_all_vehicles_cache_key(status_filter):
    return f"vehicles:all:{status_filter or 'ANY'}"


def create_driver(driver_data: dict) -> Driver:
    """Cria um novo motorista."""
    try:
        first_name = str(driver_data.get("first_name", "")).strip()
        last_name = str(driver_data.get("last_name", "")).strip()
        if not first_name:
            raise ValueError("Nome próprio do motorista é obrigatório.")
        if not last_name:
            raise ValueError("Apelido do motorista é obrigatório.")
        email = driver_data.get("email")
        email = str(email).strip().lower() if email and str(email).strip() else None
        phone_number = driver_data.get("phone_number")
        phone_number = (
            str(phone_number).strip()
            if phone_number and str(phone_number).strip()
            else None
        )
        new_driver = Driver(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            is_active=driver_data.get("is_active", True),
        )
        sqlAlchemy.session.add(new_driver)
        sqlAlchemy.session.commit()
        sqlAlchemy.session.refresh(new_driver)
        return new_driver
    except IntegrityError as exc:
        sqlAlchemy.session.rollback()
        raise ValueError(
            "Email '%s' já está registado para outro motorista." % email
        ) from exc
    except ValueError as ve:
        sqlAlchemy.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error("Erro de BD ao criar motorista: %s", e, exc_info=True)
        raise ValueError("Erro de base de dados ao criar motorista.") from e
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error("Erro inesperado ao criar motorista: %s", e_unexp, exc_info=True)
        raise ValueError("Erro inesperado ao criar motorista.") from e_unexp


def get_driver_by_id(driver_id: int):
    """Busca um motorista por ID."""
    try:
        driver = sqlAlchemy.session.query(Driver).filter(Driver.id == driver_id).first()
        return driver
    except SQLAlchemyError as e:
        logger.error(
            "Erro de BD ao obter motorista por ID %s: %s", driver_id, e, exc_info=True
        )
        raise ValueError("Erro de BD ao obter motorista ID %s." % driver_id) from e


def get_all_drivers(only_active: bool = False) -> list[Driver]:
    """Retorna todos os motoristas."""
    try:
        query = sqlAlchemy.session.query(Driver)
        if only_active:
            query = query.filter(Driver.is_active.is_(True))
        result = query.order_by(Driver.last_name, Driver.first_name).all()
        return result
    except SQLAlchemyError as e:
        logger.error("Erro de BD ao obter todos os motoristas: %s", e, exc_info=True)
        raise ValueError("Erro de BD ao obter todos os motoristas.") from e


def update_driver(driver_id: int, driver_data: dict):
    """Atualiza dados de um motorista."""
    try:
        driver_to_update = get_driver_by_id(driver_id)
        if not driver_to_update:
            return None
        updated = False
        if "first_name" in driver_data and str(driver_data["first_name"]).strip():
            driver_to_update.first_name = str(driver_data["first_name"]).strip()
            updated = True
        if "last_name" in driver_data and str(driver_data["last_name"]).strip():
            driver_to_update.last_name = str(driver_data["last_name"]).strip()
            updated = True
        if "email" in driver_data:
            email_val = driver_data["email"]
            driver_to_update.email = (
                str(email_val).strip().lower()
                if email_val and str(email_val).strip()
                else None
            )
            updated = True
        if "phone_number" in driver_data:
            phone_val = driver_data["phone_number"]
            driver_to_update.phone_number = (
                str(phone_val).strip() if phone_val and str(phone_val).strip() else None
            )
            updated = True
        if "is_active" in driver_data and isinstance(driver_data["is_active"], bool):
            driver_to_update.is_active = driver_data["is_active"]
            updated = True
        if not updated:
            return driver_to_update
        sqlAlchemy.session.commit()
        sqlAlchemy.session.refresh(driver_to_update)
        return driver_to_update
    except IntegrityError as exc:
        sqlAlchemy.session.rollback()
        raise ValueError(
            "Email fornecido já está registado para outro motorista."
        ) from exc
    except ValueError as ve:
        sqlAlchemy.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro de BD ao atualizar motorista %s: %s", driver_id, e, exc_info=True
        )
        raise ValueError("Erro de base de dados ao atualizar motorista.") from e
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro inesperado ao atualizar motorista %s: %s",
            driver_id,
            e_unexp,
            exc_info=True,
        )
        raise ValueError("Erro inesperado ao atualizar motorista.") from e_unexp


def delete_driver_by_id(driver_id: int) -> bool:
    """Remove um motorista por ID."""
    try:
        driver_to_delete = get_driver_by_id(driver_id)
        if driver_to_delete:
            if getattr(driver_to_delete, "bookings", None):
                raise ValueError(
                    "Não é possível excluir o motorista ID %s pois está associado a reservas."
                    % driver_id
                )
            sqlAlchemy.session.delete(driver_to_delete)
            sqlAlchemy.session.commit()
            return True
        return False
    except ValueError as ve:
        sqlAlchemy.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro de BD ao excluir motorista %s: %s", driver_id, e, exc_info=True
        )
        if "FOREIGN KEY constraint failed" in str(e).lower():
            raise ValueError(
                "Não é possível excluir o motorista ID %s pois está associado a reservas (FK)."
                % driver_id
            ) from e
        raise ValueError("Erro de BD ao excluir motorista.") from e
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro inesperado ao excluir motorista %s: %s",
            driver_id,
            e_unexp,
            exc_info=True,
        )
        raise ValueError("Erro inesperado ao excluir motorista.") from e_unexp


# --- CRUD Veículos ---


def create_vehicle(vehicle_data: dict) -> Vehicle:
    """Cria um novo veículo."""
    try:
        license_plate = str(vehicle_data.get("license_plate", "")).strip().upper()
        if not license_plate:
            raise ValueError("Matrícula do veículo é obrigatória.")
        capacity_passengers_str = vehicle_data.get("capacity_passengers")
        capacity_passengers = (
            int(capacity_passengers_str) if capacity_passengers_str is not None else 4
        )
        if capacity_passengers < 1:
            raise ValueError("Capacidade de passageiros deve ser >= 1.")
        capacity_bags_str = vehicle_data.get("capacity_bags")
        capacity_bags = int(capacity_bags_str) if capacity_bags_str is not None else 3
        if capacity_bags < 0:
            raise ValueError("Capacidade de malas deve ser >= 0.")
        year_str = vehicle_data.get("year")
        year = int(year_str) if year_str and str(year_str).strip() else None
        if year is not None and not 1900 <= year <= datetime.date.today().year + 2:
            raise ValueError(f"Ano do veículo inválido: {year}.")
        new_vehicle = Vehicle(
            license_plate=license_plate,
            make=vehicle_data.get("make"),
            model=vehicle_data.get("model"),
            year=year,
            capacity_passengers=capacity_passengers,
            capacity_bags=capacity_bags,
            status=str(vehicle_data.get("status", "ACTIVE")).upper(),
        )
        sqlAlchemy.session.add(new_vehicle)
        sqlAlchemy.session.commit()
        sqlAlchemy.session.refresh(new_vehicle)
        return new_vehicle
    except IntegrityError as exc:
        sqlAlchemy.session.rollback()
        raise ValueError(
            "Veículo com a matrícula '%s' já existe." % license_plate
        ) from exc
    except ValueError as ve:
        sqlAlchemy.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error("Erro de BD ao criar veículo: %s", e, exc_info=True)
        raise ValueError("Erro de base de dados ao criar veículo.") from e
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error("Erro inesperado ao criar veículo: %s", e_unexp, exc_info=True)
        raise ValueError("Erro inesperado ao criar veículo.") from e_unexp


def get_vehicle_by_id(vehicle_id: int):
    try:
        vehicle = (
            sqlAlchemy.session.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
        )
        return vehicle
    except SQLAlchemyError as e:
        logger.error(
            "Erro de BD ao obter veículo por ID %s: %s", vehicle_id, e, exc_info=True
        )
        raise ValueError("Erro de BD ao obter veículo ID %s." % vehicle_id) from e


def get_all_vehicles(status_filter: str):
    try:
        query = sqlAlchemy.session.query(Vehicle)
        if status_filter and status_filter.strip():
            query = query.filter(Vehicle.status == status_filter.strip().upper())
        result = query.order_by(
            Vehicle.make, Vehicle.model, Vehicle.license_plate
        ).all()
        return result
    except SQLAlchemyError as e:
        logger.error("Erro de BD ao obter todos os veículos: %s", e, exc_info=True)
        raise ValueError("Erro de BD ao obter todos os veículos.") from e


def update_vehicle(vehicle_id: int, vehicle_data: dict):
    """Atualiza dados de um veículo."""
    try:
        vehicle_to_update = get_vehicle_by_id(vehicle_id)
        if not vehicle_to_update:
            return None
        updated = False
        if (
            "license_plate" in vehicle_data
            and str(vehicle_data["license_plate"]).strip()
        ):
            lp = str(vehicle_data["license_plate"]).strip().upper()
            if not lp:
                raise ValueError("Matrícula não pode ser vazia.")
            vehicle_to_update.license_plate = lp
            updated = True
        if "make" in vehicle_data:
            vehicle_to_update.make = (
                vehicle_data["make"]
                if vehicle_data["make"] and str(vehicle_data["make"]).strip()
                else None
            )
            updated = True
        if "model" in vehicle_data:
            vehicle_to_update.model = (
                vehicle_data["model"]
                if vehicle_data["model"] and str(vehicle_data["model"]).strip()
                else None
            )
            updated = True
        if "year" in vehicle_data:
            year_str = vehicle_data["year"]
            if year_str and str(year_str).strip():
                year_val = int(year_str)
                if not 1900 <= year_val <= datetime.date.today().year + 2:
                    raise ValueError(f"Ano do veículo inválido: {year_val}.")
                vehicle_to_update.year = year_val
            else:
                vehicle_to_update.year = None
            updated = True
        if (
            "capacity_passengers" in vehicle_data
            and vehicle_data["capacity_passengers"] is not None
        ):
            cap_pass = int(vehicle_data["capacity_passengers"])
            if cap_pass < 1:
                raise ValueError("Capacidade de passageiros deve ser >= 1.")
            vehicle_to_update.capacity_passengers = cap_pass
            updated = True
        if "capacity_bags" in vehicle_data:
            cap_bags_str = vehicle_data["capacity_bags"]
            if cap_bags_str is not None and str(cap_bags_str).strip() != "":
                cap_bags = int(cap_bags_str)
                if cap_bags < 0:
                    raise ValueError("Capacidade de malas deve ser >= 0.")
                vehicle_to_update.capacity_bags = cap_bags
            else:
                vehicle_to_update.capacity_bags = None
            updated = True
        if "status" in vehicle_data and str(vehicle_data["status"]).strip():
            status_val = str(vehicle_data["status"]).strip().upper()
            vehicle_to_update.status = status_val
            updated = True
        if not updated:
            return vehicle_to_update
        sqlAlchemy.session.commit()
        sqlAlchemy.session.refresh(vehicle_to_update)
        return vehicle_to_update
    except IntegrityError as exc:
        sqlAlchemy.session.rollback()
        raise ValueError(
            "Matrícula fornecida já está registada para outro veículo."
        ) from exc
    except ValueError as ve:
        sqlAlchemy.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro de BD ao atualizar veículo %s: %s", vehicle_id, e, exc_info=True
        )
        raise ValueError("Erro de base de dados ao atualizar veículo.") from e
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro inesperado ao atualizar veículo %s: %s",
            vehicle_id,
            e_unexp,
            exc_info=True,
        )
        raise ValueError("Erro inesperado ao atualizar veículo.") from e_unexp


def delete_vehicle_by_id(vehicle_id: int) -> bool:
    """Remove veículo por ID."""
    try:
        vehicle_to_delete = get_vehicle_by_id(vehicle_id)
        if vehicle_to_delete:
            sqlAlchemy.session.delete(vehicle_to_delete)
            sqlAlchemy.session.commit()
            return True
        return False
    except ValueError as ve:
        sqlAlchemy.session.rollback()
        raise ve
    except SQLAlchemyError as e:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro de BD ao excluir veículo %s: %s", vehicle_id, e, exc_info=True
        )
        if "FOREIGN KEY constraint failed" in str(e).lower():
            raise ValueError(
                "Veículo não pode ser excluído pois está associado a outros registos (ex: reservas)."
            ) from e
        raise ValueError("Erro de BD ao excluir veículo.") from e
    except Exception as e_unexp:
        sqlAlchemy.session.rollback()
        logger.error(
            "Erro inesperado ao excluir veículo %s: %s",
            vehicle_id,
            e_unexp,
            exc_info=True,
        )
        raise ValueError("Erro inesperado ao excluir veículo.") from e_unexp
