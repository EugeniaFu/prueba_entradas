"""
Utilidades para comparar nombres de clientes.
Sirve para detectar el mismo nombre escrito diferente (Yolanda / Iolanda, Pérez / Peres, Gonzalez / Gonsales).
"""
import re
import unicodedata


def simplificar_nombre(texto):
    """
    Lleva un nombre a una forma "fonética" simple para compararlo:
    minúsculas, sin acentos ni espacios, letras que suenan igual unificadas
    y letras dobles juntas.
    """
    texto = unicodedata.normalize('NFD', (texto or '').lower())
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')  # quitar acentos
    texto = re.sub(r'[^a-z]', '', texto)                                  # solo letras, sin espacios

    texto = texto.replace('ll', 'y')
    texto = re.sub(r'c([ei])', r's\1', texto)   # ce/ci suenan como se/si
    texto = texto.replace('z', 's')
    texto = texto.replace('v', 'b')
    texto = texto.replace('y', 'i')
    texto = re.sub(r'(?<!c)h', '', texto)       # h muda (se respeta la "ch")
    texto = re.sub(r'(.)\1+', r'\1', texto)     # letras dobles: Anna = Ana
    return texto
