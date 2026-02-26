import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Configuración básica de Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'clave-secreta-cambiar-en-produccion'
    
    # Configuración de SQLAlchemy
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuración de Base de Datos (para mysql-connector-python directo)
    DB_CONFIG = {
        'host': os.getenv('DB_HOST'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'database': os.getenv('DB_NAME'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'charset': 'utf8mb4',
        'autocommit': True,
        'time_zone': '-06:00' # Zona horaria de México Central/Camp (CST)
    }
    
    # Configuración de correo electrónico
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'alejandralopeez2003@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'qamz lgmm lsby bcko'
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'alejandralopeez2003@gmail.com'
    
    # Configuración de desarrollo/producción
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() in ['true', 'on', '1']
    ENV = os.environ.get('FLASK_ENV', 'development')
    
    # Configuración de seguridad
    SHOW_RESET_LINKS_ON_ERROR = False  # Por defecto NO mostrar enlaces en errores
    
class DevelopmentConfig(Config):
    DEBUG = True
    ENV = 'development'
    SHOW_RESET_LINKS_ON_ERROR = True  # Solo en desarrollo mostrar enlaces
    
class ProductionConfig(Config):
    DEBUG = False
    ENV = 'production'
    SHOW_RESET_LINKS_ON_ERROR = False  # NUNCA en producción
    # En producción, asegúrate de usar variables de entorno para datos sensibles
    
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}