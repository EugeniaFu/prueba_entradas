#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de búsqueda de códigos postales usando JSON
"""

import os
import json
from typing import Dict

class CodigosPostalesJSON:
    """
    Manejador de códigos postales usando archivo JSON (RÁPIDO Y RECOMENDADO)
    
    Ventajas:
    - 10-20x más rápido que Excel
    - No requiere pandas en producción
    - Carga en memoria al iniciar (muy eficiente)
    - Tamaño más pequeño que Excel
    """
    
    def __init__(self, json_path: str = 'codigos_postales.json'):
        self.json_path = json_path
        self.datos = None
        self.cargado = False
        
        # Intentar cargar el JSON al inicializar
        self._cargar_json()
    
    def _cargar_json(self):
        """
        Carga el archivo JSON en memoria (solo una vez)
        """
        try:
            if not os.path.exists(self.json_path):
                print(f"⚠️ Archivo JSON no encontrado: {self.json_path}")
                print("   Ejecuta 'python convertir_excel_a_json.py' para generarlo")
                return False
            
            print(f"📂 Cargando códigos postales desde JSON...", end=" ")
            start_time = time.time()
            
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.datos = json.load(f)
            
            elapsed = time.time() - start_time
            print(f"✅ {len(self.datos)} CPs cargados en {elapsed:.3f}s")
            
            self.cargado = True
            return True
            
        except Exception as e:
            print(f"❌ Error al cargar JSON: {e}")
            return False
    
    def buscar_colonias(self, codigo_postal: str) -> Dict:
        """
        Busca colonias por código postal en el JSON
        
        Args:
            codigo_postal: CP de 5 dígitos (ej: "24095")
            
        Returns:
            Dict con success, estado, municipio, colonias, fuente
        """
        
        try:
            # Verificar que el JSON esté cargado
            if not self.cargado:
                return {
                    'success': False,
                    'message': 'Archivo JSON no disponible. Verifica la configuración.'
                }
            
            # Normalizar CP
            cp = codigo_postal.zfill(5)
            
            # Buscar en el diccionario (búsqueda instantánea)
            if cp in self.datos:
                info = self.datos[cp]
                
                return {
                    'success': True,
                    'estado': info['estado'],
                    'municipio': info['municipio'],
                    'colonias': info['colonias'],
                    'fuente': f'JSON ⚡ ({len(info["colonias"])} colonias)'
                }
            else:
                return {
                    'success': False,
                    'message': f'CP {codigo_postal} no encontrado.'
                }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error procesando CP {codigo_postal}: {str(e)}'
            }
    
    def get_stats(self) -> Dict:
        """
        Obtiene estadísticas del sistema
        """
        if not self.cargado:
            return {'error': 'JSON no cargado'}
        
        return {
            'total_cps': len(self.datos),
            'archivo': self.json_path,
            'tamaño_mb': round(os.path.getsize(self.json_path) / (1024 * 1024), 2)
        }