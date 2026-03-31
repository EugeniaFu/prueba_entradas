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
        if (['TRANSFERENCIA', 'T.DÉBITO', 'T.CRÉDITO'].includes(this.value)) {
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

// Función para redondear según las reglas de efectivo
function redondearEfectivo(monto) {
    const entero = Math.floor(monto);
    const centavos = Math.round((monto - entero) * 100);
    if (centavos <= 49) return entero;
    if (centavos >= 60) return entero + 1;
    return entero + 0.5;
}


function cargarCobroRetraso(rentaId) {
    rentaIdCobroRetrasoActual = rentaId;
    fetch(`/cobros_retraso/preview/${rentaId}`)
        .then(resp => {
            if (!resp.ok) {
                return resp.json().then(errorData => {
                    throw new Error(errorData.error || 'No se encontró la nota de entrada o la renta');
                });
            }
            return resp.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            notaEntradaId = data.nota_entrada_id;
            diasRetraso = data.dias_retraso;
            detallesCobroRetraso = data.detalles || [];

            // Mostrar días de retraso
            const diasRetrasoElement = document.getElementById('dias-retraso');
            if (diasRetrasoElement) {
                diasRetrasoElement.textContent = diasRetraso;
            } else {
                console.warn('Elemento dias-retraso no encontrado en el DOM');
            }

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
            document.getElementById('cobro-retraso-metodo-pago').value = 'EFECTIVO';
            document.getElementById('cobro-retraso-monto-recibido').value = '';
            document.getElementById('cobro-retraso-cambio').value = '';
            document.getElementById('cobro-retraso-facturable').value = '0';
            document.getElementById('numero-seguimiento-retraso').value = '';
            document.getElementById('cobro-retraso-observaciones').value = '';

            calcularTotalesCobroRetraso();

            // Mostrar modal después de procesar todos los datos
            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('modalCobroRetraso'));
            modal.show();
            
            // Asegurar que el elemento existe después de mostrar el modal
            setTimeout(() => {
                const diasRetrasoElement = document.getElementById('dias-retraso');
                if (diasRetrasoElement && !diasRetrasoElement.textContent) {
                    diasRetrasoElement.textContent = diasRetraso;
                }
            }, 100);
        })
        .catch(err => {
            Swal.fire({
                icon: 'error',
                title: 'No se puede cobrar retraso',
                text: err.message,
                confirmButtonText: 'Entendido'
            });
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
    let total = subtotal + iva;
    
    // Aplicar redondeo para efectivo
    const metodoPago = document.getElementById('cobro-retraso-metodo-pago').value;
    if (metodoPago === 'EFECTIVO') {
        const totalOriginal = total;
        total = redondearEfectivo(total);
        console.log(`Redondeo aplicado: ${totalOriginal.toFixed(2)} -> ${total.toFixed(2)}`);
    }

    // Mostrar totales
    document.getElementById('subtotal-cobro-retraso').textContent = subtotal.toFixed(2);
    document.getElementById('iva-cobro-retraso').textContent = iva.toFixed(2);
    document.getElementById('total-cobro-retraso-con-iva').textContent = total.toFixed(2);

    // Monto recibido y cambio
    const montoRecibidoInput = document.getElementById('cobro-retraso-monto-recibido');
    const cambioInput = document.getElementById('cobro-retraso-cambio');
    const grupoSeguimiento = document.getElementById('grupo-numero-seguimiento-retraso');

    if (['TRANSFERENCIA', 'T.DÉBITO', 'T.CRÉDITO'].includes(metodoPago)) {
        montoRecibidoInput.value = total.toFixed(2);
        montoRecibidoInput.readOnly = true;
        cambioInput.value = '0.00';
        grupoSeguimiento.style.display = '';
    } else {
        montoRecibidoInput.readOnly = false;
        grupoSeguimiento.style.display = 'none';
        const montoRecibido = parseFloat(montoRecibidoInput.value) || 0;
        const cambio = montoRecibido > total ? (montoRecibido - total) : 0;
        cambioInput.value = cambio.toFixed(2);
    }
}

function guardarCobroRetraso() {
    // Validaciones del frontend
    const metodoPago = document.getElementById('cobro-retraso-metodo-pago').value;
    const facturable = document.getElementById('cobro-retraso-facturable').value;
    
    if (!metodoPago) {
        Swal.fire('Error', 'Debe seleccionar un método de pago', 'error');
        return;
    }
    
    if (!facturable) {
        Swal.fire('Error', 'Debe especificar si requiere facturación', 'error');
        return;
    }
    
    // Validación para efectivo
    if (metodoPago === 'EFECTIVO') {
        const montoRecibido = parseFloat(document.getElementById('cobro-retraso-monto-recibido').value) || 0;
        const total = parseFloat(document.getElementById('total-cobro-retraso-con-iva').textContent) || 0;
        if (montoRecibido < total) {
            Swal.fire('Error', 'El monto recibido debe ser mayor o igual al total', 'error');
            return;
        }
    } else {
        // Validación para métodos no efectivo
        const numeroSeguimiento = document.getElementById('numero-seguimiento-retraso').value.trim();
        if (!numeroSeguimiento) {
            Swal.fire('Error', 'Debe ingresar el número de seguimiento', 'error');
            return;
        }
    }

    // Recolectar datos
    const trasladoExtra = document.getElementById('cobro-retraso-traslado-extra').value;
    const costoTrasladoExtra = parseFloat(document.getElementById('cobro-retraso-costo-traslado').value) || 0;
    const montoRecibido = parseFloat(document.getElementById('cobro-retraso-monto-recibido').value) || 0;
    const cambio = parseFloat(document.getElementById('cobro-retraso-cambio').value) || 0;
    const numeroSeguimiento = document.getElementById('numero-seguimiento-retraso').value;
    const observaciones = document.getElementById('cobro-retraso-observaciones').value;

    const subtotal = parseFloat(document.getElementById('subtotal-cobro-retraso').textContent) || 0;
    const iva = parseFloat(document.getElementById('iva-cobro-retraso').textContent) || 0;
    const total = parseFloat(document.getElementById('total-cobro-retraso-con-iva').textContent) || 0;
    
    // Deshabilitar botón durante el envío
    const btnGuardar = document.querySelector('#form-cobro-retraso button[type="submit"]');
    if (btnGuardar) {
        btnGuardar.disabled = true;
        btnGuardar.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Guardando...';
    }

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
            facturable: parseInt(facturable),
            traslado_extra: trasladoExtra,
            costo_traslado_extra: costoTrasladoExtra,
            numero_seguimiento: numeroSeguimiento
        })
    })
        .then(resp => {
            if (!resp.ok) {
                return resp.json().then(errorData => {
                    throw new Error(errorData.error || 'Error desconocido');
                });
            }
            return resp.json();
        })
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
                Swal.fire('Error', data.error || 'No se pudo guardar el cobro por retraso.', 'error');
            }
        })
        .catch(err => {
            Swal.fire({
                icon: 'error',
                title: 'Error al guardar',
                text: err.message,
                confirmButtonText: 'Entendido'
            });
            console.error(err);
        })
        .finally(() => {
            // Rehabilitar botón
            if (btnGuardar) {
                btnGuardar.disabled = false;
                btnGuardar.innerHTML = 'Guardar Cobro';
            }
        });
}

// Función global para abrir modal de cobro retraso desde otros lugares
window.abrirModalCobroRetraso = function(rentaId) {
    cargarCobroRetraso(rentaId);
};