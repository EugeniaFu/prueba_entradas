import os
import threading
import mysql.connector
from mysql.connector import pooling
from flask import current_app
from dotenv import load_dotenv

load_dotenv()

_pool = None
_pool_lock = threading.Lock()


def _build_db_config():
    # Si existe contexto de Flask, usar su configuración
    if current_app:
        db_config = dict(current_app.config.get('DB_CONFIG') or {})
    else:
        # Construir configuración directamente desde variables de entorno
        db_config = {
            'host': os.getenv('DB_HOST'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'database': os.getenv('DB_NAME'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'charset': 'utf8mb4',
            'autocommit': True,
            'time_zone': '-06:00'
        }
    return db_config


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                db_config = _build_db_config()
                _pool = pooling.MySQLConnectionPool(
                    pool_name='app_pool',
                    pool_size=10,
                    pool_reset_session=True,
                    **db_config
                )
    return _pool


def get_db_connection():
    """
    Obtiene una conexión a la base de datos desde un pool de conexiones
    (evita el costo de abrir una conexión TCP + autenticación nueva en cada
    consulta) con zona horaria configurada para México Central (CST)
    """
    try:
        connection = _get_pool().get_connection()

        # Asegurar zona horaria (por si la sesión se reseteó al volver al pool)
        cursor = connection.cursor()
        cursor.execute("SET time_zone = '-06:00'")
        cursor.close()

        return connection

    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        raise