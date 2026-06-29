# Al inicio del archivo, agregar:
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, session
from utils.db import get_db_connection
from werkzeug.utils import secure_filename
import os
import requests
from utils.datetime_utils import get_local_now, format_date_local
from utils.decorators import requiere_sesion, requiere_permiso
from services.cliente_service import ClienteService
from services.renta_service import RentasService

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