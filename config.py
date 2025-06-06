# CurvasSistema/config_main.py
import os

# --- Configurações Gerais da Aplicação Flask ---
DEBUG = True
PORT = 5001
HOST = '0.0.0.0'
SECRET_KEY = os.environ.get('SECRET_KEY', 'uma_chave_secreta_default_para_desenvolvimento_muito_longa_e_aleatoria')

SQLALCHEMY_DATABASE_URI = f"sqlite:///data.db"

# --- API de Mapas ---
MAPS_API_PROVIDER = "OPENROUTESERVICE"

# --- Configurações de Tarifas Padrão ---
BASE_RATE_EUR = 10.0
RATE_PER_KM_EUR = 0.85
RATE_PER_PASSENGER_EUR = 2.5
RATE_PER_BAG_EUR = 1.0
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

# --- Taxa de IVA ---
VAT_RATE = 23.0

# --- Status Possíveis para Reservas ---
ALLOWED_BOOKING_STATUSES = [
    'PENDING_CONFIRMATION', 'CONFIRMED', 'DRIVER_ASSIGNED', 'ON_ROUTE_PICKUP',
    'PASSENGER_ON_BOARD', 'COMPLETED', 'CANCELED_BY_CLIENT', 'CANCELED_BY_ADMIN', 'NO_SHOW'
]

# --- Configurações de Email (Flask-Mail) ---
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'mail.curvashumildes.pt')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 465))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1', 't']
MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', '1', 't'] 
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'geral@curvashumildes.pt') 
MAIL_DEFAULT_SENDER = ('Curvas Humildes', os.environ.get('MAIL_DEFAULT_SENDER_EMAIL', 'geral@curvashumildes.pt'))

ADMIN_EMAIL_RECIPIENTS = ['geral.helder.fernandes@gmail.com', 'curvashumildes@gmail.com']
