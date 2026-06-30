let notaSeccionVisible = false;


function toggleNewNote() {
    const section = document.getElementById('nuevaNotaSection');
    const textarea = document.getElementById('nuevaNota');

    notaSeccionVisible = !notaSeccionVisible;

    if (notaSeccionVisible) {
        section.style.display = 'block';
        textarea.focus();
        section.style.animation = 'slideInUp 0.3s ease-out';
    } else {
        section.style.display = 'none';
        textarea.value = '';
    }
}

// Función mejorada para guardar nota
function guardarNota() {
    const nota = document.getElementById('nuevaNota').value.trim();
    if (!nota) {
        mostrarToast('Por favor escribe una nota', 'warning');
        return;
    }

    // Mostrar loading
    const btnGuardar = document.querySelector('button[onclick="guardarNota()"]');
    const textoOriginal = btnGuardar.innerHTML;
    btnGuardar.innerHTML = '<i class="spinner-border spinner-border-sm me-1"></i>Guardando...';
    btnGuardar.disabled = true;

    const sucursalId = document.querySelector('.bloc-notas-card')?.dataset.sucursalId || null;

    fetch('/dashboard/notas', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ nota: nota, sucursal_id: sucursalId })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                mostrarToast('Nota guardada exitosamente', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                mostrarToast('Error al guardar la nota: ' + data.error, 'danger');
                btnGuardar.innerHTML = textoOriginal;
                btnGuardar.disabled = false;
            }
        })
        .catch(error => {
            mostrarToast('Error de conexión', 'danger');
            btnGuardar.innerHTML = textoOriginal;
            btnGuardar.disabled = false;
        });
}

// Función mejorada para eliminar nota
function eliminarNota(id) {
    Swal.fire({
        title: '¿Eliminar nota?',
        text: 'Esta acción no se puede deshacer.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#dc3545',
        cancelButtonColor: '#6c757d',
        reverseButtons: true
    }).then((result) => {
        if (!result.isConfirmed) return;

        const notaElement = document.querySelector(`[data-id="${id}"]`);
        notaElement.style.opacity = '0.5';

        fetch('/dashboard/notas/' + id, {
            method: 'DELETE'
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    notaElement.style.animation = 'slideOut 0.3s ease-out';
                    setTimeout(() => notaElement.remove(), 300);
                    mostrarToast('Nota eliminada', 'success');
                } else {
                    mostrarToast('Error al eliminar la nota: ' + data.error, 'danger');
                    notaElement.style.opacity = '1';
                }
            })
            .catch(error => {
                mostrarToast('Error de conexión', 'danger');
                notaElement.style.opacity = '1';
            });
    });
}

// Sistema de notificaciones toast mejorado
function mostrarToast(mensaje, tipo = 'info') {
    // Crear contenedor de toasts si no existe
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1080;
            min-width: 300px;
        `;
        document.body.appendChild(toastContainer);
    }

    // Crear toast
    const toastId = 'toast-' + Date.now();
    const toastColors = {
        success: '#28a745',
        danger: '#dc3545',
        warning: '#ffc107',
        info: '#17a2b8'
    };

    const toast = document.createElement('div');
    toast.id = toastId;
    toast.style.cssText = `
        background: ${toastColors[tipo] || toastColors.info};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 10px;
        margin-bottom: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        transform: translateX(100%);
        transition: all 0.3s ease;
        font-weight: 500;
    `;
    toast.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <span>${mensaje}</span>
            <button type="button" style="background:none; border:none; color:white; font-size:1.2rem; cursor:pointer;" onclick="cerrarToast('${toastId}')">&times;</button>
        </div>
    `;

    toastContainer.appendChild(toast);

    // Animación de entrada
    setTimeout(() => {
        toast.style.transform = 'translateX(0)';
    }, 100);

    // Auto cerrar después de 4 segundos
    setTimeout(() => {
        cerrarToast(toastId);
    }, 4000);
}

function cerrarToast(toastId) {
    const toast = document.getElementById(toastId);
    if (toast) {
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }
}

// Función para actualizar contadores dinámicamente
function actualizarContadores() {
    const contadores = document.querySelectorAll('.badge-count');
    contadores.forEach(contador => {
        const valorActual = parseInt(contador.textContent);
        if (valorActual > 0) {
            contador.style.animation = 'pulse 2s infinite';
        }
    });
}

// Función para agregar efectos de loading
function agregarLoadingStates() {
    const cards = document.querySelectorAll('.dashboard-card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';

        setTimeout(() => {
            card.style.transition = 'all 0.6s cubic-bezier(0.25, 0.8, 0.25, 1)';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });
}

// Auto-refresh mejorado con indicador visual
function configurarAutoRefresh() {
    let tiempoRestante = 300; // 5 minutos

    function actualizarIndicador() {
        const minutos = Math.floor(tiempoRestante / 60);
        const segundos = tiempoRestante % 60;

        // Agregar indicador de refresh si no existe
        let indicador = document.getElementById('refresh-indicator');
        if (!indicador) {
            indicador = document.createElement('div');
            indicador.id = 'refresh-indicator';
            indicador.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: var(--color-primary);
                color: white;
                padding: 0.5rem 1rem;
                border-radius: 25px;
                font-size: 0.8rem;
                z-index: 1070;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                transition: all 0.3s ease;
            `;
            document.body.appendChild(indicador);
        }

        if (tiempoRestante <= 30) {
            indicador.style.background = '#dc3545';
            indicador.innerHTML = `<i class="bi bi-arrow-clockwise"></i> Actualizando en ${segundos}s`;
        } else {
            indicador.innerHTML = `<i class="bi bi-clock"></i> Próxima actualización: ${minutos}:${segundos.toString().padStart(2, '0')}`;
        }

        if (tiempoRestante <= 0) {
            indicador.innerHTML = '<i class="bi bi-arrow-clockwise spin"></i> Actualizando...';
            setTimeout(() => location.reload(), 1000);
        } else {
            tiempoRestante--;
        }
    }

    // Actualizar cada segundo
    setInterval(actualizarIndicador, 1000);
}

// Inicialización del dashboard
document.addEventListener('DOMContentLoaded', function () {
    generarCalendario();
    agregarLoadingStates();
    actualizarContadores();
    configurarAutoRefresh();

    // Agregar estilos adicionales para animaciones
    const style = document.createElement('style');
    style.textContent = `
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }
        
        @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        .spin { animation: spin 1s linear infinite; }
        
        @keyframes slideOut {
            from { opacity: 1; transform: translateX(0); }
            to { opacity: 0; transform: translateX(-100%); }
        }
    `;
    document.head.appendChild(style);

    console.log('Dashboard inicializado correctamente');
});

// Manejar errores globalmente
window.addEventListener('error', function (e) {
    console.error('Error en dashboard:', e.error);
    mostrarToast('Se produjo un error inesperado', 'danger');
});