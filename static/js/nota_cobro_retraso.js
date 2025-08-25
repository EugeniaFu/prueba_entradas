// static/js/nota_cobro_retraso.js
let rentaIdCobroRetrasoActual = null;

document.addEventListener('DOMContentLoaded', function () {
    // Abrir modal y cargar datos
    document.body.addEventListener('click', function (e) {
        const btn = e.target.closest('.btn-cobro-retraso');
        if (btn) {
            const rentaId = btn.dataset.rentaId;
            cargarCobroRetraso(rentaId);
        }
    });

    // Mostrar/ocultar campo de traslado extra
    document.getElementById('cobro-retraso-traslado-extra').addEventListener('change', function () {
        const grupo = document.getElementById('cobro-retraso-costo-traslado-group');
        grupo.style.display = (this.value === 'extra') ? '' : 'none';
        calcularTotalesCobroRetraso();
    });

    // Método de pago: mostrar número de seguimiento si aplica
    document.getElementById('cobro-retraso-metodo-pago').addEventListener('change', function () {
        const grupo = document.getElementById('grupo-numero-seguimiento-retraso');
        if (['transferencia', 'tarjeta_debito', 'tarjeta_credito'].includes(this.value)) {
            grupo.style.display = '';
        } else {
            grupo.style.display = 'none';
        }
        calcularTotalesCobroRetraso();
    });

    // Monto recibido: calcular cambio
    document.getElementById('cobro-retraso-monto-recibido').addEventListener('input', calcularTotalesCobroRetraso);

    // Costo traslado extra: recalcular totales
    document.getElementById('cobro-retraso-costo-traslado').addEventListener('input', calcularTotalesCobroRetraso);

    // Guardar cobro por retraso
    document.getElementById('form-cobro-retraso').addEventListener('submit', function (e) {
        e.preventDefault();
        guardarCobroRetraso();
    });
});

// Variables globales para el modal
let detallesCobroRetraso = [];
let diasRetraso = 0;
let notaEntradaId = null;


function cargarCobroRetraso(rentaId) {
    rentaIdCobroRetrasoActual = rentaId;
    fetch(`/cobros_retraso/preview/${rentaId}`)
        .then(resp => {
            if (!resp.ok) {
                throw new Error('No se encontró la nota de entrada o la renta');
            }
            return resp.json();
        })
        .then(data => {
            notaEntradaId = data.nota_entrada_id;
            diasRetraso = data.dias_retraso;
            detallesCobroRetraso = data.detalles || [];

            // Mostrar días de retraso
            document.getElementById('dias-retraso').textContent = diasRetraso;

            // Llenar tabla
            const tbody = document.querySelector('#tabla-cobro-retraso tbody');
            tbody.innerHTML = '';
            detallesCobroRetraso.forEach(det => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${det.nombre_producto}</td>
                    <td>${det.cantidad}</td>
                    <td>$${parseFloat(det.precio_unitario).toFixed(2)}</td>
                    <td>${det.dias_retraso}</td>
                    <td>$${parseFloat(det.subtotal).toFixed(2)}</td>
                `;
                tbody.appendChild(tr);
            });

            // Limpiar campos
            document.getElementById('cobro-retraso-traslado-extra').value = 'ninguno';
            document.getElementById('cobro-retraso-costo-traslado').value = '';
            document.getElementById('cobro-retraso-metodo-pago').value = 'efectivo';
            document.getElementById('cobro-retraso-monto-recibido').value = '';
            document.getElementById('cobro-retraso-cambio').value = '';
            document.getElementById('cobro-retraso-facturable').value = '0';
            document.getElementById('numero-seguimiento-retraso').value = '';
            document.getElementById('cobro-retraso-observaciones').value = '';

            calcularTotalesCobroRetraso();

            // Mostrar modal
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalCobroRetraso'));
            modal.show();
        })
        .catch(err => {
            Swal.fire('Error', err.message, 'error');
            console.error(err);
        });
}

function calcularTotalesCobroRetraso() {
    // Sumar subtotales
    let subtotal = detallesCobroRetraso.reduce((acc, det) => acc + parseFloat(det.subtotal), 0);

    // Traslado extra
    const trasladoExtra = document.getElementById('cobro-retraso-traslado-extra').value;
    let costoTrasladoExtra = parseFloat(document.getElementById('cobro-retraso-costo-traslado').value) || 0;
    if (trasladoExtra === 'extra' && costoTrasladoExtra > 0) {
        subtotal += costoTrasladoExtra;
    }

    // IVA y total
    const iva = subtotal * 0.16;
    const total = subtotal + iva;

    // Mostrar totales
    document.getElementById('subtotal-cobro-retraso').textContent = subtotal.toFixed(2);
    document.getElementById('iva-cobro-retraso').textContent = iva.toFixed(2);
    document.getElementById('total-cobro-retraso-con-iva').textContent = total.toFixed(2);

    // Monto recibido y cambio
    const metodoPago = document.getElementById('cobro-retraso-metodo-pago').value;
    const montoRecibidoInput = document.getElementById('cobro-retraso-monto-recibido');
    const cambioInput = document.getElementById('cobro-retraso-cambio');

    if (['transferencia', 'tarjeta_debito', 'tarjeta_credito'].includes(metodoPago)) {
        montoRecibidoInput.value = total.toFixed(2);
        montoRecibidoInput.readOnly = true;
        cambioInput.value = '0.00';
    } else {
        montoRecibidoInput.readOnly = false;
        const montoRecibido = parseFloat(montoRecibidoInput.value) || 0;
        const cambio = montoRecibido > total ? (montoRecibido - total) : 0;
        cambioInput.value = cambio.toFixed(2);
    }
}

function guardarCobroRetraso() {
    // Recolectar datos
    const trasladoExtra = document.getElementById('cobro-retraso-traslado-extra').value;
    const costoTrasladoExtra = parseFloat(document.getElementById('cobro-retraso-costo-traslado').value) || 0;
    const metodoPago = document.getElementById('cobro-retraso-metodo-pago').value;
    const montoRecibido = parseFloat(document.getElementById('cobro-retraso-monto-recibido').value) || 0;
    const cambio = parseFloat(document.getElementById('cobro-retraso-cambio').value) || 0;
    const facturable = parseInt(document.getElementById('cobro-retraso-facturable').value) || 0;
    const numeroSeguimiento = document.getElementById('numero-seguimiento-retraso').value;
    const observaciones = document.getElementById('cobro-retraso-observaciones').value;

    const subtotal = parseFloat(document.getElementById('subtotal-cobro-retraso').textContent) || 0;
    const iva = parseFloat(document.getElementById('iva-cobro-retraso').textContent) || 0;
    const total = parseFloat(document.getElementById('total-cobro-retraso-con-iva').textContent) || 0;

    // Enviar datos
    fetch(`/cobros_retraso/guardar/${rentaIdCobroRetrasoActual}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            nota_entrada_id: notaEntradaId,
            detalles: detallesCobroRetraso,
            subtotal,
            iva,
            total,
            metodo_pago: metodoPago,
            monto_recibido: montoRecibido,
            cambio,
            observaciones,
            facturable,
            traslado_extra: trasladoExtra,
            costo_traslado_extra: costoTrasladoExtra,
            estado_pago: 'Pagado',
            numero_seguimiento: numeroSeguimiento
        })
    })
        .then(resp => resp.json())
        .then(data => {
            if (data.success) {
                Swal.fire({
                    title: 'Cobro por retraso guardado',
                    text: '¿Desea descargar el PDF?',
                    icon: 'success',
                    showCancelButton: true,
                    confirmButtonText: 'Descargar PDF',
                    cancelButtonText: 'Cerrar'
                }).then(result => {
                    if (result.isConfirmed) {
                        window.open(`/cobros_retraso/pdf/${data.cobro_retraso_id}`, '_blank');
                    }
                    // Recargar la página para actualizar estados
                    window.location.reload();
                });
            } else {
                Swal.fire('Error', 'No se pudo guardar el cobro por retraso.', 'error');
            }
        })
        .catch(err => {
            Swal.fire('Error', 'Error inesperado al guardar.', 'error');
            console.error(err);
        });
}