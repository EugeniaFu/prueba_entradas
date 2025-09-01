document.addEventListener('DOMContentLoaded', function () {
    const modalEl = document.getElementById('modalNuevaRentaRenovacion');
    const botones = document.querySelectorAll('.btn-abrir-modal-renovacion');
    const formRenovar = document.getElementById('form-renovar-renta');
    const fechaInicioInput = document.getElementById('fecha_salida_modal');
    const fechaFinInput = document.getElementById('fecha_entrada_modal');
    const tbody = document.querySelector('#tabla-productos-renovacion tbody');

    botones.forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            const rentaId = this.getAttribute('data-renta-id');

            // Actualizar action del form con el ID de la renta
            formRenovar.action = `/rentas/renovar/${rentaId}`;
            document.getElementById('renta_id_hidden').value = rentaId;

            const modal = new bootstrap.Modal(modalEl);
            modal.show();

            const clienteInput = document.getElementById('cliente_nombre_modal');
            const direccionInput = document.getElementById('direccion_obra_modal');
            const observacionesInput = document.getElementById('observaciones_modal');

            // Limpiar campos
            clienteInput.value = "Cargando...";
            direccionInput.value = "";
            fechaInicioInput.value = "";
            fechaFinInput.value = "";
            observacionesInput.value = "";
            tbody.innerHTML = "";

            // Traer datos de la renta original
            fetch(`/rentas/detalle/${rentaId}`)
                .then(res => res.json())
                .then(data => {
                    clienteInput.value = data.cliente.nombre || '';
                    direccionInput.value = data.renta.direccion_obra || '';
                    fechaInicioInput.value = data.renta.fecha_salida || '';
                    fechaFinInput.value = data.renta.fecha_entrada || '';
                    observacionesInput.value = data.renta.observaciones || '';

                   if (Array.isArray(data.productos)) {
                        data.productos.forEach(p => {
                            const cantidad = Number(p.cantidad) || 1;
                            const costo = Number(p.costo_unitario) || 0;
                            const dias = Number(p.dias) || 1; // tomar dias de la renta original
                            const subtotal = (cantidad * dias * costo).toFixed(2);

                            const tr = document.createElement('tr');
                            tr.innerHTML = `
                                <td>${p.nombre}<input type="hidden" name="producto_id[]" value="${p.id || ''}"></td>
                                <td><input type="number" name="cantidad[]" value="${cantidad}" min="1" class="form-control cantidad-input"></td>
                                <td><input type="number" name="dias_renta[]" value="${dias}" min="1" class="form-control dias-input"></td>
                                <td><input type="number" name="costo_unitario[]" value="${costo}" step="0.01" class="form-control costo-input"></td>
                                <td class="subtotal-cell">${subtotal}</td>
                                <td><button type="button" class="btn btn-danger btn-quitar">Quitar</button></td>
                            `;
                            tbody.appendChild(tr);
                        });
                    }

                    calcularTotales();
                })
                .catch(err => console.error(err));
        });
    });

    // Quitar productos
    tbody.addEventListener('click', function (e) {
        if (e.target.classList.contains('btn-quitar')) {
            e.target.closest('tr').remove();
            calcularTotales();
        }
    });

    // Recalcular subtotal al cambiar cantidad, días o costo
    tbody.addEventListener('input', function (e) {
        const tr = e.target.closest('tr');
        if (tr) {
            actualizarSubtotal(tr);
            calcularTotales();
        }
    });

    // Recalcular días y subtotales cuando cambian fechas
    fechaInicioInput.addEventListener('change', actualizarDias);
    fechaFinInput.addEventListener('change', actualizarDias);

    function calcularDiasActual() {
        const fechaInicio = new Date(fechaInicioInput.value);
        const fechaFin = new Date(fechaFinInput.value);

        if (isNaN(fechaInicio.getTime())) return 1;

        let dias = 1;
        if (!isNaN(fechaFin.getTime())) {
            dias = (fechaFin - fechaInicio) / (1000 * 60 * 60 * 24) + 1;
            if (dias < 1) dias = 1;
        }
        return dias;
    }

    function actualizarDias() {
        const dias = calcularDiasActual();
        document.querySelectorAll('.dias-input').forEach(input => {
            input.value = dias;
            const tr = input.closest('tr');
            actualizarSubtotal(tr);
        });
        calcularTotales();
    }

    function actualizarSubtotal(tr) {
        const cantidad = Number(tr.querySelector('.cantidad-input').value) || 0;
        const dias = Number(tr.querySelector('.dias-input').value) || 0;
        const costo = Number(tr.querySelector('.costo-input').value) || 0;
        tr.querySelector('.subtotal-cell').textContent = (cantidad * dias * costo).toFixed(2);
    }

    function calcularTotales() {
        let subtotal = 0;
        document.querySelectorAll('#tabla-productos-renovacion .subtotal-cell').forEach(td => {
            subtotal += parseFloat(td.textContent) || 0;
        });
        const iva = subtotal * 0.16;
        const total = subtotal + iva;

        document.getElementById('subtotal_general').textContent = `$${subtotal.toFixed(2)}`;
        document.getElementById('iva_general').textContent = `$${iva.toFixed(2)}`;
        document.getElementById('total_general').textContent = `$${total.toFixed(2)}`;
    }
});