document.addEventListener('DOMContentLoaded', function () {
    let rentaIdRenovacionActual = null;
    let pendientesRenovacion = [];
    let formularioEnviandose = false;

    // Abrir modal de renovación y cargar pendientes
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-renovacion-pendientes');
        if (btn) {
            rentaIdRenovacionActual = btn.dataset.rentaId;
            cargarPendientesRenovacion(rentaIdRenovacionActual);
        }
    });

    function cargarPendientesRenovacion(rentaId) {
        fetch(`/rentas/api/rentas_pendientes/${rentaId}`)
            .then(resp => resp.json())
            .then(data => {
                pendientesRenovacion = data.pendientes || [];
                llenarModalRenovacion(data, pendientesRenovacion);
                // Guardar los precios originales en la estructura de pendientes
                if (Array.isArray(pendientesRenovacion)) {
                    pendientesRenovacion.forEach((p, idx) => {
                        // Obtener el precio original desde la API si está disponible
                        if (data.productos && Array.isArray(data.productos)) {
                            const prod = data.productos.find(pr => pr.id_producto === p.producto_id);
                            if (prod && prod.costo_unitario !== undefined) {
                                p.costo_unitario = prod.costo_unitario;
                            }
                        }
                    });
                }
                mostrarTablaPendientesRenovacion(pendientesRenovacion);
                const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalRenovacionPendientes'));
                modal.show();
            })
            .catch(() => {
                Swal.fire('Error', 'No se pudieron cargar los productos pendientes.', 'error');
            });
    }

    function mostrarTablaPendientesRenovacion(pendientes) {
        const tbody = document.getElementById('tabla-pendientes-renovacion');
        tbody.innerHTML = '';
        const dias = 1; // Puedes calcular los días si tienes fechas
        pendientes.forEach(p => {
            const cantidad = Number(p.cantidad_pendiente) || 1;
            const precio = p.costo_unitario !== undefined ? parseFloat(p.costo_unitario) : 0;
            const subtotal = cantidad * dias * precio;
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><input type="hidden" name="producto_id[]" value="${p.producto_id}">${p.nombre_producto}</td>
                <td><input type="number" name="cantidad[]" class="form-control cantidad" min="1" value="${cantidad}"></td>
                <td><input type="number" name="dias_renta[]" class="form-control dias" min="1" value="${dias}" readonly></td>
                <td><input type="number" name="costo_unitario[]" class="form-control costo" step="0.01" min="0" value="${precio.toFixed(2)}" readonly data-fijo="1"></td>
                <td><input type="number" class="form-control subtotal" step="0.01" min="0" value="${subtotal.toFixed(2)}" readonly></td>
            `;
            tbody.appendChild(tr);
        });
    }

    function llenarModalRenovacion(data, pendientes) {
        document.getElementById('direccion-obra-renovacion').value = data.direccion_obra || '';
        document.getElementById('fecha-salida-renovacion').value = '';
        document.getElementById('fecha-entrada-renovacion').value = '';
        document.getElementById('traslado-extra-renovacion').value = 'ninguno';
        document.getElementById('costo-traslado-renovacion').value = '';
        document.getElementById('factura-legal-renovacion').value = '0';

        let html = '';
        if (pendientes.length > 0) {
            pendientes.forEach(p => {
                html += `
                    <div class="mb-2 border rounded p-2">
                        <b>${p.nombre_producto || ''}</b> - Pieza: ${p.nombre_pieza || ''} <br>
                        <span class="badge bg-warning">Pendientes: ${p.cantidad_pendiente}</span>
                    </div>
                `;
            });
        } else {
            html = '<div class="text-muted">No hay productos/piezas pendientes.</div>';
        }
        document.getElementById('lista-pendientes-renovacion').innerHTML = html;
    }

    // Mostrar/ocultar costo traslado extra
    document.getElementById('traslado-extra-renovacion').addEventListener('change', function () {
        const group = document.getElementById('costo-traslado-group-renovacion');
        if (this.value !== 'ninguno') {
            group.style.display = 'block';
        } else {
            group.style.display = 'none';
            document.getElementById('costo-traslado-renovacion').value = '';
        }
    });

    // Enviar renovación
    document.getElementById('form-renovacion-pendientes').addEventListener('submit', function (e) {
        e.preventDefault();
        
        // Prevenir múltiples envíos
        if (formularioEnviandose) {
            return;
        }
        formularioEnviandose = true;
        
        const btn = document.getElementById('btn-crear-renovacion');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Generando...';

        const payload = {
            fecha_salida: document.getElementById('fecha-salida-renovacion').value,
            fecha_entrada: document.getElementById('fecha-entrada-renovacion').value,
            direccion_obra: document.getElementById('direccion-obra-renovacion').value,
            traslado_extra: document.getElementById('traslado-extra-renovacion').value,
            costo_traslado_extra: parseFloat(document.getElementById('costo-traslado-renovacion').value) || 0,
            factura_legal: parseInt(document.getElementById('factura-legal-renovacion').value) || 0,
            pendientes: pendientesRenovacion
        };

        fetch(`/renovacion_pendientes/${rentaIdRenovacionActual}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(resp => resp.json())
        .then(json => {
            if (json.success) {
                bootstrap.Modal.getInstance(document.getElementById('modalRenovacionPendientes')).hide();
                Swal.fire({
                    title: '¡Renovación Exitosa!',
                    text: 'La renovación se ha registrado correctamente.',
                    icon: 'success',
                    confirmButtonText: 'Entendido'
                }).then(() => window.location.reload());
            } else {
                Swal.fire('Error', json.error || 'No se pudo crear la renovación.', 'error');
            }
        })
        .catch(() => {
            Swal.fire('Error', 'Error al enviar la renovación.', 'error');
        })
        .finally(() => {
            formularioEnviandose = false;
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Generar Renovación';
        });
    });
});