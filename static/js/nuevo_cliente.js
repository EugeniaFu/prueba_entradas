// ========================================
// VARIABLES GLOBALES
// ========================================
let archivosSeleccionados = [];
let direccionCompleta = false;

// ========================================
// FUNCIONALIDAD DE DOCUMENTOS Y ARCHIVOS
// ========================================

document.getElementById('documentos').addEventListener('change', function (e) {
    for (let file of e.target.files) {
        archivosSeleccionados.push({ file, tipo: 'otro' });
    }
    e.target.value = '';
    renderPreview();
});

function renderPreview() {
    const preview = document.getElementById('previewDocs');
    preview.innerHTML = '';
    if (archivosSeleccionados.length === 0) {
        preview.innerHTML = '<small class="text-muted">No hay archivos seleccionados.</small>';
        return;
    }
    archivosSeleccionados.forEach((item, idx) => {
        let icon = '';
        if (item.file.type === 'application/pdf') {
            icon = '<i class="bi bi-file-earmark-pdf text-danger" style="font-size:2rem;"></i>';
        } else if (item.file.type.startsWith('image/')) {
            icon = '<i class="bi bi-file-earmark-image text-primary" style="font-size:2rem;"></i>';
        } else {
            icon = '<i class="bi bi-file-earmark" style="font-size:2rem;"></i>';
        }
        const size = (item.file.size / 1024 / 1024).toFixed(2) + ' MB';
        const url = URL.createObjectURL(item.file);
        preview.innerHTML += `
            <div class="d-flex align-items-center border rounded p-2 mb-2" style="background:#f8fafc;">
                ${icon}
                <div class="ms-3 flex-grow-1">
                    <div class="fw-bold">${item.file.name}</div>
                    <div class="text-muted" style="font-size:0.9em;">${size}</div>
                    <select class="form-select form-select-sm mt-1" style="width:auto;display:inline-block"
                        onchange="cambiarTipoDoc(${idx}, this.value)">
                        <option value="ine" ${item.tipo === 'ine' ? 'selected' : ''}>INE</option>
                        <option value="comprobante" ${item.tipo === 'comprobante' ? 'selected' : ''}>Comprobante</option>
                        <option value="licencia" ${item.tipo === 'licencia' ? 'selected' : ''}>Licencia</option>
                        <option value="otro" ${item.tipo === 'otro' ? 'selected' : ''}>Otro</option>
                    </select>
                </div>
                <a href="${url}" target="_blank" class="btn btn-outline-secondary btn-sm me-2" title="Vista previa">
                    <i class="bi bi-eye"></i>
                </a>
                <button type="button" class="btn btn-danger btn-sm" onclick="eliminarArchivo(${idx})">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        `;
    });
}

function cambiarTipoDoc(idx, tipo) {
    archivosSeleccionados[idx].tipo = tipo;
}

function eliminarArchivo(idx) {
    archivosSeleccionados.splice(idx, 1);
    renderPreview();
}

// ========================================
// FUNCIONALIDAD DE CÁMARA
// ========================================

let video = document.getElementById('video');
let canvas = document.getElementById('canvas');
let btnCamara = document.getElementById('btnCamara');
let btnFoto = document.getElementById('btnFoto');
let previewFoto = document.getElementById('previewFoto');
let fotoInput = document.getElementById('foto_documento');
let stream = null;

btnCamara.onclick = async function () {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
        video.style.display = 'block';
        btnFoto.style.display = 'inline-block';
    } catch (error) {
        alert('Error al acceder a la cámara: ' + error.message);
    }
};

btnFoto.onclick = function () {
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    let dataUrl = canvas.toDataURL('image/png');
    
    fetch(dataUrl)
        .then(res => res.blob())
        .then(blob => {
            let file = new File([blob], "foto_documento.png", { type: "image/png" });
            archivosSeleccionados.push({ file, tipo: 'ine' });
            renderPreview();
        });
    
    previewFoto.src = dataUrl;
    previewFoto.style.display = 'block';
    fotoInput.value = dataUrl;
    video.style.display = 'none';
    btnFoto.style.display = 'none';
    
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
};

// ========================================
// FUNCIONALIDAD DEL MODAL DE DIRECCIÓN
// ========================================

document.addEventListener('DOMContentLoaded', function() {
    
    // Botón para abrir modal de dirección
    const btnAbrirDireccion = document.getElementById('btnAbrirDireccion');
    if (btnAbrirDireccion) {
        btnAbrirDireccion.addEventListener('click', function() {
            const modal = new bootstrap.Modal(document.getElementById('modalDireccion'));
            modal.show();
        });
    }
    
    // Variables del modal
    const modalCpInput = document.getElementById('modal_codigo_postal');
    const modalColoniaSelect = document.getElementById('modal_colonia');
    const modalMunicipioInput = document.getElementById('modal_municipio');
    const modalEstadoInput = document.getElementById('modal_estado');
    const modalCpStatus = document.getElementById('modal_cp_status');
    
    let timeoutId;
    
    // Autocompletado por código postal
    if (modalCpInput) {
        modalCpInput.addEventListener('input', function() {
            const cp = this.value.replace(/\D/g, ''); // Solo números
            this.value = cp;
            
            // Limpiar campos - mantener siempre como SELECT por defecto
            const coloniaElement = document.getElementById('modal_colonia');
            if (coloniaElement && coloniaElement.tagName === 'INPUT') {
                // Si es input, convertir de vuelta a select
                const parent = coloniaElement.parentNode;
                const select = document.createElement('select');
                select.className = 'form-select';
                select.id = 'modal_colonia';
                select.required = true;
                select.innerHTML = '<option value="">Primero ingresa el CP</option>';
                select.disabled = true;
                parent.replaceChild(select, coloniaElement);
            } else if (modalColoniaSelect) {
                modalColoniaSelect.innerHTML = '<option value="">Primero ingresa el CP</option>';
                modalColoniaSelect.disabled = true;
            }
            
            modalMunicipioInput.value = '';
            modalEstadoInput.value = '';
            modalMunicipioInput.setAttribute('readonly', true);
            modalEstadoInput.setAttribute('readonly', true);
            modalCpStatus.textContent = 'Ingresa 5 dígitos';
            modalCpStatus.className = 'text-muted';
            
            // Cancelar búsqueda anterior
            clearTimeout(timeoutId);
            
            if (cp.length === 5) {
                modalCpStatus.textContent = 'Consultando...';
                modalCpStatus.className = 'text-info';
                
                // Esperar 500ms antes de hacer la consulta
                timeoutId = setTimeout(() => {
                    buscarColoniasPorCP(cp);
                }, 500);
            }
        });
    }
    
    // Función para buscar colonias por CP
    async function buscarColoniasPorCP(cp) {
        try {
            const response = await fetch(`/clientes/api/colonias/${cp}`);
            const data = await response.json();
            
            if (data.success) {
                // Llenar estado y municipio
                modalEstadoInput.value = data.estado;
                modalMunicipioInput.value = data.municipio;
                
                // Llenar select de colonias
                modalColoniaSelect.innerHTML = '<option value="">Selecciona una colonia</option>';
                
                // Ordenar colonias alfabéticamente para mejor UX
                const coloniasOrdenadas = data.colonias.sort();
                
                coloniasOrdenadas.forEach(colonia => {
                    const option = document.createElement('option');
                    option.value = colonia;
                    option.textContent = colonia;
                    modalColoniaSelect.appendChild(option);
                });
                
                modalColoniaSelect.disabled = false;
                modalCpStatus.textContent = `${data.colonias.length} colonias encontradas - ${data.fuente || 'API'}`;
                modalCpStatus.className = 'text-success';
                
            } else {
                modalCpStatus.textContent = data.message || 'CP no encontrado - Llena manualmente';
                modalCpStatus.className = 'text-warning';
                habilitarLlenadoManual();
            }
            
        } catch (error) {
            console.error('Error:', error);
            modalCpStatus.textContent = 'Error de conexión - Llena manualmente';
            modalCpStatus.className = 'text-danger';
            habilitarLlenadoManual();
        }
    }
    
    // Función para habilitar llenado manual
    function habilitarLlenadoManual() {
        modalMunicipioInput.removeAttribute('readonly');
        modalEstadoInput.removeAttribute('readonly');
        
        // Solo convertir si aún es un select (prevenir error replaceChild)
        const coloniaElement = document.getElementById('modal_colonia');
        if (coloniaElement && coloniaElement.tagName === 'SELECT') {
            const parent = coloniaElement.parentNode;
            if (parent) {
                const input = document.createElement('input');
                input.type = 'text';
                input.className = 'form-control';
                input.id = 'modal_colonia';
                input.required = true;
                input.placeholder = 'Escribe el nombre de la colonia';
                
                parent.replaceChild(input, coloniaElement);
            }
        } else {
            // Si ya es input, solo habilitarlo
            if (coloniaElement) {
                coloniaElement.disabled = false;
            }
        }
    }
    
    // Guardar dirección desde el modal
    const btnGuardarDireccion = document.getElementById('btnGuardarDireccion');
    if (btnGuardarDireccion) {
        btnGuardarDireccion.addEventListener('click', function() {
            const calle = document.getElementById('modal_calle').value.trim();
            const entreCalles = document.getElementById('modal_entre_calles').value.trim();
            const numeroExterior = document.getElementById('modal_numero_exterior').value.trim();
            const numeroInterior = document.getElementById('modal_numero_interior').value.trim();
            const colonia = document.getElementById('modal_colonia').value.trim();
            const codigoPostal = document.getElementById('modal_codigo_postal').value.trim();
            const municipio = document.getElementById('modal_municipio').value.trim();
            const estado = document.getElementById('modal_estado').value.trim();
            
            // Validar campos obligatorios
            if (!calle || !numeroExterior || !colonia || !codigoPostal || !municipio || !estado) {
                alert('Por favor, completa todos los campos obligatorios de la dirección.');
                return;
            }
            
            // Guardar en campos ocultos
            document.getElementById('hidden_calle').value = calle;
            document.getElementById('hidden_entre_calles').value = entreCalles;
            document.getElementById('hidden_numero_exterior').value = numeroExterior;
            document.getElementById('hidden_numero_interior').value = numeroInterior;
            document.getElementById('hidden_colonia').value = colonia;
            document.getElementById('hidden_codigo_postal').value = codigoPostal;
            document.getElementById('hidden_municipio').value = municipio;
            document.getElementById('hidden_estado').value = estado;
            
            // Mostrar resumen en el formulario principal
            let direccionTexto = `${calle}${entreCalles ? ' (entre ' + entreCalles + ')' : ''} ${numeroExterior}${numeroInterior ? ', Int. ' + numeroInterior : ''}, ${colonia}, CP ${codigoPostal}, ${municipio}, ${estado}`;
            
            document.getElementById('direccionCompleta').textContent = direccionTexto;
            document.getElementById('resumenDireccion').style.display = 'block';
            document.getElementById('estadoDireccion').textContent = 'Dirección capturada';
            document.getElementById('estadoDireccion').className = 'badge bg-success';
            
            direccionCompleta = true;
            
            // Cerrar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalDireccion'));
            modal.hide();
        });
    }
});

// ========================================
// CLIENTE FORÁNEO
// ========================================

document.getElementById('es_foraneo').addEventListener('change', function () {
    const alojamiento = document.getElementById('direccion_alojamiento');
    document.getElementById('grupoAlojamiento').style.display = this.checked ? 'block' : 'none';
    alojamiento.required = this.checked;
    if (!this.checked) alojamiento.value = '';
});

// ========================================
// AVISO DE NOMBRE SIMILAR
// Nombres + primer apellido + segundo apellido se revisan juntos
// ========================================

const camposNombre = ['nombre', 'apellido1', 'apellido2'].map(id => document.getElementById(id));
const confirmarNombre = document.getElementById('confirmar_nombre_similar');
let revisionNombre = { clave: '', similares: Promise.resolve([]) };
let avisoMostradoPara = '';

function escaparHtml(texto) {
    const div = document.createElement('div');
    div.textContent = texto ?? '';
    return div.innerHTML;
}

// Renglón con los datos de un cliente existente (aviso de nombre y de teléfono)
function htmlClienteExistente(c) {
    const estatus = c.estatus === 'betado' ? '<span class="text-danger fw-bold">BETADO</span>'
        : c.estatus === 'baja' ? '<span class="text-danger fw-bold">DADO DE BAJA</span>'
        : escaparHtml(c.estatus);
    return `<li class="mb-2">
                <strong>${escaparHtml(c.codigo_cliente)} – ${escaparHtml(c.nombre)}</strong><br>
                Tel. ${escaparHtml(c.telefono)} · ${estatus} ·
                <a href="${escaparHtml(c.url_detalle)}" target="_blank">Ver cliente</a>
            </li>`;
}

// Consulta los clientes parecidos solo cuando los tres campos tienen texto y el nombre cambió
function obtenerNombresSimilares() {
    const valores = camposNombre.map(c => c.value.trim());
    if (!valores.every(Boolean)) return Promise.resolve([]);

    const clave = valores.join('|').toLowerCase();
    if (clave !== revisionNombre.clave) {
        confirmarNombre.value = '0';
        const params = new URLSearchParams({ nombre: valores[0], apellido1: valores[1], apellido2: valores[2] });
        revisionNombre = {
            clave,
            similares: fetch(`/clientes/api/nombres-similares?${params}`)
                .then(r => r.ok ? r.json() : [])
                .catch(() => [])
        };
    }
    return revisionNombre.similares;
}

// Regresa true si se puede continuar (sin parecidos o el usuario confirmó que es otra persona)
async function revisarNombreSimilar() {
    const similares = await obtenerNombresSimilares();
    if (!similares.length || confirmarNombre.value === '1') return true;

    avisoMostradoPara = revisionNombre.clave;
    const lista = similares.map(htmlClienteExistente).join('');

    const resultado = await Swal.fire({
        icon: 'warning',
        title: 'Hay clientes con un nombre similar',
        html: `<p>Verifica con el cliente que no esté ya registrado:</p>
               <ul class="text-start">${lista}</ul>`,
        showCancelButton: true,
        confirmButtonText: 'Es otra persona, continuar',
        cancelButtonText: 'Revisar',
        allowOutsideClick: false
    });

    if (resultado.isConfirmed) {
        confirmarNombre.value = '1';
        return true;
    }
    return false;
}

// Al salir de cualquiera de los tres campos; el aviso sale una sola vez por nombre
camposNombre.forEach(campo => {
    campo.addEventListener('blur', async function () {
        const similares = await obtenerNombresSimilares();
        if (similares.length && confirmarNombre.value !== '1' && avisoMostradoPara !== revisionNombre.clave) {
            revisarNombreSimilar();
        }
    });
});

// ========================================
// AVISO DE TELÉFONO DUPLICADO
// A diferencia del nombre, este aviso bloquea el alta
// ========================================

const campoTelefono = document.getElementById('telefono');
let revisionTelefono = { telefono: '', existente: Promise.resolve(null) };
let avisoTelefonoMostradoPara = '';

// Consulta solo cuando el teléfono tiene 10 dígitos y cambió desde la última revisión
function obtenerTelefonoDuplicado() {
    const telefono = campoTelefono.value;
    if (!telefonoValido(telefono)) return Promise.resolve(null);

    if (telefono !== revisionTelefono.telefono) {
        revisionTelefono = {
            telefono,
            existente: fetch(`/clientes/api/telefono-duplicado?${new URLSearchParams({ telefono })}`)
                .then(r => r.ok ? r.json() : null)
                .catch(() => null)
        };
    }
    return revisionTelefono.existente;
}

// Regresa true si el teléfono está libre
async function revisarTelefonoDuplicado() {
    const existente = await obtenerTelefonoDuplicado();
    if (!existente) return true;

    avisoTelefonoMostradoPara = revisionTelefono.telefono;
    const motivo = existente.estatus === 'betado' ? 'pertenece a un cliente <span class="text-danger fw-bold">BETADO</span>'
        : existente.estatus === 'baja' ? 'pertenece a un cliente <span class="text-danger fw-bold">DADO DE BAJA</span>'
        : 'ya está registrado con otro cliente';

    await Swal.fire({
        icon: 'error',
        title: 'Teléfono ya registrado',
        html: `<p>Este teléfono ${motivo}. No se puede dar de alta.</p>
               <ul class="text-start">${htmlClienteExistente(existente)}</ul>`,
        confirmButtonText: 'Entendido',
        allowOutsideClick: false,
        didClose: () => campoTelefono.focus()
    });
    return false;
}

// Al salir del campo; el aviso sale una sola vez por número
campoTelefono.addEventListener('blur', async function () {
    const existente = await obtenerTelefonoDuplicado();
    if (existente && avisoTelefonoMostradoPara !== revisionTelefono.telefono) {
        revisarTelefonoDuplicado();
    }
});

// ========================================
// VALIDACIÓN Y ENVÍO DEL FORMULARIO
// ========================================

document.getElementById('formNuevoCliente').addEventListener('submit', async function (e) {
    e.preventDefault();

    // Validar dirección
    if (!direccionCompleta) {
        alert('Por favor, ingresa la dirección del cliente antes de guardar.');
        return false;
    }

    // Validar teléfono a 10 dígitos
    if (!telefonoValido(document.getElementById('telefono').value)) {
        alert('El teléfono debe tener 10 dígitos.');
        return false;
    }

    // Teléfono de otro cliente: se vuelve a mostrar el aviso y no se guarda
    if (!(await revisarTelefonoDuplicado())) {
        return false;
    }

    // Validar alojamiento de cliente foráneo
    if (document.getElementById('es_foraneo').checked && !document.getElementById('direccion_alojamiento').value.trim()) {
        alert('Por favor, ingresa la dirección de alojamiento del cliente foráneo.');
        return false;
    }

    // Validar archivos
    if (archivosSeleccionados.length === 0) {
        alert('Debes subir al menos un documento.');
        return false;
    }
    
    // Nombre similar sin confirmar: se vuelve a mostrar el aviso
    if (!(await revisarNombreSimilar())) {
        return false;
    }

    // Sin restricción de tamaño para documentos de clientes
    // (Permitir archivos grandes para documentos e imágenes de alta calidad)
    
    const form = e.target;
    
    // Deshabilitar botón y mostrar indicador de progreso
    const btn = document.getElementById('btn-guardar-cliente');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando cliente...';
    }
    
    // Mostrar mensaje de progreso global
    const progressDiv = document.createElement('div');
    progressDiv.id = 'upload-progress';
    progressDiv.className = 'alert alert-info mt-3';
    progressDiv.innerHTML = `
        <div class="d-flex align-items-center">
            <div class="spinner-border spinner-border-sm me-3"></div>
            <div>
                <strong>Procesando información del cliente...</strong><br>
                <small>Subiendo archivos y guardando datos. Esto puede tomar unos momentos.</small>
            </div>
        </div>
    `;
    form.appendChild(progressDiv);
    
    // Preparar FormData
    const formData = new FormData(form);
    archivosSeleccionados.forEach((item, idx) => {
        formData.append('documentos', item.file);
        formData.append(`tipo_documento_${idx}`, item.tipo);
    });
    
    // Enviar formulario con timeout extendido
    fetch(form.action, {
        method: 'POST',
        body: formData,
        // Sin timeout para permitir subidas grandes
    }).then(response => {
        if (response.redirected) {
            // Mostrar éxito antes de redirigir
            progressDiv.className = 'alert alert-success mt-3';
            progressDiv.innerHTML = `
                <div class="d-flex align-items-center">
                    <i class="bi bi-check-circle me-3" style="font-size: 1.5rem;"></i>
                    <div>
                        <strong>¡Cliente guardado exitosamente!</strong><br>
                        <small>Redirigiendo...</small>
                    </div>
                </div>
            `;
            
            // Esperar un poco antes de redirigir para que vea el mensaje
            setTimeout(() => {
                window.location.href = response.url;
            }, 1500);
        } else {
            response.text().then(html => {
                document.body.innerHTML = html;
            });
        }
    }).catch(error => {
        console.error('Error:', error);
        
        // Remover indicador de progreso
        if (progressDiv) {
            progressDiv.remove();
        }
        
        // Mostrar error específico según el tipo
        let errorMsg = 'Error de conexión. Por favor, verifica tu conexión a internet e intenta de nuevo.';
        
        if (error.name === 'TypeError') {
            errorMsg = 'Error de red. Verifica tu conexión a internet.';
        }
        
        alert(errorMsg);
        
        // Rehabilitar botón
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-save"></i> Guardar';
        }
    });
});