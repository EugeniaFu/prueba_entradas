import mysql.connector
from flask import current_app

def get_db_connection():
    """
    Obtiene una conexión a la base de datos usando la configuración centralizada
    con zona horaria configurada para Campeche (CST)
    """
    try:
        # Intentar usar la configuración de Flask si está disponible
        if current_app:
            db_config = current_app.config['DB_CONFIG']
        else:
            # Fallback: importar configuración directamente
            from config import Config
            db_config = Config.DB_CONFIG
            
        connection = mysql.connector.connect(**db_config)
        
        # Verificar y establecer zona horaria si no está configurada
        cursor = connection.cursor()
        cursor.execute("SET time_zone = '-06:00'")
        cursor.close()
        
        return connection
    except Exception as e:
        # Si falla, usar configuración directa (para compatibilidad)
        print(f"Warning: Using fallback DB connection. Error: {e}")
        connection = mysql.connector.connect(
            host='database-1.cf0ey64ia6yt.us-east-2.rds.amazonaws.com',
            user='admin',
            password='12345678',
            database='andamiosdb',
            charset='utf8mb4',
            autocommit=True,
            time_zone='-06:00'  # Zona horaria de Campeche (CST)
        )
        
        # Asegurar zona horaria también en fallback
        cursor = connection.cursor()
        cursor.execute("SET time_zone = '-06:00'")
        cursor.close()
        
        return connection