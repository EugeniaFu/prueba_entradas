from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, session, send_file
from utils.db import get_db_connection
from werkzeug.utils import secure_filename
import os
import requests
from io import BytesIO
from datetime import datetime
from utils.datetime_utils import get_local_now, format_date_local
from utils.decorators import requiere_sesion, requiere_permiso
from services.cliente_service import ClienteService
from services.renta_service import RentasService
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
from PyPDF2 import PdfReader, PdfWriter

clientes_bp = Blueprint('clientes', __name__, url_prefix='/clientes')

@clientes_bp.route('/', methods=['GET'])
@requiere_sesion()
@requiere_permiso('ver_clientes')
def clientes():
    busqueda = request.args.get('busqueda', '').strip()
    filtro = request.args.get('filtro', '').strip()
    ver_bajas = request.args.get('ver_bajas', '').strip()
    
    # Extraemos la lista usando nuestro nuevo servicio, manteniendo el código limpio de consultas SQL
    clientes = ClienteService.obtener_lista_clientes(busqueda, filtro, ver_bajas)

    return render_template(
        'clientes/clientes.html',
        clientes=clientes,
        filtro=filtro,
        ver_bajas=ver_bajas
    )






#############################
###############################
############################# EDITA CLIENTES

@clientes_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@requiere_sesion()
@requiere_permiso('editar_cliente')
def editar_cliente(id):
    if request.method == 'POST':
        datos_cliente = {
            'nombre': request.form['nombre'],
            'apellido1': request.form['apellido1'],
            'apellido2': request.form['apellido2'],
            'telefono': request.form['telefono'],
            'correo': request.form['correo'],
            'rfc': request.form['rfc'],
            'tipo_cliente': request.form['tipo_cliente'],
            'calle': request.form.get('calle', '').strip(),
            'entre_calles': request.form.get('entre_calles', '').strip(),
            'numero_exterior': request.form.get('numero_exterior', '').strip(),
            'numero_interior': request.form.get('numero_interior', '').strip(),
            'colonia': request.form.get('colonia', '').strip(),
            'codigo_postal': request.form.get('codigo_postal', '').strip(),
            'municipio': request.form.get('municipio', '').strip(),
            'estado': request.form.get('estado', '').strip()
        }
        
        ids_eliminar = request.form.getlist('eliminar_doc')
        
        # Procesar actualizaciones de tipo de documento
        documentos_existentes = {}
        for key in request.form:
            if key.startswith('tipo_documento_existente_'):
                doc_id = key.replace('tipo_documento_existente_', '')
                documentos_existentes[doc_id] = request.form[key]

        # Subir nuevos documentos
        archivos = [f for f in request.files.getlist('documentos') if f and f.filename]
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'clientes')
        os.makedirs(upload_folder, exist_ok=True)
        
        documentos_nuevos = []
        for idx, archivo in enumerate(archivos):
            try:
                filename = secure_filename(archivo.filename)
                ruta = os.path.join(upload_folder, filename)
                archivo.save(ruta)
                tipo_documento = request.form.get(f"tipo_documento_{idx}", "otro")
                documentos_nuevos.append({'tipo_documento': tipo_documento, 'filename': filename})
            except Exception as e:
                flash(f"Error al subir el archivo {archivo.filename}", "danger")

        # Usar el servicio para la base de datos
        try:
            ClienteService.actualizar_cliente_y_documentos(id, datos_cliente, ids_eliminar, documentos_existentes, documentos_nuevos)
            flash("Cliente actualizado correctamente.", "success")
        except Exception as e:
            flash(f"Error al actualizar el cliente: {str(e)}", "danger")

        return redirect(url_for('clientes.clientes'))
    else:
        # Datos del cliente extraídos por el servicio
        cliente = ClienteService.obtener_cliente_por_id(id)
        documentos = ClienteService.obtener_documentos_cliente(id)
        
        if not cliente:
            flash("Cliente no encontrado.", "danger")
            return redirect(url_for('clientes.clientes'))
        return render_template('clientes/editar_cliente.html', cliente=cliente, documentos=documentos)





############################################
############################################
############################## BAJA, REACTIVACION Y ELIMINACION DEFINITIVA
@clientes_bp.route('/baja/<int:id>')
@requiere_sesion()
@requiere_permiso('baja_cliente')
def baja_cliente(id):
    ClienteService.cambiar_estado_cliente(id, activo=False)
    flash("Cliente dado de baja correctamente.", "info")
    return redirect(url_for('clientes.clientes'))

@clientes_bp.route('/reactivar/<int:id>')
@requiere_sesion()
@requiere_permiso('reactivar_cliente')
def reactivar_cliente(id):
    ClienteService.cambiar_estado_cliente(id, activo=True)
    flash("Cliente reactivado correctamente.", "success")
    return redirect(url_for('clientes.clientes', ver_bajas=1))

@clientes_bp.route('/eliminar/<int:id>')
@requiere_sesion()
@requiere_permiso('eliminar_cliente')
def eliminar_cliente(id):
    ClienteService.eliminar_cliente_definitivo(id)
    flash("Cliente eliminado definitivamente.", "danger")
    return redirect(url_for('clientes.clientes', ver_bajas=1))






############################################
############################################
############################## visualizacion del cliente

@clientes_bp.route('/detalle/<int:id>')
@requiere_sesion()
@requiere_permiso('ver_detalle_cliente')
def detalle_cliente(id):
    cliente = ClienteService.obtener_detalle_cliente(id)
    documentos = ClienteService.obtener_documentos_cliente(id)

    if not cliente:
        flash("Cliente no encontrado.", "danger")
        return redirect(url_for('clientes.clientes'))

    historial = RentasService.obtener_historial_cliente(id)
    return render_template('clientes/detalle_cliente.html', cliente=cliente, documentos=documentos, historial=historial)





############################################
############################################
##############################  BUSCADOR

@clientes_bp.route('/buscar')
@requiere_sesion()
@requiere_permiso('buscar_clientes')
def buscar_clientes():
    term = request.args.get('q', '').strip()
    results = ClienteService.buscar_clientes_dinamico(term)
    return jsonify(results)





############################################
############################################
############################## BUSCADOR DE CODIGOS POSTALES 

@clientes_bp.route('/api/colonias/<codigo_postal>')
@requiere_sesion()
def obtener_colonias_por_cp(codigo_postal):
    """
    Busca colonias por código postal
    Método: JSON Local (rápido)
    """
    try:
        from utils.codigos_postales import CodigosPostalesJSON
        
        buscador_json = CodigosPostalesJSON()
        resultado_json = buscador_json.buscar_colonias(codigo_postal)
        
        if resultado_json['success']:
            return jsonify({
                'success': True,
                'estado': resultado_json['estado'],
                'municipio': resultado_json['municipio'], 
                'colonias': resultado_json['colonias'],
                'fuente': 'JSON Local'
            })
        else:
            # CP no encontrado, activar llenado manual
            return jsonify({
                'success': False, 
                'message': f'CP {codigo_postal} no encontrado. Llena los datos manualmente.'
            })
                
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': 'Error al buscar código postal. Llena los datos manualmente.'
        })





############################################
############################################
############################## NUEVO CLIENTE 

@clientes_bp.route('/nuevo', methods=['GET', 'POST'])
@requiere_sesion()
@requiere_permiso('crear_cliente')
def nuevo_cliente():
    if request.method == 'POST':
        datos_cliente = {
            'nombre': request.form['nombre'],
            'apellido1': request.form['apellido1'],
            'apellido2': request.form['apellido2'],
            'telefono': request.form['telefono'],
            'correo': request.form.get('correo'),
            'rfc': request.form.get('rfc'),
            'tipo_cliente': request.form['tipo_cliente'],
            'fecha_alta': format_date_local(get_local_now(), '%Y-%m-%d'),
            'calle': request.form.get('calle', '').strip(),
            'entre_calles': request.form.get('entre_calles', '').strip(),
            'numero_exterior': request.form.get('numero_exterior', '').strip(),
            'numero_interior': request.form.get('numero_interior', '').strip(),
            'colonia': request.form.get('colonia', '').strip(),
            'codigo_postal': request.form.get('codigo_postal', '').strip(),
            'municipio': request.form.get('municipio', '').strip(),
            'estado': request.form.get('estado', '').strip()
        }

        archivos = request.files.getlist('documentos')
        
        # Si el usuario en sesión no tiene sucursal (es admin), tomamos la sucursal que eligió del formulario
        sucursal_id = session.get('sucursal_id')
        if not sucursal_id:
            sucursal_id = request.form.get('sucursal_id')

        # VALIDACIONES
        errores = []
        if not datos_cliente['nombre'] or not datos_cliente['apellido1'] or not datos_cliente['apellido2'] or not datos_cliente['telefono'] or not datos_cliente['tipo_cliente']:
            errores.append("Todos los campos obligatorios deben estar llenos.")
        
        if not datos_cliente['calle'] or not datos_cliente['numero_exterior'] or not datos_cliente['colonia'] or not datos_cliente['codigo_postal'] or not datos_cliente['municipio'] or not datos_cliente['estado']:
            errores.append("Todos los campos de dirección son obligatorios.")
        
        if not any(archivo.filename for archivo in archivos):
            errores.append("Debes subir al menos un documento (INE, Licencia o Comprobante).")
        if not sucursal_id:
            errores.append("Debes seleccionar una sucursal para el cliente.")

        # Verificar duplicados desde el servicio
        errores.extend(ClienteService.verificar_duplicados(datos_cliente['telefono'], datos_cliente['correo']))

        # Obtener sucursales por si hay fallo y debemos re-renderizar
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM sucursales WHERE activo = 1")
        except Exception:
            cursor.execute("SELECT * FROM sucursales")
        sucursales = cursor.fetchall()
        cursor.close()
        conn.close()

        if errores:
            for error in errores:
                flash(error, 'danger')
            return render_template('clientes/nuevo_cliente.html', sucursales=sucursales)

        # Si todo bien, guardar archivos físicos
        archivos_validos = [archivo for archivo in archivos if archivo and archivo.filename]
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'clientes')
        os.makedirs(upload_folder, exist_ok=True)
        
        documentos_nuevos = []
        for idx, archivo in enumerate(archivos_validos):
            try:
                filename = secure_filename(archivo.filename)
                import time
                timestamp = str(int(time.time()))
                name, ext = os.path.splitext(filename)
                filename = f"{name}_{timestamp}{ext}"
                
                ruta = os.path.join(upload_folder, filename)
                archivo.save(ruta)
                
                tipo_documento = request.form.get(f"tipo_documento_{idx}", "otro")
                documentos_nuevos.append({'tipo_documento': tipo_documento, 'filename': filename})
            except Exception as e:
                flash(f"Error procesando el archivo {archivo.filename}: {e}", "danger")
                return render_template('clientes/nuevo_cliente.html', sucursales=sucursales)
        
        # Enviar al servicio
        # El prefijo es el id de la sucursal con 2 dígitos, así nunca hay que
        # tocar este código al dar de alta una sucursal nueva.
        prefijo = f"{int(sucursal_id):02d}"
        success, err_msg = ClienteService.crear_cliente_completo(datos_cliente, sucursal_id, prefijo, documentos_nuevos)
        
        if success:
            flash("Cliente registrado exitosamente.", "success")
            return redirect(url_for('clientes.clientes'))
        else:
            flash(f"Ocurrió un error al guardar el cliente: {err_msg}", "danger")
            return render_template('clientes/nuevo_cliente.html', sucursales=sucursales)

    # Si es GET, consultamos las sucursales para el Admin
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM sucursales WHERE activo = 1")
    except Exception:
        cursor.execute("SELECT * FROM sucursales")
    sucursales = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('clientes/nuevo_cliente.html', sucursales=sucursales)


# ─────────────────────────────────────────────────────────────────────────────
# SALDO A FAVOR Y CONSOLIDACIÓN DE PAGOS
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_saldo_favor_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saldo_favor_clientes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            cliente_id INT NOT NULL,
            sucursal_id INT NOT NULL,
            tipo ENUM('credito','debito') NOT NULL DEFAULT 'credito',
            monto DECIMAL(12,2) NOT NULL,
            concepto VARCHAR(255) NOT NULL,
            referencia_tabla VARCHAR(50),
            referencia_id INT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usuario_id INT,
            INDEX idx_cliente_saldo (cliente_id)
        )
    """)


@clientes_bp.route('/api/saldo-favor/<int:cliente_id>', methods=['GET'])
@requiere_sesion()
@requiere_permiso('ver_estado_cuenta')
def get_saldo_favor(cliente_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        _ensure_saldo_favor_table(cursor)
        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo='credito' THEN monto ELSE 0 END), 0)
              - COALESCE(SUM(CASE WHEN tipo='debito'  THEN monto ELSE 0 END), 0)
              AS saldo
            FROM saldo_favor_clientes WHERE cliente_id = %s
        """, (cliente_id,))
        row = cursor.fetchone()
        saldo = float(row['saldo']) if row and row['saldo'] else 0.0

        cursor.execute("""
            SELECT id, tipo, monto, concepto, fecha
            FROM saldo_favor_clientes
            WHERE cliente_id = %s
            ORDER BY fecha DESC LIMIT 20
        """, (cliente_id,))
        movimientos = cursor.fetchall()
        for m in movimientos:
            m['monto'] = float(m['monto'])
            m['fecha'] = m['fecha'].strftime('%d/%m/%Y %H:%M') if m['fecha'] else ''

        return jsonify({'success': True, 'saldo': saldo, 'movimientos': movimientos})
    finally:
        cursor.close()
        conn.close()


@clientes_bp.route('/api/saldo-favor/<int:cliente_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('agregar_saldo_favor')
def agregar_saldo_favor(cliente_id):
    data = request.get_json()
    monto = float(data.get('monto', 0))
    concepto = data.get('concepto', '').strip()
    if monto <= 0:
        return jsonify({'success': False, 'message': 'El monto debe ser mayor a cero.'})
    if not concepto:
        return jsonify({'success': False, 'message': 'El concepto es requerido.'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        _ensure_saldo_favor_table(cursor)
        cursor.execute("SELECT sucursal_id FROM clientes WHERE id = %s", (cliente_id,))
        cli = cursor.fetchone()
        sucursal_id = cli['sucursal_id'] if cli else 1
        cursor.execute("""
            INSERT INTO saldo_favor_clientes
                (cliente_id, sucursal_id, tipo, monto, concepto, referencia_tabla, usuario_id)
            VALUES (%s, %s, 'credito', %s, %s, 'manual', %s)
        """, (cliente_id, sucursal_id, monto, concepto, session.get('user_id')))
        conn.commit()
        return jsonify({'success': True, 'message': 'Saldo a favor registrado correctamente.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


@clientes_bp.route('/api/estado-cuenta/<int:cliente_id>', methods=['GET'])
@requiere_sesion()
@requiere_permiso('ver_estado_cuenta')
def get_estado_cuenta(cliente_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        _ensure_saldo_favor_table(cursor)

        cursor.execute("""
            SELECT r.id, r.folio, r.id_sucursal,
                   r.fecha_salida, r.fecha_programada,
                   r.estado_renta, r.estado_pago,
                   r.renta_asociada_id,
                   COALESCE(r.renta_asociada_id, r.id) AS raiz_id,
                   COALESCE(
                       (SELECT folio FROM rentas WHERE id = r.renta_asociada_id),
                       r.folio
                   ) AS folio_raiz,
                   COALESCE(r.total_con_iva, r.total, 0) AS total,
                   COALESCE(
                       (SELECT SUM(p.monto) FROM prefacturas p WHERE p.renta_id = r.id AND p.pagada = 1),
                       0
                   ) AS pagado
            FROM rentas r
            WHERE r.cliente_id = %s
              AND r.estado_renta NOT IN ('cancelada')
              AND r.estado_pago NOT IN ('Pago realizado','Cancelado sin pago','Reembolsado','Saldo a favor')
            ORDER BY r.fecha_salida ASC, r.id ASC
        """, (cliente_id,))
        rentas_raw = cursor.fetchall()

        # Solo rentas con saldo real > 0.50 (umbral de redondeo en efectivo)
        rentas = []
        for r in rentas_raw:
            r['total'] = float(r['total'])
            r['pagado'] = float(r['pagado'])
            r['saldo_pendiente'] = round(r['total'] - r['pagado'], 2)
            if r['saldo_pendiente'] > 0.50:
                r['fecha_salida'] = r['fecha_salida'].strftime('%d/%m/%Y') if r['fecha_salida'] else ''
                r['fecha_programada'] = r['fecha_programada'].strftime('%d/%m/%Y') if r['fecha_programada'] else ''
                r['raiz_id'] = int(r['raiz_id'])
                r['folio_raiz'] = int(r['folio_raiz']) if r['folio_raiz'] else r['folio']
                r['renta_asociada_id'] = int(r['renta_asociada_id']) if r['renta_asociada_id'] else None
                rentas.append(r)

        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo='credito' THEN monto ELSE 0 END), 0)
              - COALESCE(SUM(CASE WHEN tipo='debito'  THEN monto ELSE 0 END), 0)
              AS saldo
            FROM saldo_favor_clientes WHERE cliente_id = %s
        """, (cliente_id,))
        row = cursor.fetchone()
        saldo_favor = float(row['saldo']) if row and row['saldo'] else 0.0
        total_adeudo = sum(r['saldo_pendiente'] for r in rentas)

        return jsonify({
            'success': True,
            'rentas': rentas,
            'saldo_favor': saldo_favor,
            'total_adeudo': round(total_adeudo, 2)
        })
    finally:
        cursor.close()
        conn.close()


@clientes_bp.route('/api/pago-consolidado/<int:cliente_id>', methods=['POST'])
@requiere_sesion()
@requiere_permiso('consolidar_pago')
def pago_consolidado(cliente_id):
    """
    Distribuye un pago lump-sum entre las rentas activas con saldo pendiente,
    de más antigua a más reciente (oldest-first). Genera una prefactura por cada
    renta que reciba pago.
    """
    from routes.prefactura import obtener_folio_consecutivo_prefactura
    from routes.caja import registrar_movimiento_automatico

    data = request.get_json()
    monto_efectivo = float(data.get('monto', 0))
    metodo_pago = data.get('metodo_pago', 'EFECTIVO').upper()
    numero_seguimiento = data.get('numero_seguimiento', '') or ''
    usar_saldo_favor = bool(data.get('usar_saldo_favor', False))
    facturable = int(data.get('facturable', 0))

    if monto_efectivo <= 0 and not usar_saldo_favor:
        return jsonify({'success': False, 'message': 'El monto debe ser mayor a cero.'})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        _ensure_saldo_favor_table(cursor)
        conn.start_transaction()

        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo='credito' THEN monto ELSE 0 END), 0)
              - COALESCE(SUM(CASE WHEN tipo='debito'  THEN monto ELSE 0 END), 0)
              AS saldo
            FROM saldo_favor_clientes WHERE cliente_id = %s
        """, (cliente_id,))
        row = cursor.fetchone()
        saldo_favor_disponible = float(row['saldo']) if row and row['saldo'] else 0.0
        saldo_favor_a_usar = saldo_favor_disponible if usar_saldo_favor else 0.0

        disponible = monto_efectivo + saldo_favor_a_usar

        cursor.execute("""
            SELECT r.id, r.folio, r.id_sucursal, r.fecha_salida, r.estado_pago,
                   COALESCE(r.total_con_iva, r.total, 0) AS total,
                   COALESCE(
                       (SELECT SUM(p.monto) FROM prefacturas p WHERE p.renta_id = r.id AND p.pagada = 1),
                       0
                   ) AS pagado
            FROM rentas r
            WHERE r.cliente_id = %s
              AND r.estado_renta NOT IN ('cancelada')
              AND r.estado_pago NOT IN ('Pago realizado','Cancelado sin pago','Reembolsado','Saldo a favor')
            ORDER BY r.fecha_salida ASC, r.id ASC
        """, (cliente_id,))
        rentas = cursor.fetchall()

        if not rentas:
            conn.rollback()
            return jsonify({'success': False, 'message': 'No hay rentas con saldo pendiente.'})

        # Un solo folio compartido para toda la consolidación (misma secuencia que
        # prefacturas, cobros extra y cobros por retraso de la sucursal).
        cursor.execute("SELECT sucursal_id FROM clientes WHERE id = %s", (cliente_id,))
        cli_suc = cursor.fetchone()
        sucursal_id_cliente = cli_suc['sucursal_id'] if cli_suc else rentas[0]['id_sucursal']
        folio_compartido = obtener_folio_consecutivo_prefactura(sucursal_id_cliente)

        pagos_generados = []
        remanente = disponible

        for r in rentas:
            if remanente <= 0:
                break
            total = float(r['total'])
            pagado = float(r['pagado'])
            saldo_pendiente = round(total - pagado, 2)
            if saldo_pendiente <= 0.50:  # umbral de redondeo en efectivo
                continue

            pago_renta = min(remanente, saldo_pendiente)
            remanente = round(remanente - pago_renta, 2)

            if pago_renta >= saldo_pendiente or abs(saldo_pendiente - pago_renta) < 1.00:
                nuevo_estado_pago = 'Pago realizado'
            else:
                nuevo_estado_pago = 'Saldo pendiente'
            # pagada=1 siempre: el dinero fue recibido.
            # La renta usa estado_pago para saber si quedó saldo pendiente.

            cursor.execute("""
                INSERT INTO prefacturas
                    (renta_id, fecha_emision, tipo, pagada, metodo_pago, monto,
                     monto_recibido, cambio, numero_seguimiento, generada,
                     facturable, folio, id_sucursal)
                VALUES (%s, NOW(), 'abono', 1, %s, %s, %s, 0, %s, 1, %s, %s, %s)
            """, (
                r['id'], metodo_pago, pago_renta,
                pago_renta, numero_seguimiento, facturable,
                folio_compartido, r['id_sucursal']
            ))
            prefactura_id = cursor.lastrowid

            cursor.execute("""
                UPDATE rentas SET estado_pago = %s, metodo_pago = %s WHERE id = %s
            """, (nuevo_estado_pago, metodo_pago, r['id']))

            cursor.execute("""
                INSERT INTO historial_rentas (renta_id, accion, descripcion, fecha)
                VALUES (%s, 'pago_consolidado', %s, NOW())
            """, (r['id'], f"Pago consolidado ${pago_renta:.2f} (folio #{folio_compartido:04d})"))

            pagos_generados.append({
                'renta_id': r['id'],
                'folio_renta': r['folio'],
                'monto_aplicado': pago_renta,
                'prefactura_id': prefactura_id,
                'nuevo_estado': nuevo_estado_pago
            })

        # Descontar saldo a favor utilizado
        if usar_saldo_favor and saldo_favor_a_usar > 0:
            usado_real = min(saldo_favor_a_usar, disponible - remanente)
            if usado_real > 0:
                cursor.execute("SELECT sucursal_id FROM clientes WHERE id = %s", (cliente_id,))
                cli = cursor.fetchone()
                sucursal_id = cli['sucursal_id'] if cli else (rentas[0]['id_sucursal'] if rentas else 1)
                cursor.execute("""
                    INSERT INTO saldo_favor_clientes
                        (cliente_id, sucursal_id, tipo, monto, concepto, referencia_tabla, usuario_id)
                    VALUES (%s, %s, 'debito', %s, 'Aplicado en pago consolidado', 'consolidado', %s)
                """, (cliente_id, sucursal_id, usado_real, session.get('user_id')))

        # Remanente → saldo a favor
        if remanente > 0.01:
            cursor.execute("SELECT sucursal_id FROM clientes WHERE id = %s", (cliente_id,))
            cli = cursor.fetchone()
            sucursal_id = cli['sucursal_id'] if cli else (rentas[0]['id_sucursal'] if rentas else 1)
            cursor.execute("""
                INSERT INTO saldo_favor_clientes
                    (cliente_id, sucursal_id, tipo, monto, concepto, referencia_tabla, usuario_id)
                VALUES (%s, %s, 'credito', %s, 'Remanente de pago consolidado', 'consolidado', %s)
            """, (cliente_id, sucursal_id, remanente, session.get('user_id')))

        conn.commit()

        # Registrar ingreso en caja (solo efectivo, fuera de transacción)
        if metodo_pago == 'EFECTIVO' and monto_efectivo > 0:
            monto_caja = monto_efectivo - max(remanente - saldo_favor_a_usar, 0)
            if monto_caja > 0.01:
                try:
                    sucursal_id = rentas[0]['id_sucursal'] if rentas else 1
                    registrar_movimiento_automatico(
                        tipo='ingreso',
                        concepto=f"Pago consolidado cliente #{cliente_id}",
                        monto=round(monto_caja, 2),
                        metodo_pago='EFECTIVO',
                        usuario_id=session.get('user_id'),
                        sucursal_id=sucursal_id,
                        referencia_tabla='clientes',
                        referencia_id=cliente_id
                    )
                except Exception as e:
                    print(f"Error registrando movimiento caja consolidado: {e}")

        return jsonify({
            'success': True,
            'message': f'Pago consolidado aplicado. {len(pagos_generados)} renta(s) procesada(s).',
            'pagos': pagos_generados,
            'saldo_favor_nuevo': round(remanente if remanente > 0.01 else 0, 2),
            'folio': folio_compartido,
            'pdf_url': f'/clientes/pdf-comprobante-consolidado/{cliente_id}?folio={folio_compartido}'
        })

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# PDF ESTADO DE CUENTA
# ─────────────────────────────────────────────────────────────────────────────

@clientes_bp.route('/pdf-estado-cuenta/<int:cliente_id>', methods=['GET'])
@requiere_sesion()
@requiere_permiso('ver_estado_cuenta')
def pdf_estado_cuenta(cliente_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Client info
        cursor.execute("""
            SELECT c.*, s.nombre AS sucursal_nombre, s.plantilla_renta,
                   s.plantilla_cotizacion
            FROM clientes c
            LEFT JOIN sucursales s ON c.sucursal_id = s.id
            WHERE c.id = %s
        """, (cliente_id,))
        cliente = cursor.fetchone()
        if not cliente:
            return "Cliente no encontrado", 404

        # Rentals with pending balance (including finalized-but-unpaid)
        cursor.execute("""
            SELECT r.id, r.folio, r.id_sucursal,
                   r.fecha_salida, r.fecha_programada, r.fecha_entrada,
                   r.estado_renta, r.estado_pago, r.direccion_obra,
                   r.traslado, r.costo_traslado,
                   r.renta_asociada_id,
                   COALESCE(r.renta_asociada_id, r.id) AS raiz_id,
                   COALESCE(
                       (SELECT folio FROM rentas WHERE id = r.renta_asociada_id),
                       r.folio
                   ) AS folio_raiz,
                   COALESCE(r.total_con_iva, r.total, 0) AS total_con_iva,
                   COALESCE(r.total, 0) AS subtotal,
                   COALESCE(r.iva, 0)   AS iva_monto,
                   COALESCE(
                       (SELECT SUM(p.monto) FROM prefacturas p WHERE p.renta_id = r.id AND p.pagada = 1),
                       0
                   ) AS pagado
            FROM rentas r
            WHERE r.cliente_id = %s
              AND r.estado_renta NOT IN ('cancelada')
              AND r.estado_pago NOT IN ('Pago realizado','Cancelado sin pago','Reembolsado','Saldo a favor')
            ORDER BY r.fecha_salida ASC, r.id ASC
        """, (cliente_id,))
        rentas_raw = cursor.fetchall()

        rentas = []
        for r in rentas_raw:
            renta = dict(r)
            renta['total_con_iva'] = float(renta['total_con_iva'])
            renta['subtotal'] = float(renta['subtotal'])
            renta['iva_monto'] = float(renta['iva_monto'])
            renta['pagado'] = float(renta['pagado'])
            renta['saldo_pendiente'] = round(renta['total_con_iva'] - renta['pagado'], 2)
            if renta['saldo_pendiente'] <= 0.50:  # ignorar diferencias de redondeo
                continue

            cursor.execute("""
                SELECT prod.nombre, rd.cantidad, rd.dias_renta, rd.costo_unitario, rd.subtotal
                FROM renta_detalle rd
                JOIN productos prod ON rd.id_producto = prod.id_producto
                WHERE rd.renta_id = %s
            """, (r['id'],))
            renta['productos'] = cursor.fetchall()

            cursor.execute("""
                SELECT folio FROM notas_salida
                WHERE renta_id = %s ORDER BY id DESC LIMIT 1
            """, (r['id'],))
            ns = cursor.fetchone()
            renta['folio_salida'] = ns['folio'] if ns else None

            cursor.execute("""
                SELECT folio FROM notas_entrada
                WHERE renta_id = %s ORDER BY id DESC LIMIT 1
            """, (r['id'],))
            ne = cursor.fetchone()
            renta['folio_entrada'] = ne['folio'] if ne else None

            rentas.append(renta)

        if not rentas:
            return "Este cliente no tiene rentas con saldo pendiente.", 404

        # Agrupar rentas por cadena (original + renovaciones)
        cadenas = {}
        orden_raiz = []
        for r in rentas:
            raiz_id = r['raiz_id']
            if raiz_id not in cadenas:
                cadenas[raiz_id] = {'folio_raiz': r['folio_raiz'], 'eslabones': []}
                orden_raiz.append(raiz_id)
            cadenas[raiz_id]['eslabones'].append(r)

        _ensure_saldo_favor_table(cursor)
        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo='credito' THEN monto ELSE 0 END), 0)
              - COALESCE(SUM(CASE WHEN tipo='debito'  THEN monto ELSE 0 END), 0)
              AS saldo
            FROM saldo_favor_clientes WHERE cliente_id = %s
        """, (cliente_id,))
        row = cursor.fetchone()
        saldo_favor = float(row['saldo']) if row and row['saldo'] else 0.0

        total_adeudo = sum(r['saldo_pendiente'] for r in rentas)
        neto_a_pagar = max(0.0, total_adeudo - saldo_favor)
        plantilla_renta = cliente.get('plantilla_cotizacion') or cliente.get('plantilla_renta')

    finally:
        cursor.close()
        conn.close()

    # Register font
    try:
        font_path = os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Carlito', font_path))
    except Exception:
        pass

    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)

    nombre_completo = f"{cliente['nombre']} {cliente['apellido1']} {cliente.get('apellido2','') or ''}".strip()
    fecha_str = datetime.now().strftime('%d/%m/%Y - %H:%M:%S')

    # ── Título  ──────────────────────────────────────
    can.setFont("Helvetica-Bold", 12)
    can.drawString(25, 719, "ESTADO DE CUENTA")

    can.setFont("Carlito", 10)
    can.drawString(482, 720, fecha_str)

    # ── Datos del cliente ─────────────────────────────────────────────────────
    y = 690
    can.setFont("Helvetica-Bold", 11)
    can.drawString(25, y - 5, "DATOS DEL CLIENTE")
    y -= 20
    can.line(25, y + 12, 580, y + 12)

    can.setFont("Carlito", 10)
    codigo = cliente.get('codigo_cliente') or '—'
    can.drawString(25, y, f"CLIENTE: {codigo} - {nombre_completo.upper()}")
    y -= 13
    can.drawString(25, y, f"TELÉFONO: {cliente.get('telefono') or 'NO REGISTRADO'}")
    y -= 13
    can.drawString(25, y, f"EMAIL: {cliente.get('correo') or 'NO REGISTRADO'}")
    y -= 15

    can.setFont("Carlito", 10)
    can.drawString(25, y,
        "A CONTINUACIÓN SE PRESENTAN LAS RENTAS CON SALDO PENDIENTE DE PAGO:")
    y -= 10

    # ── Encabezado tabla ─────────────────────────────────────────────────────

    def nueva_pagina_ec():
        can.showPage()
        ny = 750
        can.setFont("Helvetica-Bold", 10)
        can.drawString(25, ny, f"ESTADO DE CUENTA — {nombre_completo.upper()} (CONTINUACIÓN)")
        can.setFont("Carlito", 10)
        can.drawString(482, ny, fecha_str)
        can.setStrokeColorRGB(0.14, 0.22, 0.37)
        can.setLineWidth(1)
        can.line(25, ny - 6, 580, ny - 6)
        can.setStrokeColorRGB(0, 0, 0)
        return ny - 20

    # ── Cadenas (original + renovaciones agrupadas) ───────────────────────────
    for raiz_id in orden_raiz:
        cadena = cadenas[raiz_id]
        eslabones = cadena['eslabones']
        folio_raiz = cadena['folio_raiz']

        primer = eslabones[0]
        ultimo = eslabones[-1]

        fecha_inicio = primer['fecha_salida'].strftime('%d/%m/%Y') if primer.get('fecha_salida') else '—'
        if ultimo.get('fecha_entrada'):
            fecha_fin_cadena = ultimo['fecha_entrada'].strftime('%d/%m/%Y')
            lbl_fin_cadena = 'ENTRADA'
        elif ultimo.get('fecha_programada'):
            fecha_fin_cadena = ultimo['fecha_programada'].strftime('%d/%m/%Y')
            lbl_fin_cadena = 'PROG'
        else:
            fecha_fin_cadena = 'EN CURSO'
            lbl_fin_cadena = ''

        total_cadena = sum(e['total_con_iva'] for e in eslabones)
        pagado_cadena = sum(e['pagado'] for e in eslabones)
        saldo_cadena = round(sum(e['saldo_pendiente'] for e in eslabones), 2)

        total_prods = sum(len(e.get('productos', [])) for e in eslabones)
        altura_cadena = 22 + 12 + 14 + len(eslabones) * 13 + total_prods * 10 + 48
        if y - altura_cadena < 180:
            y = nueva_pagina_ec()

        folio_str = f"#{str(folio_raiz).zfill(4)}" if folio_raiz else f"ID {raiz_id}"

        # ── Encabezado de cadena (azul oscuro) ────────────────────────────
        can.setFillColorRGB(0.14, 0.22, 0.37)
        can.rect(25, y - 14, 555, 18, fill=1, stroke=0)
        can.setFillColorRGB(1, 1, 1)
        can.setFont("Helvetica-Bold", 9)
        can.drawString(29, y - 8, f"RENTA {folio_str}")
        can.setFont("Carlito", 9)
        periodo_txt = (f"{fecha_inicio}  →  {lbl_fin_cadena + ': ' if lbl_fin_cadena else ''}{fecha_fin_cadena}")
        can.drawString(106, y - 8, periodo_txt)
        can.setFillColorRGB(0, 0, 0)
        y -= 16

        # Dirección de obra (del último eslabón, o del primero)
        obra = ultimo.get('direccion_obra') or primer.get('direccion_obra')
        if obra:
            can.setFillColorRGB(0.94, 0.94, 0.94)
            can.rect(25, y - 10, 555, 12, fill=1, stroke=0)
            can.setFillColorRGB(0.2, 0.2, 0.2)
            can.setFont("Carlito", 8)
            can.drawString(29, y - 7, f"OBRA: {obra[:90].upper()}")
            can.setFillColorRGB(0, 0, 0)
            y -= 12

        # Encabezado de columnas de la cadena
        can.setFillColorRGB(0.88, 0.88, 0.88)
        can.rect(25, y - 11, 555, 13, fill=1, stroke=0)
        can.setFillColorRGB(0, 0, 0)
        can.setFont("Helvetica-Bold", 8)
        can.drawString(30, y - 8, "DESCRIPCIÓN")
        can.drawRightString(340, y - 8, "CANT.")
        can.drawRightString(390, y - 8, "DÍAS")
        can.drawRightString(468, y - 8, "P. UNIT.")
        can.drawRightString(540, y - 8, "SUBTOTAL")
        y -= 13

        # ── Eslabones (cortes de la cadena) ───────────────────────────────
        for eslabon in eslabones:
            e_folio = f"#{str(eslabon['folio']).zfill(4)}" if eslabon.get('folio') else ''
            e_sal = eslabon['fecha_salida'].strftime('%d/%m/%Y') if eslabon.get('fecha_salida') else '—'
            if eslabon.get('fecha_entrada'):
                e_fin = eslabon['fecha_entrada'].strftime('%d/%m/%Y')
                e_lbl = 'ENTRADA'
            elif eslabon.get('fecha_programada'):
                e_fin = eslabon['fecha_programada'].strftime('%d/%m/%Y')
                e_lbl = 'PROG'
            else:
                e_fin = '—'
                e_lbl = 'PROG'

            if y < 80:
                y = nueva_pagina_ec()

            # Barra de período (azul acero suave)
            can.setFillColorRGB(0.78, 0.85, 0.93)
            can.rect(25, y - 9, 555, 12, fill=1, stroke=0)
            can.setFillColorRGB(0.08, 0.15, 0.30)
            can.setFont("Helvetica-Bold", 8)
            can.drawString(29, y - 6, e_folio)
            can.setFont("Carlito", 8)
            can.drawString(62, y - 6, f"SALIDA: {e_sal}   {e_lbl}: {e_fin}")
            costo_tras_e = float(eslabon.get('costo_traslado') or 0)
            if costo_tras_e > 0:
                tipo_tras_e = (eslabon.get('traslado') or '').upper()
                can.drawRightString(540, y - 6, f"TRASLADO ({tipo_tras_e}): ${costo_tras_e:.2f}")
            can.setFillColorRGB(0, 0, 0)
            y -= 18

            # Productos del eslabón
            can.setFont("Carlito", 8)
            for idx, prod in enumerate(eslabon.get('productos', [])):
                if y < 80:
                    y = nueva_pagina_ec()
                if idx % 2 == 1:
                    can.setFillColorRGB(0.97, 0.97, 0.97)
                    can.rect(25, y - 3, 555, 11, fill=1, stroke=0)
                    can.setFillColorRGB(0, 0, 0)
                can.drawString(30, y, str(prod['nombre'])[:42].upper())
                can.drawRightString(340, y, str(prod['cantidad']))
                can.drawRightString(390, y, str(prod.get('dias_renta') or '—'))
                can.drawRightString(468, y, f"${float(prod.get('costo_unitario', 0)):.2f}")
                can.drawRightString(540, y, f"${float(prod.get('subtotal', 0)):.2f}")
                y -= 10

        # ── Totales de la cadena ───────────────────────────────────────────
        y -= 2
        can.setStrokeColorRGB(0.65, 0.65, 0.65)
        can.line(330, y + 2, 555, y + 2)
        can.setStrokeColorRGB(0, 0, 0)
        y -= 5

        can.setFont("Carlito", 8)
        can.setFillColorRGB(0.35, 0.35, 0.35)
        can.drawRightString(468, y, "TOTAL CADENA:")
        can.setFillColorRGB(0, 0, 0)
        can.drawRightString(540, y, f"${total_cadena:.2f}")
        y -= 10

        can.setFont("Carlito", 8)
        can.setFillColorRGB(0.35, 0.35, 0.35)
        can.drawRightString(468, y, "PAGADO:")
        can.setFillColorRGB(0, 0.45, 0)
        can.drawRightString(540, y, f"${pagado_cadena:.2f}")
        can.setFillColorRGB(0, 0, 0)
        y -= 10

        can.setFillColorRGB(0.96, 0.88, 0.88)
        can.rect(330, y - 4, 225, 14, fill=1, stroke=0)
        can.setFillColorRGB(0.65, 0, 0)
        can.setFont("Helvetica-Bold", 9)
        can.drawRightString(468, y, "SALDO PENDIENTE:")
        can.drawRightString(540, y, f"${saldo_cadena:.2f}")
        can.setFillColorRGB(0, 0, 0)
        y -= 14


    # ── Resumen general ───────────────────────────────────────────────────────
    if y < 160:
        y = nueva_pagina_ec()

    can.setStrokeColorRGB(0.14, 0.22, 0.37)
    can.setLineWidth(1.5)
    can.line(25, y + 6, 580, y + 6)
    can.setStrokeColorRGB(0, 0, 0)
    can.setLineWidth(1)
    y -= 7

    can.setFont("Carlito", 10)
    can.drawRightString(465, y, "TOTAL ADEUDADO:")
    can.drawRightString(545, y, f"${total_adeudo:.2f}")
    y -= 15
    if saldo_favor > 0:
        can.setFillColorRGB(0, 0.5, 0)
        can.drawRightString(465, y, "SALDO A FAVOR:")
        can.drawRightString(545, y, f"-${saldo_favor:.2f}")
        can.setFillColorRGB(0, 0, 0)
        y -= 15
    can.setFont("Helvetica-Bold", 11)
    can.drawRightString(465, y, "NETO A PAGAR:")
    can.drawRightString(545, y, f"${neto_a_pagar:.2f}")
    y -= 10

    # ── Footer (igual que cotizaciones) ──────────────────────────────────────
    espacio_necesario = 120
    if y < espacio_necesario:
        can.showPage()
        y = 750

    can.setFont("Helvetica-Bold", 8)
    can.drawString(50, y, "* TODOS NUESTROS EQUIPOS CUENTAN CON CERTIFICADOS DE SEGURIDAD")
    y -= 10
    can.drawString(50, y, "* LOS ANDAMIOS TIENEN CERTIFICACIÓN QUE CUMPLE CON LA NOM-009-STPS")
    y -= 15

    can.setFont("Helvetica-Bold", 8)
    can.drawString(50, y, "MÉTODOS DE PAGO Y FACTURACIÓN:")
    y -= 10
    can.setFont("Carlito", 8)
    can.drawString(60, y, "• EFECTIVO, TRANSFERENCIA BANCARIA, TARJETAS DE DÉBITO Y CRÉDITO")
    y -= 10
    can.drawString(60, y, "• CONTAMOS CON FACTURACIÓN ELECTRÓNICA")
    y -= 10

    can.setFont("Helvetica-Bold", 8)
    can.drawString(50, y, "CONDICIONES:")
    y -= 10
    can.setFont("Carlito", 8)
    for cond in [
        "• SE REQUIERE EL PAGO COMPLETO POR ADELANTADO",
        "• EL PERÍODO INCLUYE DOMINGOS Y DÍAS FESTIVOS",
        "• NO SE ARMA, NI SE DESARMA EL EQUIPO",
    ]:
        can.drawString(60, y, cond)
        y -= 10

    y -= 5
    can.setFont("Helvetica-Bold", 8)
    can.drawString(50, y, "DATOS BANCARIOS:")
    y -= 10
    can.setFont("Carlito", 8)
    can.drawString(60, y, "CUENTA: JAVIER ENRIQUE ALCOCER BERNES")
    y -= 10
    can.drawString(60, y, "• BANCO: BANORTE   • CTA: 0659076153   • CLABE: 072050006590761530")
    y -= 10
    can.drawString(60, y, "• R.F.C: AOBJ650602UE1   • EMAIL: puntalesyandamioscolosio@hotmail.com")
    y -= 24

    can.line(25, y + 18, 580, y + 18)
    y -= 1
    can.setFont("Helvetica-Bold", 9)
    can.drawString(173, y, "ATENDIDO POR: ING. JAVIER ENRIQUE ALCOCER BERNES")
    y -= 12
    can.drawString(135, y, "GERENTE DE ANDAMIOS COLOSIO DEL ESTADO DE CAMPECHE, CAMPECHE")
    y -= 15
    can.setFont("Helvetica-Bold", 10)
    can.drawString(160, y, "VISITE NUESTRA PÁGINA: WWW.ANDAMIOSCOLOSIO.COM")

    can.save()
    packet.seek(0)

    # Overlay on branch template
    try:
        plantilla_path = None
        if plantilla_renta:
            plantilla_path = os.path.join(current_app.root_path, plantilla_renta)
            if not os.path.exists(plantilla_path):
                plantilla_path = None
        if not plantilla_path:
            plantilla_path = os.path.join(current_app.root_path, 'static/notas/base.pdf')

        overlay_pdf = PdfReader(packet)
        output = PdfWriter()
        if os.path.exists(plantilla_path):
            plantilla_pdf = PdfReader(plantilla_path)
            template_pg = plantilla_pdf.pages[0]
            for i, op in enumerate(overlay_pdf.pages):
                if i == 0:
                    template_pg.merge_page(op)
                    output.add_page(template_pg)
                else:
                    output.add_page(op)
        else:
            for p in overlay_pdf.pages:
                output.add_page(p)
    except Exception as e:
        print(f"Error combinando plantilla estado cuenta: {e}")
        overlay_pdf = PdfReader(packet)
        output = PdfWriter()
        for p in overlay_pdf.pages:
            output.add_page(p)

    out_stream = BytesIO()
    output.write(out_stream)
    out_stream.seek(0)
    nombre_archivo = f"estado_cuenta_{cliente_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    return send_file(out_stream, download_name=nombre_archivo, mimetype='application/pdf')


# ─────────────────────────────────────────────────────────────────────────────
# PDF COMPROBANTE DE PAGO CONSOLIDADO (post-pago)
# ─────────────────────────────────────────────────────────────────────────────

@clientes_bp.route('/api/historial-consolidados/<int:cliente_id>', methods=['GET'])
@requiere_sesion()
def historial_consolidados(cliente_id):
    """
    Devuelve los pagos consolidados del cliente agrupados por fecha y conjunto
    de prefacturas generadas el mismo segundo (misma operación).
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT p.id, p.folio, p.monto, p.metodo_pago, p.fecha_emision,
                   r.folio AS folio_renta, r.id AS renta_id
            FROM prefacturas p
            JOIN rentas r ON p.renta_id = r.id
            WHERE r.cliente_id = %s AND p.tipo = 'abono'
            ORDER BY p.folio DESC, p.id DESC
            LIMIT 100
        """, (cliente_id,))
        rows = cursor.fetchall()

        # Agrupar por folio compartido (todas las prefacturas de una consolidación
        # comparten el mismo folio consecutivo).
        from collections import OrderedDict
        grupos = OrderedDict()
        for row in rows:
            key = row['folio']
            if key not in grupos:
                grupos[key] = {
                    'folio': row['folio'],
                    'fecha': row['fecha_emision'].strftime('%d/%m/%Y %H:%M') if row['fecha_emision'] else '',
                    'metodo_pago': row['metodo_pago'],
                    'total': 0.0,
                    'rentas': []
                }
            grupos[key]['total'] += float(row['monto'])
            grupos[key]['rentas'].append(
                f"#{str(row['folio_renta']).zfill(4)}" if row['folio_renta'] else f"ID {row['renta_id']}"
            )

        resultado = []
        for key, g in grupos.items():
            resultado.append({
                'folio': g['folio'],
                'fecha': g['fecha'],
                'metodo_pago': g['metodo_pago'],
                'total': round(g['total'], 2),
                'rentas': list(dict.fromkeys(g['rentas'])),
                'pdf_url': f'/clientes/pdf-comprobante-consolidado/{cliente_id}?folio={g["folio"]}'
            })

        return jsonify({'success': True, 'historial': resultado})
    finally:
        cursor.close()
        conn.close()


@clientes_bp.route('/pdf-comprobante-consolidado/<int:cliente_id>', methods=['GET'])
@requiere_sesion()
@requiere_permiso('consolidar_pago')
def pdf_comprobante_consolidado(cliente_id):
    """
    Genera un comprobante de pago consolidado.
    Acepta ?folio=N (preferido) o ?ids=1,2,3 (compatibilidad hacia atrás).
    Todas las prefacturas de una consolidación comparten el mismo folio.
    """
    folio_param = request.args.get('folio', '').strip()
    ids_raw = request.args.get('ids', '')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Client info
        cursor.execute("""
            SELECT c.*, s.nombre AS sucursal_nombre, s.plantilla_renta
            FROM clientes c LEFT JOIN sucursales s ON c.sucursal_id = s.id
            WHERE c.id = %s
        """, (cliente_id,))
        cliente = cursor.fetchone()
        if not cliente:
            return "Cliente no encontrado", 404

        # Prefacturas + renta info
        if folio_param.isdigit():
            folio_num = int(folio_param)
            cursor.execute("""
                SELECT p.id, p.folio, p.monto, p.metodo_pago, p.numero_seguimiento,
                       p.fecha_emision, p.tipo,
                       r.id AS renta_id, r.folio AS folio_renta,
                       r.fecha_salida, r.fecha_programada, r.fecha_entrada,
                       r.direccion_obra,
                       COALESCE(r.total_con_iva, r.total, 0) AS total_renta,
                       COALESCE(
                           (SELECT SUM(pp.monto) FROM prefacturas pp WHERE pp.renta_id = r.id AND pp.pagada = 1),
                           0
                       ) AS total_pagado_renta
                FROM prefacturas p
                JOIN rentas r ON p.renta_id = r.id
                WHERE p.folio = %s AND r.cliente_id = %s AND p.tipo = 'abono'
                ORDER BY r.fecha_salida ASC, p.id ASC
            """, (folio_num, cliente_id))
        elif ids_raw:
            try:
                prefactura_ids = [int(x) for x in ids_raw.split(',') if x.strip().isdigit()]
            except ValueError:
                return "IDs inválidos", 400
            if not prefactura_ids:
                return "No se especificaron prefacturas", 400
            fmt_ids = ','.join(['%s'] * len(prefactura_ids))
            cursor.execute(f"""
                SELECT p.id, p.folio, p.monto, p.metodo_pago, p.numero_seguimiento,
                       p.fecha_emision, p.tipo,
                       r.id AS renta_id, r.folio AS folio_renta,
                       r.fecha_salida, r.fecha_programada, r.fecha_entrada,
                       r.direccion_obra,
                       COALESCE(r.total_con_iva, r.total, 0) AS total_renta,
                       COALESCE(
                           (SELECT SUM(pp.monto) FROM prefacturas pp WHERE pp.renta_id = r.id AND pp.pagada = 1),
                           0
                       ) AS total_pagado_renta
                FROM prefacturas p
                JOIN rentas r ON p.renta_id = r.id
                WHERE p.id IN ({fmt_ids})
                ORDER BY r.fecha_salida ASC, p.id ASC
            """, prefactura_ids)
            folio_num = None
        else:
            return "Debe especificar ?folio=N o ?ids=...", 400

        filas = cursor.fetchall()
        if not filas:
            return "No se encontraron prefacturas", 404
        folio_num = filas[0]['folio'] if filas[0].get('folio') else folio_num

        plantilla_renta = cliente.get('plantilla_renta')
        monto_total = sum(float(f['monto']) for f in filas)
        fecha_pago = filas[0]['fecha_emision']
        metodo_pago = filas[0]['metodo_pago']

        # Nombre del usuario para firma
        usuario_nombre = "USUARIO NO IDENTIFICADO"
        usuario_id = session.get('user_id')
        if usuario_id:
            cursor.execute("""
                SELECT CONCAT(nombre, ' ', apellido1, ' ', apellido2) AS nombre_completo
                FROM usuarios WHERE id = %s
            """, (usuario_id,))
            u = cursor.fetchone()
            if u:
                usuario_nombre = u['nombre_completo'].upper()

    finally:
        cursor.close()
        conn.close()

    # Register font
    try:
        font_path = os.path.join(current_app.root_path, 'static/fonts/Carlito-Regular.ttf')
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Carlito', font_path))
    except Exception:
        pass

    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)

    nombre_completo = f"{cliente['nombre']} {cliente['apellido1']} {cliente.get('apellido2','') or ''}".strip()
    fecha_str = fecha_pago.strftime('%d/%m/%Y - %H:%M:%S') if fecha_pago else datetime.now().strftime('%d/%m/%Y - %H:%M:%S')

    # ── Título (igual que prefactura) ────────────────────────────────────────
    can.setFont("Courier-Bold", 15)
    can.drawString(490, 732, "PREFACTURA")

    # ── Fecha y folio (derecha, igual que prefactura) ─────────────────────────
    can.setFont("Carlito", 12)
    can.drawRightString(575, 715, fecha_str)
    can.setFont("Courier-Bold", 20)
    if folio_num:
        can.drawRightString(575, 690, f"#{folio_num:04d}")

    # ── Bloque de cliente (izquierda, igual que prefactura) ───────────────────
    y_cliente = 715
    can.setFont("Carlito", 10)

    can.drawString(36, y_cliente, f"CLIENTE: {cliente.get('codigo_cliente','—')} - {nombre_completo.upper()}")
    y_cliente -= 13
    can.drawString(36, y_cliente, f"TELÉFONO: {cliente.get('telefono') or 'NO REGISTRADO'}")
    y_cliente -= 13
    can.drawString(36, y_cliente, f"CORREO: {cliente.get('correo') or 'NO REGISTRADO'}")
    y_cliente -= 13

    # Dirección
    dir_completa = cliente.get('calle') or ''
    if cliente.get('numero_exterior'):
        dir_completa += f" #{cliente['numero_exterior']}"
    if cliente.get('numero_interior'):
        dir_completa += f", INT. {cliente['numero_interior']}"
    if cliente.get('entre_calles'):
        dir_completa += f" (ENTRE {cliente['entre_calles']})"
    if cliente.get('colonia'):
        dir_completa += f", COL. {cliente['colonia']}"
    if cliente.get('codigo_postal'):
        dir_completa += f" - C.P. {cliente['codigo_postal']}"
    for line in simpleSplit(f"DIRECCIÓN: {dir_completa.upper()}", "Carlito", 10, 390):
        can.drawString(36, y_cliente, line)
        y_cliente -= 13

    can.drawString(36, y_cliente, f"ESTADO: {(cliente.get('estado') or 'NO REGISTRADO').upper()}")
    can.drawString(290, y_cliente, f"MUNICIPIO: {(cliente.get('municipio') or 'NO REGISTRADO').upper()}")
    y_cliente -= 13
    can.drawString(36, y_cliente, f"RFC: {(cliente.get('rfc') or 'NO REGISTRADO').upper()}")
    can.drawString(290, y_cliente, f"SUCURSAL: {(cliente.get('sucursal_nombre') or '').upper()}")
    y_cliente -= 20

    # ── Tabla de rentas ───────────────────────────────────────────────────────
    y_tabla = y_cliente - 5

    can.line(28, y_tabla + 20, 585, y_tabla + 20)
    can.setFont("Helvetica-Bold", 9)
    can.drawString(36, y_tabla + 10, "FOLIO RENTA")
    can.drawString(110, y_tabla + 10, "SALIDA")
    can.drawString(178, y_tabla + 10, "ENTRADA")
    can.drawString(246, y_tabla + 10, "DIRECCIÓN OBRA")
    can.drawRightString(460, y_tabla + 10, "TOTAL RENTA")
    can.drawRightString(570, y_tabla + 10, "ABONO")
    can.line(28, y_tabla + 5, 585, y_tabla + 5)
    y_tabla -= 15

    can.setFont("Carlito", 9)
    for f in filas:
        if y_tabla < 300:
            break
        folio_r = f"#{str(f['folio_renta']).zfill(4)}" if f['folio_renta'] else f"ID {f['renta_id']}"
        fecha_sal = f['fecha_salida'].strftime('%d/%m/%Y') if f.get('fecha_salida') else '—'
        # Usar fecha_entrada real; si no tiene, mostrar fecha_programada
        fecha_fin = (f['fecha_entrada'].strftime('%d/%m/%Y') if f.get('fecha_entrada')
                     else (f['fecha_programada'].strftime('%d/%m/%Y') if f.get('fecha_programada') else '—'))
        obra = (f.get('direccion_obra') or '—')[:22]
        total_r = float(f['total_renta'])
        total_pg = float(f['total_pagado_renta'])

        can.drawString(36, y_tabla + 5, folio_r)
        can.drawString(110, y_tabla + 5, fecha_sal)
        can.drawString(178, y_tabla + 5, fecha_fin)
        can.drawString(246, y_tabla + 5, obra)
        can.drawRightString(460, y_tabla + 5, f"${total_r:.2f}")
        can.drawRightString(570, y_tabla + 5, f"${float(f['monto']):.2f}")
        y_tabla -= 13
    y_tabla -= 5

    # ── Totales ───────────────────────────────────────────────────────────────
    can.line(28, y_tabla + 15, 585, y_tabla + 15)
    y_totales = y_tabla + 10 - 10

    can.setFont("Helvetica-Bold", 9)
    can.drawString(400, y_totales, "TOTAL PAGADO:")
    can.drawRightString(570, y_totales, f"${monto_total:.2f}")
    y_totales -= 12

    # Método(s) de pago
    metodos_unicos = list(dict.fromkeys(f['metodo_pago'] for f in filas))
    can.setFont("Carlito", 10)
    can.drawString(400, y_totales, "MÉTODO DE PAGO:")
    can.drawRightString(570, y_totales, ' / '.join(metodos_unicos))
    y_totales -= 12

    seguimientos = list({f['numero_seguimiento'] for f in filas if f.get('numero_seguimiento')})
    if seguimientos:
        can.drawString(400, y_totales, "SEGUIMIENTO:")
        can.drawRightString(570, y_totales, seguimientos[0][:20])
        y_totales -= 12

    # ── Avisos (igual que prefactura) ────────────────────────────────────────
    y_avisos = y_totales - 6
    can.line(28, y_avisos + 16, 585, y_avisos + 16)
    y_avisos -= 5

    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y_avisos, "REQUISITOS DEL CLIENTE:")
    y_avisos -= 12
    can.setFont("Carlito", 8)
    can.drawString(60, y_avisos, "LOS SIGUIENTES DOCUMENTOS PUEDEN SER EN IMAGEN O EN COPIA IMPRESA:")
    y_avisos -= 12
    can.drawString(70, y_avisos, "• IDENTIFICACIÓN OFICIAL.")
    y_avisos -= 10
    can.drawString(70, y_avisos, "• LICENCIA DE CONDUCIR.")
    y_avisos -= 10
    can.drawString(70, y_avisos, "• CONSTANCIA DE SITUACIÓN FISCAL.")
    y_avisos -= 10
    can.drawString(70, y_avisos, "• COMPROBANTE DE DOMICILIO.")
    y_avisos -= 15

    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y_avisos, "REQUISITOS DE RENTA:")
    y_avisos -= 11
    can.setFont("Carlito", 8)
    can.drawString(70, y_avisos, "• SE REQUIERE EL PAGO COMPLETO POR ADELANTADO DE LA RENTA.")
    y_avisos -= 10
    can.drawString(70, y_avisos, "• UBICACIÓN EXACTA DE LA OBRA (POR GOOGLE MAPS)")
    y_avisos -= 15

    can.setFont("Helvetica-Bold", 10)
    can.drawString(60, y_avisos, "¡IMPORTANTE!")
    y_avisos -= 11
    can.setFont("Carlito", 8)
    can.drawString(70, y_avisos, "• EL PERIODO DE RENTA INCLUYE DOMINGOS, DÍAS INHÁBILES Y FESTIVOS.")
    y_avisos -= 10
    can.drawString(70, y_avisos, "• NO SE ARMA, NI SE DESARMA EL EQUIPO.")
    y_avisos -= 10

    # ── Firma ─────────────────────────────────────────────────────────────────
    can.setFont("Carlito", 10)
    can.line(60, y_avisos, 250, y_avisos)
    y_avisos -= 15
    can.drawString(60, y_avisos, f"ATENDIDO POR: {usuario_nombre}")

    can.save()
    packet.seek(0)

    # Overlay on template
    try:
        plantilla_path = None
        if plantilla_renta:
            plantilla_path = os.path.join(current_app.root_path, plantilla_renta)
            if not os.path.exists(plantilla_path):
                plantilla_path = None
        if not plantilla_path:
            plantilla_path = os.path.join(current_app.root_path, 'static/notas/base.pdf')

        overlay_pdf = PdfReader(packet)
        output = PdfWriter()
        if os.path.exists(plantilla_path):
            plantilla_pdf = PdfReader(plantilla_path)
            tp = plantilla_pdf.pages[0]
            for i, op in enumerate(overlay_pdf.pages):
                if i == 0:
                    tp.merge_page(op)
                    output.add_page(tp)
                else:
                    output.add_page(op)
        else:
            for p in overlay_pdf.pages:
                output.add_page(p)
    except Exception as e:
        print(f"Error plantilla comprobante: {e}")
        overlay_pdf = PdfReader(packet)
        output = PdfWriter()
        for p in overlay_pdf.pages:
            output.add_page(p)

    out_stream = BytesIO()
    output.write(out_stream)
    out_stream.seek(0)
    nombre_archivo = f"comprobante_pago_{cliente_id}_{datetime.now().strftime('%Y%m%d%H%M')}.pdf"
    return send_file(out_stream, download_name=nombre_archivo, mimetype='application/pdf')

    return render_template('clientes/nuevo_cliente.html', sucursales=sucursales)