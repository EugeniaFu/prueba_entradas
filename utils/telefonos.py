"""
Utilidades para el manejo de números telefónicos de clientes.
Formato único de guardado: 10 dígitos separados como "981 876 5432".
"""
import re


def normalizar_telefono(texto):
    """
    Convierte cualquier captura de teléfono al formato "XXX XXX XXXX".

    Returns:
        str | None: Teléfono formateado, o None si no tiene 10 dígitos.
    """
    digitos = re.sub(r'\D', '', texto or '')
    # Quitar lada internacional de México (+52)
    if len(digitos) == 12 and digitos.startswith('52'):
        digitos = digitos[2:]
    if len(digitos) != 10:
        return None
    return f"{digitos[:3]} {digitos[3:6]} {digitos[6:]}"
