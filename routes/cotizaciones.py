from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from utils.db import get_db_connection
from datetime import datetime, timedelta
import json
from utils.datetime_utils import get_local_now
from utils.decorators import requiere_sesion, requiere_permiso

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from flask import send_file, current_app
from io import BytesIO
import os




cotizaciones_bp = Blueprint('cotizaciones', __name__, url_prefix='/cotizaciones')

# Definir los estados de cotización
ESTADOS_COTIZACION = {
    'ENVIADA': 'enviada',
    'VENCIDA': 'vencida',
    'RENTA': 'renta'
}

def generar_numero_cotizacion():
    """Genera un número único de cotización"""
    conexion = get_db_connection()
    cursor = conexion.cursor()
    
    # Obtener el año actual
    año_actual = get_local_now().year
    
    # Buscar el último número de cotización del año
    cursor.execute("""
        SELECT numero_cotizacion 
        FROM cotizaciones 
        WHERE numero_cotizacion LIKE %s 
        ORDER BY id DESC 
        LIMIT 1
    """, (f"{año_actual}%",))
    
    resultado = cursor.fetchone()
    
    if resultado:
        ultimo_numero = int(resultado[0].split('-')[1])
        nuevo_numero = ultimo_numero + 1
    else:
        nuevo_numero = 1
    
    cursor.close()
    conexion.close()
    
    return f"{año_actual}-{nuevo_numero:04d}"





def verificar_cotizaciones_vencidas():
    """Actualiza automáticamente las cotizaciones vencidas"""
    conexion = get_db_connection()
    cursor = conexion.cursor()
    
    try:
        # Marcar como vencidas las cotizaciones que pasaron los 7 días
        cursor.execute("""
            UPDATE cotizaciones 
            SET estado = 'vencida' 
            WHERE estado = 'enviada' 
            AND fecha_vigencia < CURDATE()
        """)
        
        conexion.commit()
        print(f"Cotizaciones vencidas actualizadas: {cursor.rowcount}")
        
    except Exception as e:
        print(f"Error al actualizar cotizaciones vencidas: {e}")
        conexion.rollback()
    finally:
        cursor.close()
        conexion.close()





def calcular_estado_vigencia(cotizacion):
    """Calcula el estado de vigencia de una cotización (similar a rentas)"""
    
    # Solo mostrar indicadores para cotizaciones ENVIADAS
    if cotizacion['estado'] != 'enviada':
        return None
    
    # Si no tiene fecha de vigencia, no mostrar indicador
    if not cotizacion['fecha_vigencia']:
        return None
    
    fecha_vigencia = cotizacion['fecha_vigencia']
    dias_para_vencer = cotizacion['dias_para_vencer']
    ahora = get_local_now()
    
    # Si ya pasó la fecha de vigencia = VENCIDA
    if dias_para_vencer is not None and dias_para_vencer <= 0:
        return {
            'estado': 'vencida',
            'clase': 'bg-danger',
            'texto': 'Vencida'
        }
    
    # Si le quedan 3 días o menos = POR VENCER
    elif dias_para_vencer is not None and dias_para_vencer <= 3:
        return {
            'estado': 'por_vencer',
            'clase': 'bg-warning',
            'texto': f'Vence en {dias_para_vencer} día{"s" if dias_para_vencer != 1 else ""}'
        }
    
    # Si le quedan más de 3 días = VIGENTE
    elif dias_para_vencer is not None and dias_para_vencer > 3:
        return {
            'estado': 'vigente',
            'clase': 'bg-success',
            'texto': f'{dias_para_vencer} días restantes'
        }
    
    # En cualquier otro caso, no mostrar indicador adicional
    return None





def calcular_precio_por_dias(producto_id, dias_renta):
    """Calcula el precio según los días de renta"""
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    
    # Obtener precios actualizados de la BD
    cursor.execute("""
        SELECT precio_dia, precio_14_dias, precio_29_dias, precio_30_dias
        FROM producto_precios 
        WHERE id_producto = %s
    """, (producto_id,))
    
    precios = cursor.fetchone()
    
    # Obtener si es precio único
    cursor.execute("SELECT precio_unico FROM productos WHERE id_producto = %s", (producto_id,))
    precio_unico_result = cursor.fetchone()
    precio_unico = precio_unico_result['precio_unico'] if precio_unico_result else 0
    
    cursor.close()
    conexion.close()
    
    if not precios:
        return 0.00
    
    # Nueva lógica de precios igual que en rentas y prefactura
    if precio_unico == 1:
        return float(precios['precio_dia'])  # Precio único por día
    else:
        # Lógica para determinar precio según días
        if dias_renta <= 2:
            return float(precios['precio_dia'])          # 1-2 días
        elif dias_renta <= 14:
            return float(precios['precio_14_dias'])      # 3-14 días
        elif dias_renta <= 29:
            return float(precios['precio_29_dias'])      # 15-29 días
        else:  # 30+ días
            return float(precios['precio_30_dias'])      # 30+ días












# En routes/cotizaciones.py, agregar estas funciones:

def generar_pdf_cotizacion_buffer(cotizacion_id):
    """Función auxiliar para generar PDF y retornar buffer"""
    import os
    
    conexion = get_db_connection()
    cursor = conexion.cursor(dictionary=True)
    
    # Obtener datos de la cotización
    cursor.execute("""
        SELECT c.*, u.nombre as usuario_nombre, u.apellido1 as usuario_apellido,
               s.nombre as sucursal_nombre, s.direccion as sucursal_direccion,
               c.fecha_creacion as fecha_creacion_local
        FROM cotizaciones c
        JOIN usuarios u ON c.usuario_id = u.id
        JOIN sucursales s ON c.sucursal_id = s.id
        WHERE c.id = %s
    """, (cotizacion_id,))
    
    cotizacion = cursor.fetchone()
    
    # Obtener detalle de productos con piezas - CORREGIDO con JOIN a tabla piezas
    cursor.execute("""
        SELECT cd.*, p.nombre, p.descripcion, p.tipo, c.dias_renta,
               GROUP_CONCAT(DISTINCT CONCAT(pp.cantidad, ' ', pz.nombre_pieza) SEPARATOR ', ') as piezas
        FROM cotizacion_detalle cd
        JOIN productos p ON cd.producto_id = p.id_producto
        JOIN cotizaciones c ON cd.cotizacion_id = c.id
        LEFT JOIN producto_piezas pp ON p.id_producto = pp.id_producto
        LEFT JOIN piezas pz ON pp.id_pieza = pz.id_pieza
        WHERE cd.cotizacion_id = %s
        GROUP BY cd.id
    """, (cotizacion_id,))
    
    productos = cursor.fetchall()
    cursor.close()
    conexion.close()
    
    # --- GENERAR OVERLAY CON DATOS ---
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    
    # Registrar fuente Carlito
    try:
        pdfmetrics.registerFont(TTFont('Carlito', os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')))
        can.setFont("Carlito", 10)
    except:
        can.setFont("Carlito", 10)
    
    # === INFORMACIÓN DE LA EMPRESA (PARTE SUPERIOR) ===
    can.setFont("Helvetica-Bold", 12)
    can.drawString(25, 708, "COTIZACIÓN DE RENTA DE ANDAMIOS Y EQUIPO LIGERO")
    
    
    # Fecha y folio (lado derecho)
    # Una sola línea con formato completo
    can.setFont("Carlito", 10)
    can.drawString(482, 708, f"{cotizacion['fecha_creacion_local'].strftime('%d/%m/%Y - %H:%M:%S')}")
    
    can.setFont("Helvetica-Bold", 10)
    can.drawString(455, 680, f"COTIZACIÓN # {cotizacion['numero_cotizacion']}")
    
    can.setFont("Carlito", 10)
    can.drawString(455, 670, f"VIGENCIA: {cotizacion['fecha_vigencia'].strftime('%d/%m/%Y')}")
    
    
    # === DATOS DEL CLIENTE (TODOS DE LA TABLA COTIZACIONES) ===
    y = 675
    can.setFont("Helvetica-Bold", 11)
    can.drawString(25, y-5, "DATOS DEL CLIENTE")
    y -= 20

    # Línea separadora
    can.line(25, 668, 580, 668)
    
    can.setFont("Carlito", 10)
    # Determinar destinatario (empresa o cliente)
    if cotizacion['cliente_empresa'] and cotizacion['cliente_empresa'].strip():
        destinatario = cotizacion['cliente_empresa'].upper()
        can.drawString(25, y, f"EMPRESA: {destinatario}")
        y -= 15
        can.drawString(25, y, f"CONTACTO: {cotizacion['cliente_nombre'].upper()}")
    else:
        destinatario = cotizacion['cliente_nombre'].upper()
        can.drawString(25, y, f"CLIENTE: {destinatario}")
    
    y -= 15
    can.drawString(25, y, f"TELÉFONO: {cotizacion['cliente_telefono']}")
    y -= 15
    can.drawString(25, y, f"EMAIL: {cotizacion['cliente_email'] or 'No proporcionado'.upper()}")
    y -= 15
    can.drawString(25, y, f"DIAS DE RENTA: {cotizacion['dias_renta']}")
    
    y -= 20
    # === SALUDO PERSONALIZADO ===
    can.setFont("Carlito", 10)
    if cotizacion['cliente_empresa'] and cotizacion['cliente_empresa'].strip():
        saludo = f"ESTIMADA EMPRESA {cotizacion['cliente_empresa'].upper()}, A CONTINUACIÓN SE LE PRESENTA  LA COTIZACIÓN SOLICITADA:"
    else:
        saludo = f"ESTIMADO/A {cotizacion['cliente_nombre'].upper()}, A CONTINUACIÓN SE LE PRESENTA  LA COTIZACIÓN SOLICITADA:"
    
    can.drawString(25, y, saludo)
    
    can.line(25, y-5, 580, y-5)  # Línea separadora
    y -= 15
    # === TABLA DE PRODUCTOS ===
    can.setFont("Helvetica-Bold", 9)
    can.drawString(50, y, "PRODUCTO")
    can.drawString(330, y, "CANT.")
    can.drawString(380, y, "DÍAS")
    can.drawString(420, y, "PRECIO UNIT.")
    can.drawString(500, y, "SUBTOTAL")
    
    y -= 3
    can.line(25, y, 580, y)  # Línea separadora
    y -= 15
    
    can.setFont("Carlito", 8)
    subtotal_productos = 0
    

    for producto in productos:

    # Guardar posición Y inicial para los datos numéricos
        y_inicial_producto = y
        
        # Nombre del producto
        can.setFont("Carlito", 8)
        can.drawString(25, y, producto['nombre'][:30].upper())
        y -= 8
        # Función para dividir texto en líneas
        def dividir_texto(texto, max_chars):
            palabras = texto.split()
            lineas = []
            linea_actual = ""
            
            for palabra in palabras:
                if len(linea_actual + " " + palabra) <= max_chars:
                    if linea_actual:
                        linea_actual += " " + palabra
                    else:
                        linea_actual = palabra
                else:
                    if linea_actual:
                        lineas.append(linea_actual)
                    linea_actual = palabra
            
            if linea_actual:
                lineas.append(linea_actual)
            
            return lineas
        
        # Descripción del producto con saltos de línea
        if producto['descripcion']:
            can.setFont("Carlito", 7)
            descripcion_upper = producto['descripcion'].upper()
            lineas_descripcion = dividir_texto(descripcion_upper, 75)  # Máximo 45 caracteres por línea
            
            for linea in lineas_descripcion:
                can.drawString(40, y, linea)
                y -= 8  # Espaciado entre líneas más pequeño
        
        # Piezas SOLO si es conjunto/kit Y tiene piezas
        if producto['tipo'] == 'conjunto' and producto['piezas']:
            can.setFont("Carlito", 7)
            
            # Multiplicar piezas por la cantidad de equipos
            piezas_multiplicadas = []
            for pieza in producto['piezas'].split(', '):
                # Extraer cantidad y nombre de cada pieza (formato: "2 Tubos")
                partes = pieza.strip().split(' ', 1)
                if len(partes) >= 2:
                    try:
                        cantidad_original = int(partes[0])
                        nombre_pieza = partes[1]
                        cantidad_total = cantidad_original * producto['cantidad']
                        piezas_multiplicadas.append(f"{cantidad_total} {nombre_pieza}")
                    except ValueError:
                        # Si no se puede convertir a entero, mantener original
                        piezas_multiplicadas.append(pieza)
                else:
                    piezas_multiplicadas.append(pieza)
            
            piezas_texto = f"INCLUYE: {', '.join(piezas_multiplicadas).upper()}"
            lineas_piezas = dividir_texto(piezas_texto, 75)
            
            for linea in lineas_piezas:
                can.drawString(40, y, linea)
                y -= 8
        
        # Datos numéricos alineados con el nombre del producto
        can.setFont("Carlito", 9)
        can.drawRightString(348, y_inicial_producto, str(producto['cantidad']))
        can.drawRightString(396, y_inicial_producto, str(producto['dias_renta']))
        can.drawRightString(473, y_inicial_producto, f"${producto['precio_unitario']:.2f}")
        can.drawRightString(545, y_inicial_producto, f"${producto['subtotal']:.2f}")
        
        subtotal_productos += producto['subtotal']
        y -= 7  # Espacio entre productos





    
    # Traslado si existe
    if cotizacion['requiere_traslado'] and cotizacion['costo_traslado'] > 0:
        can.setFont("Carlito", 9)
        can.drawString(25, y, f"TRASLADO {cotizacion['tipo_traslado'].upper()}")
        y -= 10
        can.setFont("Carlito", 7)
        
        # Descripción específica según el tipo de traslado
        if cotizacion['tipo_traslado'].lower() == 'redondo':
            descripcion_traslado = "SERVICIO DE TRASLADO DE IDA Y REGRESO DEL EQUIPO"
        else:
            cotizacion['tipo_traslado'].lower() == 'medio'
            descripcion_traslado = "SERVICIO DE TRASLADO (IDA O REGRESO SEGÚN EL CLIENTE)"
        
        
        can.drawString(40, y, descripcion_traslado)
        y -= 5
        
        can.setFont("Carlito", 9)
        can.drawRightString(348, y+3, "-")
        can.drawRightString(396, y+3, "-")
        can.drawRightString(473, y+3, "-")
        can.drawRightString(545, y+3, f"${cotizacion['costo_traslado']:.2f}")
        
    y -= 6
    # Línea separadora antes de totales
    can.line(25, y, 580, y)
    y -= 15
    
    # === TOTALES ===
    can.setFont("Carlito", 10)
    can.drawString(430, y, "SUBTOTAL:")
    can.drawRightString(545, y, f"${cotizacion['subtotal']:.2f}")
    y -= 15
    
    can.drawString(430, y, "IVA (16%):")
    can.drawRightString(545, y, f"${cotizacion['iva']:.2f}")
    y -= 15
    
    can.setFont("Helvetica-Bold", 11)
    can.drawString(430, y, "TOTAL:")
    can.drawRightString(545, y, f"${cotizacion['total']:.2f}")
    y -= 10


    
    espacio_necesario = 100 # Espacio para certificaciones, métodos de pago, etc.

    if y < espacio_necesario:
        # Crear nueva página
        can.showPage()
        y = 750  # Reiniciar Y en la nueva página
        
        # Opcional: Agregar encabezado en la nueva página
        can.setFont("Helvetica-Bold", 12)
        can.drawString(50, y, f"COTIZACIÓN #{cotizacion['numero_cotizacion']} - CONTINUACIÓN")
        y -= 30

    

        # === CERTIFICACIONES DE SEGURIDAD (SIN TÍTULO, SOLO ASTERISCO Y NEGRITAS) ===
    can.setFont("Helvetica-Bold", 8)  # Tamaño un poco más pequeño y negritas
    can.drawString(50, y, "* TODOS NUESTROS EQUIPOS CUENTAN CON CERTIFICADOS DE SEGURIDAD")
    y -= 10
    can.drawString(50, y, "* LOS ANDAMIOS TIENEN CERTIFICACIÓN QUE CUMPLE CON LA NOM-009-STPS")
    y -= 15

    # === MÉTODOS DE PAGO Y FACTURACIÓN COMBINADOS ===
    can.setFont("Helvetica-Bold", 8)
    can.drawString(50, y, "MÉTODOS DE PAGO Y FACTURACIÓN:")
    y -= 10

    can.setFont("Carlito", 8)
    can.drawString(60, y, "• EFECTIVO, TRANSFERENCIA BANCARIA, TARJETAS DE DÉBITO Y CRÉDITO")
    y -= 10
    can.drawString(60, y, "• CONTAMOS CON FACTURACIÓN ELECTRÓNICA")
    y -= 10

    # === REQUISITOS DEL CLIENTE (MANTENER COMO ESTÁ) ===
    can.setFont("Helvetica-Bold", 8)
    can.drawString(50, y, "REQUISITOS DEL CLIENTE:")
    y -= 10

    can.setFont("Carlito", 8)
    requisitos = [
        "• IDENTIFICACIÓN OFICIAL",
        "• LICENCIA DE CONDUCIR", 
        "• CONSTANCIA DE SITUACIÓN FISCAL",
        "• COMPROBANTE DE DOMICILIO"
    ]

    for req in requisitos:
        can.drawString(60, y, req)
        y -= 10

    y -= 5

    # === CONDICIONES (MANTENER COMO ESTÁ) ===
    can.setFont("Helvetica-Bold", 8)
    can.drawString(50, y, "CONDICIONES:")
    y -= 10

    can.setFont("Carlito", 8)
    condiciones = [
        "• SE REQUIERE EL PAGO COMPLETO POR ADELANTADO",
        "• UBICACIÓN EXACTA DE LA OBRA (GOOGLE MAPS)",
        "• EL PERÍODO INCLUYE DOMINGOS Y DÍAS FESTIVOS",
        "• NO SE ARMA, NI SE DESARMA EL EQUIPO",
        "• COTIZACIÓN VÁLIDA POR 7 DÍAS"
    ]

    for cond in condiciones:
        can.drawString(60, y, cond)
        y -= 10

    y -= 5

    # === DATOS BANCARIOS ===
    can.setFont("Helvetica-Bold", 8)
    can.drawString(50, y, "DATOS BANCARIOS:")
    y -= 10

    can.setFont("Carlito", 8)
    can.drawString(60, y, "CUENTA: JAVIER ENRIQUE ALCOCER BERNES")
    y -= 10
    can.drawString(60, y, "• BANCO: BANORTE")
    y -= 10
    can.drawString(60, y, "• CTA: 0659076153")
    y -= 10
    can.drawString(60, y, "• CLABE: 072050006590761530")
    y -= 10
    can.drawString(60, y, "• R.F.C: AOBJ650602UE1")
    y -= 10
    can.drawString(60, y, "• EMAIL: puntalesyandamioscolosio@hotmail.com")

    y -= 24







        # === PIE DE PÁGINA ===
    # Línea separadora antes del pie de página
    can.line(25, y+18, 580, y+18)
    y -= 1

    
    can.setFont("Helvetica-Bold", 9)
    # Calcular posición centrada manualmente
    texto1 = "ATENDIDO POR: ING. JAVIER ENRIQUE ALCOCER BERNES"
    texto2 = "GERENTE DE ANDAMIOS COLOSIO DEL ESTADO DE CAMPECHE, CAMPECHE"
    texto3 = "VISITE NUESTRA PÁGINA: WWW.ANDAMIOSCOLOSIO.COM"

    # Centrar texto manualmente (aproximadamente en x=300 para una página de 612 pts)
    can.drawString(173, y, texto1)
    y -= 12
    can.drawString(135, y, texto2)
    y -= 15

    # Página web
    can.setFont("Helvetica-Bold", 10)
    can.drawString(160, y, texto3)

    can.save()
    packet.seek(0)
    
    # --- COMBINAR CON PLANTILLA ---
    try:
        plantilla_path = os.path.join(current_app.root_path, 'static/notas/cotizacion.pdf')
        existing_pdf = PdfReader(plantilla_path)
        output = PdfWriter()
        
        # Leer el overlay
        new_pdf = PdfReader(packet)
        
        # ⭐ AGREGAR TODAS LAS PÁGINAS DEL OVERLAY ⭐
        for page_num in range(len(new_pdf.pages)):
            if page_num == 0:
                # Primera página: combinar con plantilla
                page = existing_pdf.pages[0]
                page.merge_page(new_pdf.pages[page_num])
                output.add_page(page)
            else:
                # Páginas adicionales: agregar solo el overlay
                output.add_page(new_pdf.pages[page_num])
        
    except Exception as e:
        print(f"Error al usar plantilla: {e}")
        # Si no hay plantilla, usar solo el overlay
        output = PdfWriter()
        new_pdf = PdfReader(packet)
        for page in new_pdf.pages:
            output.add_page(page)
    
    # Retornar buffer
    output_stream = BytesIO()
    output.write(output_stream)
    output_stream.seek(0)
    
    return output_stream


# Mantener la función original para acceso directo
@cotizaciones_bp.route('/pdf/<int:cotizacion_id>')
@requiere_sesion()
@requiere_permiso('ver_cotizaciones')
def generar_pdf_cotizacion(cotizacion_id):
    """Generar PDF de cotización - acceso directo por URL"""
    try:
        buffer = generar_pdf_cotizacion_buffer(cotizacion_id)
        
        # Obtener número de cotización para el nombre del archivo
        conexion = get_db_connection()
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT numero_cotizacion FROM cotizaciones WHERE id = %s", (cotizacion_id,))
        cotizacion = cursor.fetchone()
        cursor.close()
        conexion.close()
        
        numero_cotizacion = cotizacion['numero_cotizacion'] if cotizacion else str(cotizacion_id)
        
        return send_file(
            buffer,
            download_name=f"cotizacion_{numero_cotizacion}.pdf",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        print(f"Error al generar PDF: {e}")
        flash('Error al generar el PDF de la cotización', 'error')
        return redirect(url_for('cotizaciones.index'))














@cotizaciones_bp.route('/')
@requiere_sesion()
@requiere_permiso('ver_cotizaciones')
def index():
    """Página principal de cotizaciones"""
    try:
        verificar_cotizaciones_vencidas()
        
        conexion = get_db_connection()
        cursor = conexion.cursor(dictionary=True)
        
        # Obtener filtros
        busqueda = request.args.get('busqueda', '')
        filtro_estado = request.args.get('filtro', '')
        
        # Query base
        query = """
            SELECT c.*, u.nombre as usuario_nombre, u.apellido1 as usuario_apellido,
                   s.nombre as sucursal_nombre,
                   DATEDIFF(c.fecha_vigencia, CURDATE()) as dias_para_vencer
            FROM cotizaciones c
            JOIN usuarios u ON c.usuario_id = u.id
            JOIN sucursales s ON c.sucursal_id = s.id
            WHERE 1=1
        """
        
        params = []
        
        if busqueda:
            query += " AND (c.numero_cotizacion LIKE %s OR c.cliente_nombre LIKE %s OR c.cliente_empresa LIKE %s)"
            busqueda_param = f"%{busqueda}%"
            params.extend([busqueda_param, busqueda_param, busqueda_param])
        
        if filtro_estado:
            query += " AND c.estado = %s"
            params.append(filtro_estado)
        
        query += " ORDER BY c.fecha_creacion DESC"
        
        cursor.execute(query, params)
        cotizaciones = cursor.fetchall()
        
        # Aplicar estado de vigencia
        cotizaciones_con_estado = []
        for cotizacion in cotizaciones:
            estado_vigencia = calcular_estado_vigencia(cotizacion)
            cotizacion_con_estado = dict(cotizacion)
            cotizacion_con_estado['estado_vigencia'] = estado_vigencia
            cotizaciones_con_estado.append(cotizacion_con_estado)
        
        # Obtener productos por cotización
        productos_por_cotizacion = {}
        for cotizacion in cotizaciones_con_estado:
            cursor.execute("""
                SELECT p.nombre, cd.cantidad, cd.precio_unitario, cd.subtotal
                FROM cotizacion_detalle cd
                JOIN productos p ON cd.producto_id = p.id_producto
                WHERE cd.cotizacion_id = %s
            """, (cotizacion['id'],))
            productos_por_cotizacion[cotizacion['id']] = cursor.fetchall()
        
        # Obtener productos para el modal
        cursor.execute("SELECT id_producto, nombre FROM productos WHERE estatus = 'activo'")
        productos_disponibles = cursor.fetchall()
        
        cursor.close()
        conexion.close()
        
        return render_template('cotizaciones/cotizacion.html', 
                             cotizaciones=cotizaciones_con_estado,
                             productos_por_cotizacion=productos_por_cotizacion,
                             productos=productos_disponibles)
    
    except Exception as e:
        print(f"Error en cotizaciones index: {e}")
        flash('Error al cargar las cotizaciones', 'error')
        return render_template('cotizaciones/cotizacion.html', 
                             cotizaciones=[], 
                             productos_por_cotizacion={},
                             productos=[])









@cotizaciones_bp.route('/crear', methods=['POST'])
@requiere_sesion()
@requiere_permiso('crear_cotizacion')
def crear_cotizacion():
    """Crear nueva cotización"""
    try:
        # Obtener datos del formulario
        cliente_nombre = request.form.get('cliente_nombre')
        cliente_telefono = request.form.get('cliente_telefono')
        cliente_email = request.form.get('cliente_email', '')
        cliente_empresa = request.form.get('cliente_empresa', '')
        dias_renta = int(request.form.get('dias_renta'))
        requiere_traslado = bool(request.form.get('requiere_traslado'))
        tipo_traslado = request.form.get('tipo_traslado') if requiere_traslado else None
        costo_traslado = float(request.form.get('costo_traslado', 0)) if requiere_traslado else 0
        
        # Calcular fecha de vigencia: 7 días desde hoy
        fecha_vigencia = get_local_now() + timedelta(days=7)
        
        # Obtener productos
        productos = []
        i = 0
        while f'productos[{i}][producto_id]' in request.form:
            producto_id = int(request.form[f'productos[{i}][producto_id]'])
            cantidad = int(request.form[f'productos[{i}][cantidad]'])
            precio_unitario = float(request.form[f'productos[{i}][precio_unitario]'])
            subtotal = float(request.form[f'productos[{i}][subtotal]'])
            
            productos.append({
                'producto_id': producto_id,
                'cantidad': cantidad,
                'precio_unitario': precio_unitario,
                'subtotal': subtotal
            })
            i += 1
        
        if not productos and not requiere_traslado:
            return jsonify({'error': 'Debe agregar al menos un producto o servicio de traslado'}), 400
        
        # Calcular totales
        subtotal_productos = sum(p['subtotal'] for p in productos)
        subtotal_total = subtotal_productos + costo_traslado
        iva = subtotal_total * 0.16
        total = subtotal_total + iva
        
        # Generar número de cotización
        numero_cotizacion = generar_numero_cotizacion()
        
        # Obtener usuario y sucursal de la sesión
        usuario_id = session.get('user_id')
        sucursal_id = session.get('sucursal_id')
        
        conexion = get_db_connection()
        cursor = conexion.cursor()
        
        # Insertar cotización
        cursor.execute("""
            INSERT INTO cotizaciones (
                numero_cotizacion, cliente_nombre, cliente_telefono, cliente_email,
                cliente_empresa, dias_renta, requiere_traslado, tipo_traslado,
                costo_traslado, subtotal, iva, total, fecha_vigencia, estado, usuario_id, sucursal_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            numero_cotizacion, cliente_nombre, cliente_telefono, cliente_email,
            cliente_empresa, dias_renta, requiere_traslado, tipo_traslado,
            costo_traslado, subtotal_total, iva, total, fecha_vigencia.date(), 
            'enviada', usuario_id, sucursal_id
        ))
        
        cotizacion_id = cursor.lastrowid
        
        # Insertar detalle de productos
        for producto in productos:
            cursor.execute("""
                INSERT INTO cotizacion_detalle (
                    cotizacion_id, producto_id, cantidad, precio_unitario, subtotal
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                cotizacion_id, producto['producto_id'], producto['cantidad'],
                producto['precio_unitario'], producto['subtotal']
            ))
        
        # Insertar seguimiento
        cursor.execute("""
            INSERT INTO cotizacion_seguimiento (
                cotizacion_id, estado_nuevo, comentarios, usuario_id
            ) VALUES (%s, %s, %s, %s)
        """, (cotizacion_id, 'enviada', 'Cotización creada y enviada', usuario_id))
        
        conexion.commit()
        cursor.close()
        conexion.close()

        # Verificar si espera JSON o redirección
        if request.headers.get('Accept') == 'application/json':
            return jsonify({
                'success': True,
                'cotizacion_id': cotizacion_id,
                'pdf_url': f'/cotizaciones/pdf/{cotizacion_id}'
            })
        else:
            return redirect(url_for('cotizaciones.generar_pdf_cotizacion', cotizacion_id=cotizacion_id))
        
    except Exception as e:
        print(f"Error al crear cotización: {e}")

        if request.headers.get('Accept') == 'application/json':
            return jsonify({'success': False, 'error': 'Error al crear la cotización'}), 500
        else:
            return f"<h1>Error al generar la cotización</h1><p>{str(e)}</p><p><a href='javascript:history.back()'>Volver</a></p>", 500



        
        
        
 









@cotizaciones_bp.route('/precios/<int:producto_id>/<int:dias>')  # Cambiar de '/cotizaciones/precios/...' a '/precios/...'
@requiere_sesion()
def obtener_precio_producto(producto_id, dias):

    """API para obtener precio de producto según días"""
    try:
        precio = calcular_precio_por_dias(producto_id, dias)
        return jsonify({'precio': precio})
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@cotizaciones_bp.route('/<int:cotizacion_id>/cambiar-estado', methods=['POST'])  # Quitar '/cotizaciones'
@requiere_sesion()
@requiere_permiso('editar_cotizacion')
def cambiar_estado_cotizacion(cotizacion_id):
 
    """Cambiar estado de una cotización"""
    try:
        nuevo_estado = request.json.get('estado')
        comentarios = request.json.get('comentarios', '')
        usuario_id = session.get('user_id')
        
        # Validar que el estado sea válido
        if nuevo_estado not in ['enviada', 'vencida', 'renta']:
            return jsonify({'error': 'Estado no válido'}), 400
        
        conexion = get_db_connection()
        cursor = conexion.cursor()
        
        # Obtener estado actual
        cursor.execute("SELECT estado FROM cotizaciones WHERE id = %s", (cotizacion_id,))
        resultado = cursor.fetchone()
        
        if not resultado:
            return jsonify({'error': 'Cotización no encontrada'}), 404
        
        estado_anterior = resultado[0]
        
        # Actualizar estado
        cursor.execute("""
            UPDATE cotizaciones 
            SET estado = %s 
            WHERE id = %s
        """, (nuevo_estado, cotizacion_id))
        
        # Registrar seguimiento
        cursor.execute("""
            INSERT INTO cotizacion_seguimiento (
                cotizacion_id, estado_anterior, estado_nuevo, comentarios, usuario_id
            ) VALUES (%s, %s, %s, %s, %s)
        """, (cotizacion_id, estado_anterior, nuevo_estado, comentarios, usuario_id))
        
        conexion.commit()
        cursor.close()
        conexion.close()
        
        return jsonify({'success': True, 'message': 'Estado actualizado correctamente'})
        
    except Exception as e:
        print(f"Error al cambiar estado: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500




@cotizaciones_bp.route('/<int:cotizacion_id>/convertir-renta', methods=['POST'])  # Quitar '/cotizaciones'
@requiere_sesion()
@requiere_permiso('crear_renta')
def convertir_cotizacion_a_renta(cotizacion_id):
 
    """Convertir cotización a renta"""
    try:
        # Aquí implementarías la lógica para crear una renta basada en la cotización
        # Por ahora solo cambiamos el estado
        return cambiar_estado_cotizacion(cotizacion_id)
        
    except Exception as e:
        print(f"Error al convertir cotización a renta: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500
    


############################################
############################### ELIMINAR COTIZACIONES
###########################################

@cotizaciones_bp.route('/<int:cotizacion_id>/eliminar', methods=['DELETE'])
@requiere_sesion()
@requiere_permiso('eliminar_cotizacion')
def eliminar_cotizacion(cotizacion_id):
    """Eliminar cotización (eliminación lógica)"""
    try:
        usuario_id = session.get('user_id')
        
        conexion = get_db_connection()
        cursor = conexion.cursor()
        
        # Verificar que la cotización existe
        cursor.execute("SELECT numero_cotizacion FROM cotizaciones WHERE id = %s", (cotizacion_id,))
        cotizacion = cursor.fetchone()
        
        if not cotizacion:
            return jsonify({'error': 'Cotización no encontrada'}), 404
        
        # Eliminar detalles de productos
        cursor.execute("DELETE FROM cotizacion_detalle WHERE cotizacion_id = %s", (cotizacion_id,))
        
        # Eliminar seguimiento
        cursor.execute("DELETE FROM cotizacion_seguimiento WHERE cotizacion_id = %s", (cotizacion_id,))
        
        # Eliminar la cotización principal
        cursor.execute("DELETE FROM cotizaciones WHERE id = %s", (cotizacion_id,))
        
        conexion.commit()
        cursor.close()
        conexion.close()
        
        return jsonify({
            'success': True, 
            'message': f'Cotización {cotizacion[0]} eliminada correctamente'
        })
        
    except Exception as e:
        print(f"Error al eliminar cotización: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500



















 