// Reutiliza los modales existentes de "Nueva Renta" y "Renovar Renta" para la edición,
// bloqueando los campos que no se pueden modificar en lugar de construir un modal aparte.
document.addEventListener('DOMContentLoaded', function () {
    let modoEdicionRentaId = null; // null = el modal de Nueva Renta está en modo creación

    const formNuevaRenta = document.getElementById('form-nueva-renta');
    const modalNuevaRentaEl = document.getElementById('modalNuevaRenta');
    const tituloNuevaRenta = document.getElementById('modalNuevaRentaLabel');
    const btnGuardarRenta = document.getElementById('btn-guardar-renta');

    if (!formNuevaRenta || !modalNuevaRentaEl) return;

    function restaurarBotonGuardar() {
        btnGuardarRenta.disabled = false;
        btnGuardarRenta.innerHTML = modoEdicionRentaId
            ? '<i class="bi bi-check2-circle me-2"></i>Guardar Cambios'
            : '<i class="bi bi-check2-circle me-2"></i>Guardar Renta';
    }

    function resetModalNuevaRentaACreacion() {
        modoEdicionRentaId = null;
        if (tituloNuevaRenta) tituloNuevaRenta.innerHTML = '<i class="bi bi-plus-circle me-2"></i>Nueva Renta';
        if (btnGuardarRenta) btnGuardarRenta.innerHTML = '<i class="bi bi-check2-circle me-2"></i>Guardar Renta';
        if (window.jQuery) $('#cliente_id').prop('disabled', false);
        const selectSucursal = document.getElementById('id_sucursal');
        if (selectSucursal && selectSucursal.tagName === 'SELECT') {
            selectSucursal.disabled = false;
        }
    }

    function construirFilaProductoExistente(p) {
        const tbody = document.querySelector('#tabla-productos tbody');
        const option = document.querySelector(`#producto_select option[value="${p.id_producto}"]`);
        const nombre = option ? option.textContent : 'Producto';
        const costo = parseFloat(p.costo_unitario) || 0;
        const precioBase = parseFloat(p.precio_base) || costo;
        const ajusteTipo = p.ajuste_tipo || 'ninguno';
        const ajusteValor = parseFloat(p.ajuste_valor) || 0;
        const subtotal = p.cantidad * p.dias_renta * costo;
        const puedeAjustar = window.puedeAjustarPrecios || false;

        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <input type="hidden" name="producto_id[]" value="${p.id_producto}">
                ${nombre}
            </td>
            <td><input type="number" name="cantidad[]" class="form-control form-control-sm cantidad" min="1" value="${p.cantidad}"></td>
            <td><input type="number" name="dias_renta[]" class="form-control form-control-sm dias" min="1" value="${p.dias_renta}" readonly></td>
            <td>
                <input type="number" class="form-control form-control-sm precio-base" step="0.01" min="0" value="${precioBase.toFixed(2)}" readonly>
                <input type="hidden" name="precio_base[]" value="${precioBase.toFixed(2)}">
            </td>
            <td>
                <select class="form-select form-select-sm ajuste-tipo" name="ajuste_tipo[]" ${puedeAjustar ? '' : 'disabled'}>
                    <option value="ninguno" ${ajusteTipo === 'ninguno' ? 'selected' : ''}>S/A</option>
                    <option value="porcentaje" ${ajusteTipo === 'porcentaje' ? 'selected' : ''}>%</option>
                    <option value="fijo" ${ajusteTipo === 'fijo' ? 'selected' : ''}>$</option>
                </select>
            </td>
            <td><input type="number" name="ajuste_valor[]" class="form-control form-control-sm ajuste-valor" step="0.01" value="${ajusteValor}" ${ajusteTipo === 'ninguno' ? 'disabled' : ''}></td>
            <td><input type="number" name="costo_unitario[]" class="form-control form-control-sm costo" step="0.01" min="0" value="${costo.toFixed(2)}" readonly></td>
            <td><input type="number" class="form-control form-control-sm subtotal" step="0.01" min="0" value="${subtotal.toFixed(2)}" readonly></td>
            <td><button type="button" class="btn btn-danger btn-sm btn-eliminar-producto"><i class="bi bi-trash"></i></button></td>
        `;
        tbody.appendChild(row);
    }

    function abrirModalEditarRentaOriginal(rentaId, info) {
        modoEdicionRentaId = rentaId;
        if (tituloNuevaRenta) tituloNuevaRenta.innerHTML = '<i class="bi bi-pencil me-2"></i>Editar Renta';
        if (btnGuardarRenta) btnGuardarRenta.innerHTML = '<i class="bi bi-check2-circle me-2"></i>Guardar Cambios';

        // Cliente y sucursal no son editables
        if (window.jQuery) $('#cliente_id').prop('disabled', true);
        const selectSucursal = document.getElementById('id_sucursal');
        if (selectSucursal && selectSucursal.tagName === 'SELECT') {
            selectSucursal.value = info.id_sucursal;
            selectSucursal.disabled = true;
        }

        document.getElementById('fecha_salida').value = info.fecha_salida || '';
        document.getElementById('fecha_entrada').value = info.fecha_entrada || '';
        document.getElementById('direccion_obra').value = info.direccion_obra || '';
        document.getElementById('observaciones').value = info.observaciones || '';
        document.getElementById('traslado').value = info.traslado || 'ninguno';
        document.getElementById('costo_traslado').value = info.costo_traslado || 0;

        const tieneFechaProgramada = !!info.fecha_programada;
        document.getElementById('renta_programada').checked = tieneFechaProgramada;
        document.getElementById('fecha_programada').value = info.fecha_programada || '';
        document.getElementById('fecha_programada_group').style.display = tieneFechaProgramada ? '' : 'none';
        document.getElementById('costo_traslado_group').style.display =
            (info.traslado && info.traslado !== 'ninguno') ? '' : 'none';

        document.querySelector('#tabla-productos tbody').innerHTML = '';
        (info.productos || []).forEach(p => construirFilaProductoExistente(p));
        document.getElementById('mensaje_sin_productos').style.display = (info.productos || []).length ? 'none' : 'block';

        const labelTraslado = document.getElementById('tipo_traslado_label');
        if (labelTraslado) {
            labelTraslado.textContent =
                info.traslado === 'medio_ida' ? '(Medio - Ida)' :
                info.traslado === 'medio_regreso' ? '(Medio - Regreso)' :
                info.traslado === 'redondo' ? '(Redondo)' : '(Ninguno)';
        }

        // Reutiliza el recálculo de subtotales/totales que ya escucha rentas.js sobre la tabla
        document.querySelectorAll('#tabla-productos .cantidad').forEach(input => {
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });

        bootstrap.Modal.getOrCreateInstance(modalNuevaRentaEl).show();
    }

    // Cuando estamos editando, interceptamos el submit para mandarlo como edición (JSON)
    // en vez de la creación normal (POST de formulario tradicional).
    formNuevaRenta.addEventListener('submit', async function (e) {
        if (!modoEdicionRentaId) return; // modo creación: deja que el form se envíe normal

        e.preventDefault();
        btnGuardarRenta.disabled = true;
        btnGuardarRenta.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...';

        const productos = [];
        document.querySelectorAll('#tabla-productos tbody tr').forEach(fila => {
            productos.push({
                id_producto: fila.querySelector('input[name="producto_id[]"]').value,
                cantidad: fila.querySelector('.cantidad').value,
                dias_renta: fila.querySelector('.dias').value || 1,
                costo_unitario: fila.querySelector('.costo').value,
                precio_base: fila.querySelector('.precio-base').value,
                ajuste_tipo: fila.querySelector('.ajuste-tipo').value,
                ajuste_valor: fila.querySelector('.ajuste-valor').value
            });
        });

        if (productos.length === 0) {
            Swal.fire('Atención', 'Agrega al menos un producto a la renta.', 'warning');
            restaurarBotonGuardar();
            return;
        }

        const payload = {
            fecha_salida: document.getElementById('fecha_salida').value,
            fecha_entrada: document.getElementById('fecha_entrada').value || null,
            fecha_programada: document.getElementById('renta_programada').checked
                ? (document.getElementById('fecha_programada').value || null) : null,
            direccion_obra: document.getElementById('direccion_obra').value,
            observaciones: document.getElementById('observaciones').value,
            traslado: document.getElementById('traslado').value,
            costo_traslado: document.getElementById('costo_traslado').value || 0,
            productos
        };

        try {
            const res = await fetch(`/rentas/editar/${modoEdicionRentaId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const json = await res.json();
            if (json.status === 'ok') {
                Swal.fire({
                    title: '¡Listo!',
                    text: json.mensaje,
                    icon: 'success',
                    confirmButtonText: 'Entendido'
                }).then(() => window.location.reload());
            } else {
                Swal.fire('Error', json.mensaje || 'No se pudo guardar la edición.', 'error');
                restaurarBotonGuardar();
            }
        } catch (err) {
            Swal.fire('Error', 'Error inesperado al guardar los cambios.', 'error');
            restaurarBotonGuardar();
        }
    });

    modalNuevaRentaEl.addEventListener('hidden.bs.modal', function () {
        if (modoEdicionRentaId) {
            resetModalNuevaRentaACreacion();
            formNuevaRenta.reset();
            document.querySelector('#tabla-productos tbody').innerHTML = '';
        }
    });

    // ===================== Punto de entrada: botón "Editar renta" =====================
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-editar-renta');
        if (!btn) return;

        const rentaId = btn.dataset.rentaId;
        fetch(`/rentas/info_editar/${rentaId}`)
            .then(resp => resp.json())
            .then(data => {
                if (data.status !== 'ok') {
                    Swal.fire('No se puede editar', data.mensaje || 'Esta renta ya no se puede editar.', 'warning');
                    return;
                }
                const info = data.info;
                if (info.tipo === 'renovacion') {
                    if (window.abrirModalEditarRenovacion) {
                        window.abrirModalEditarRenovacion(rentaId);
                    }
                } else {
                    abrirModalEditarRentaOriginal(rentaId, info);
                }
            })
            .catch(() => {
                Swal.fire('Error', 'No se pudo obtener la información de la renta.', 'error');
            });
    });
});
