// ========================================
// FORMATO DE TELÉFONO: "981 876 5432"
// Aplica a todo input con el atributo data-telefono
// ========================================

function formatearTelefono(valor) {
    let digitos = valor.replace(/\D/g, '');
    // Quitar lada internacional de México (+52) al pegar
    if (digitos.length === 12 && digitos.startsWith('52')) digitos = digitos.slice(2);
    digitos = digitos.slice(0, 10);
    return [digitos.slice(0, 3), digitos.slice(3, 6), digitos.slice(6)].filter(Boolean).join(' ');
}

function telefonoValido(valor) {
    return valor.replace(/\D/g, '').length === 10;
}

document.querySelectorAll('input[data-telefono]').forEach(function (input) {
    const aviso = document.createElement('div');
    aviso.className = 'invalid-feedback';
    aviso.textContent = 'El teléfono debe tener 10 dígitos';
    input.insertAdjacentElement('afterend', aviso);

    input.value = formatearTelefono(input.value);

    input.addEventListener('input', function () {
        this.value = formatearTelefono(this.value);
        if (telefonoValido(this.value)) this.classList.remove('is-invalid');
    });

    input.addEventListener('blur', function () {
        this.classList.toggle('is-invalid', this.value !== '' && !telefonoValido(this.value));
    });
});
