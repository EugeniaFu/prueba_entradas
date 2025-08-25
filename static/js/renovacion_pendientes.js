document.addEventListener('DOMContentLoaded', function () {
    let rentaIdRenovacionActual = null;
    let pendientesRenovacion = [];

    // Abrir modal de renovación y cargar pendientes
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-renovacion-pendientes');
        if (btn) {
            rentaIdRenovacionActual = btn.dataset.rentaId;
            cargarPendientesRenovacion(rentaIdRenovacionActual);
        }
    });

    function cargarPendientesRenovacion(rentaId) {
        fetch(`/api/rentas_pendientes/${rentaId}`)
            .then(resp => resp.json())
            .then(data => {
                pendientesRenovacion = data.pendientes || [];
                llenarModalRenovacion(data, pendientesRenovacion);
                const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalRenovacionPendientes'));
                modal.show();
            })
            .catch(() => {
                Swal.fire('Error', 'No se pudieron cargar los productos pendientes.', 'error');
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
        const btn = document.getElementById('btn-crear-renovacion');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Creando...';

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
                Swal.fire('Renovación creada', 'La renovación se ha registrado correctamente.', 'success')
                    .then(() => window.location.reload());
            } else {
                Swal.fire('Error', json.error || 'No se pudo crear la renovación.', 'error');
            }
        })
        .catch(() => {
            Swal.fire('Error', 'Error al enviar la renovación.', 'error');
        })
        .finally(() => {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check-circle"></i> Crear renovación';
        });
    });
});