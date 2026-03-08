import os
import mysql.connector
from flask import current_app
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """
    Obtiene una conexión a la base de datos usando variables de entorno
    con zona horaria configurada para México Central (CST)
    """
    try:
        # Si existe contexto de Flask, usar su configuración
        if current_app:
            db_config = current_app.config.get('DB_CONFIG')
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

        connection = mysql.connector.connect(**db_config)

        # Asegurar zona horaria
        cursor = connection.cursor()
        cursor.execute("SET time_zone = '-06:00'")
        cursor.close()

        return connection

    except Exception as e:
        print(f"Error al conectar a la base de datos: {e}")
        raise