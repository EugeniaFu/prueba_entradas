# Front Controller - Punto de entrada principal del sistema
from flask import Flask, render_template, redirect, url_for
from flask_mail import Mail
import os

# Traer la configuración desde otro archivo
from config import config

# Traer todos los módulos que manejan diferentes partes del sistema
from routes.login import login_bp
from routes.dashboard import dashboard_bp
from routes.clientes import clientes_bp
from routes.inventario import bp_inventario
from routes.producto import bp_producto
from routes.empleados import empleados_bp
from routes.usuarios import usuarios_bp
from routes.cotizaciones import cotizaciones_bp
from routes.rentas import rentas_bp
from routes.salidas_internas import salidas_internas_bp
from routes.notas_entrada import notas_entrada_bp
from routes.notas_salida import notas_salida_bp
from routes.prefactura import prefactura_bp
from routes.cobros_extra import bp_extras
from routes.cobro_retraso import cobro_retraso_bp
from routes.caja import caja_bp
from routes.reportes import reportes_bp
from routes.sucursales import sucursales_bp
from routes.roles import roles_bp
from utils.permisos_sync import inicializar_permisos

# Función que arma toda la aplicación
def create_app(config_name='default'):
    # Crear la app principal
    app = Flask(__name__)
    
    # Aplicar la configuración que queremos usar
    app.config.from_object(config[config_name])
    
    # Activar el sistema de correos
    mail = Mail(app)
    
    # Función que convierte estados en colores para las plantillas
    @app.template_filter('estado_color')
    def estado_color(estado):
        colores = {
            'activa': 'success',
            'programada': 'primary',
            'finalizada': 'secondary',
            'cancelada': 'danger',
            'renovada': 'info',
            'parcialmente devuelta': 'warning'
        }
        return colores.get(estado, 'dark')

    # Inyectar las sucursales globalmente en todas las vistas
    @app.context_processor
    def inject_sucursales():
        from utils.db import get_db_connection
        sucursales = []
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute("SELECT id, nombre FROM sucursales WHERE activo = 1")
            except Exception:
                cursor.execute("SELECT id, nombre FROM sucursales")
            sucursales = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception as e:
            pass
        return dict(list_sucursales=sucursales)
    
    # Conectar todos los módulos a la aplicación principal
    # Cada módulo maneja su propia parte del sistema
    app.register_blueprint(login_bp)           # Maneja login y autenticación
    app.register_blueprint(dashboard_bp)       # Maneja el tablero principal
    app.register_blueprint(clientes_bp)        # Maneja todo de clientes
    app.register_blueprint(bp_inventario)      # Maneja inventario y almacén
    app.register_blueprint(bp_producto)        # Maneja productos y piezas
    app.register_blueprint(empleados_bp)       # Maneja empleados
    app.register_blueprint(usuarios_bp)        # Maneja usuarios del sistema
    app.register_blueprint(cotizaciones_bp)    # Maneja cotizaciones
    app.register_blueprint(rentas_bp)          # Maneja rentas de equipo
    app.register_blueprint(salidas_internas_bp)# Maneja movimientos internos
    app.register_blueprint(notas_entrada_bp)   # Maneja devoluciones de equipo
    app.register_blueprint(notas_salida_bp)    # Maneja entregas de equipo
    app.register_blueprint(prefactura_bp)      # Maneja facturación
    app.register_blueprint(bp_extras)          # Maneja cobros extra
    app.register_blueprint(cobro_retraso_bp)   # Maneja cobros por retraso
    app.register_blueprint(caja_bp)            # Maneja caja y dinero
    app.register_blueprint(reportes_bp)        # Maneja reportes y estadísticas
    app.register_blueprint(sucursales_bp)      # Maneja el CRUD de sucursales
    app.register_blueprint(roles_bp)           # Maneja el panel RBAC de Roles y Permisos
    
    # Página de inicio - redirige al login
    @app.route('/')
    def home():
        return redirect(url_for('login.login'))
    
    # Devolver la aplicación ya armada
    
    # ----------------------------------------------------
    # Sincronización Automática de Permisos
    # Cada vez que inicie el servidor, verificará si hay
    # permisos nuevos en el código que falten en la BD
    # ----------------------------------------------------
    with app.app_context():
        inicializar_permisos()
        
    return app

# Crear la aplicación usando la función de arriba
app = create_app(os.getenv('FLASK_ENV', 'default'))

# Si ejecutamos este archivo directamente, arrancar el servidor
if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])