import os

class Configuration:
    DEBUG = False
    TESTING = False

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "uma_chave_secreta_default_para_desenvolvimento_muito_longa_e_aleatoria"
    )

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "mysql+pymysql://root:simaopks009@localhost:3306/db")
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAPS_API_PROVIDER = os.environ.get("MAPS_API_PROVIDER", "OPENROUTESERVICE")
    MAPS_API_KEY = os.environ.get("MAPS_API_KEY", "")
    VAT_RATE = 23.0
    
    BASE_RATE_EUR = float(os.environ.get("BASE_RATE_EUR", 10.0))
    RATE_PER_KM_EUR = float(os.environ.get("RATE_PER_KM_EUR", 0.85))
    RATE_PER_PASSENGER_EUR = float(os.environ.get("RATE_PER_PASSENGER_EUR", 2.5))
    RATE_PER_BAG_EUR = float(os.environ.get("RATE_PER_BAG_EUR", 1.0))

    PREDEFINED_ROUTES = {
        "aeroporto lisboa#centro cidade lisboa": 30.0,
        "aeroporto lisboa#parque das nacoes": 20.0,
        "aeroporto lisboa#cascais": 55.0,
        "gare do oriente#baixa lisboa": 18.0,
        "sintra#aeroporto lisboa": 45.0,
    }

    NIGHT_SURCHARGE_APPLIES = True
    NIGHT_SURCHARGE_PERCENTAGE = 20.0
    NIGHT_SURCHARGE_START_HOUR = 22
    NIGHT_SURCHARGE_END_HOUR = 6
    BOOKING_SLOT_OVERLAP_MINUTES = 30

    ALLOWED_BOOKING_STATUSES = [
        "PENDING_CONFIRMATION",
        "CONFIRMED",
        "DRIVER_ASSIGNED",
        "ON_ROUTE_PICKUP",
        "PASSENGER_ON_BOARD",
        "COMPLETED",
        "CANCELED_BY_CLIENT",
        "CANCELED_BY_ADMIN",
        "NO_SHOW",
    ]

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "mail.curvashumildes.pt")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 465))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ["true", "1", "t"]
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() in ["true", "1", "t"]
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "geral@curvashumildes.pt")
    MAIL_DEFAULT_SENDER = (
        "Curvas Humildes",
        os.environ.get("MAIL_DEFAULT_SENDER_EMAIL", "geral@curvashumildes.pt"),
    )

    ADMIN_EMAIL_RECIPIENTS = [
        "geral.helder.fernandes@gmail.com",
        "curvashumildes@gmail.com",
    ]

    CACHE_TYPE = os.environ.get("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", 300))

    HOST = os.environ.get("HOST", "0.0.0.0")
    PORT = int(os.environ.get("PORT", 5002))

    JWT_TOKEN_LOCATION = os.environ.get("JWT_TOKEN_LOCATION", "cookies")
    JWT_ACCESS_COOKIE_NAME = os.environ.get("JWT_ACCESS_COOKIE_NAME", "access_token")
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_SECRET_KEY = os.environ.get(
        "JWT_SECRET_KEY",
        "uma_chave_secreta_default_para_desenvolvimento_muito_longa_e_aleatoria"
    )

    ADMINSTRATOR_NAME = os.environ.get("ADMINISTRATOR_NAME", "Helder Fernandes")
    ADMINSTRATOR_EMAIL = os.environ.get("ADMINISTRATOR_EMAIL" , "geral@curvashumildes.pt")
    ADMINSTRATOR_PHONE_NUMBER = os.environ.get("ADMINISTRATOR_PHONE_NUMBER", "+351 962 345 438")
    ADMINSTRATOR_PASSWORD = os.environ.get("ADMINISTRATOR_PASSWORD", "123456") # Conta de admistração.

class Development(Configuration):
    DEBUG = True # Hot reload
    ENV = "development"


class Production(Configuration):
    DEBUG = False
    ENV = "production"


class Testing(Configuration):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
