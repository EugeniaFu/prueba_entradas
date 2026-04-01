#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de búsqueda de códigos postales usando Excel local
"""

import pandas as pd
import os
from typing import Dict, List, Optional
import time

class CodigosPostalesExcel:
    """
    Manejador de códigos postales usando archivo Excel local
    """
    
    def __init__(self, excel_path: str = 'Codigos_postales.xls'):
        self.excel_path = excel_path
        self.cache = {}  # Cache para optimizar búsquedas repetidas
        self.state_mapping = {
            # Mapeo de nombres de estados en el Excel a nombres estándar
            'Distrito_Federal': 'Ciudad de México',
            'Coahuila_de_Zaragoza': 'Coahuila',
            'Michoacán_de_Ocampo': 'Michoacán',
            'Veracruz_de_Ignacio_de_la_Llave': 'Veracruz'
        }
        
    def get_state_from_cp(self, cp: str) -> Optional[str]:
        """
        Determina el estado más probable basado en el código postal
        """
        cp_int = int(cp)
        
        # Mapeo aproximado por rangos de CP (principales) 
        if 1000 <= cp_int <= 16999:
            return 'Distrito_Federal'
        elif 20000 <= cp_int <= 23999:
            return 'Aguascalientes'  # Aproximado, puede variar
        elif 24000 <= cp_int <= 24999:
            return 'Campeche'
        elif 44000 <= cp_int <= 45999:
            return 'Jalisco'
        elif 64000 <= cp_int <= 66999:
            return 'Nuevo_León'
        # Agregar más rangos según necesidad
        
        return None
    
    def buscar_colonias(self, codigo_postal: str) -> Dict:
        """
        Busca colonias por código postal en el Excel local
        
        Args:
            codigo_postal: CP de 5 dígitos (ej: "24095")
            
        Returns:
            Dict con success, estado, municipio, colonias, fuente
        """
        
        try:
            # Normalizar CP
            cp = codigo_postal.zfill(5)
            cp_int = int(cp)
            
            # Verificar cache
            if cp in self.cache:
                result = self.cache[cp].copy()
                result['fuente'] = f'Excel Local (Cache) 🚀'
                return result
            
            print(f'🔍 Buscando CP {cp} en Excel local...')
            start_time = time.time()
            
            # Primero, intentar encontrar el estado por rango de CP
            probable_state = self.get_state_from_cp(cp)
            states_to_search = []
            
            if probable_state:
                states_to_search.append(probable_state)
            
            # Si no encuentra por rango, buscar en todos los estados principales
            main_states = ['Campeche', 'Distrito_Federal', 'Jalisco', 'Nuevo_León', 
                          'México', 'Puebla', 'Guanajuato', 'Veracruz_de_Ignacio_de_la_Llave']
            
            for state in main_states:
                if state not in states_to_search:
                    states_to_search.append(state)
            
            # Buscar en los estados candidatos
            for state_name in states_to_search:
                try:
                    print(f'   📍 Consultando {state_name}...')
                    df = pd.read_excel(self.excel_path, sheet_name=state_name)
                    
                    # Buscar por código postal (columna d_codigo)
                    matches = df[df['d_codigo'] == cp_int]
                    
                    if len(matches) > 0:
                        # Extraer datos
                        primer_registro = matches.iloc[0]
                        colonias = matches['d_asenta'].unique().tolist()
                        
                        # Limpiar nombres de colonias
                        colonias = [col.strip() for col in colonias if pd.notna(col) and col.strip()]
                        
                        # Preparar resultado
                        estado_limpio = self.state_mapping.get(state_name, state_name.replace('_', ' '))
                        
                        resultado = {
                            'success': True,
                            'estado': estado_limpio,
                            'municipio': primer_registro['D_mnpio'],
                            'colonias': sorted(colonias),  # Ordenadas alfabéticamente
                            'fuente': f'Excel Local ⚡ ({len(colonias)} colonias)'
                        }
                        
                        # Guardar en cache
                        self.cache[cp] = resultado.copy()
                        
                        elapsed = time.time() - start_time
                        print(f'   ✅ Encontrado en {elapsed:.3f}s - {len(colonias)} colonias')
                        
                        return resultado
                        
                except Exception as e:
                    print(f'   ⚠️ Error en {state_name}: {e}')
                    continue
            
            # Si no se encuentra en ningún estado
            print(f'   ❌ CP {cp} no encontrado en Excel')
            return {
                'success': False,
                'message': f'CP {codigo_postal} no encontrado en archive local.'
            }
            
        except Exception as e:
            print(f'❌ Error buscando CP {codigo_postal}: {e}')
            return {
                'success': False,
                'message': f'Error procesando CP {codigo_postal}: {str(e)}'
            }

# Función de prueba
def test_excel_search():
    """Función de prueba para validar el sistema"""
    
    print('🧪 PROBANDO SISTEMA DE BÚSQUEDA EN EXCEL...')
    
    buscador = CodigosPostalesExcel()
    
    # Casos de prueba
    test_cases = [
        '24095',  # Campeche - sabemos que tiene 11 colonias
        '24000',  # Campeche Centro
        '01000',  # Ciudad de México
        '44100',  # Guadalajara  
        '99999'   # CP inexistente
    ]
    
    for cp in test_cases:
        print(f'\n🎯 Probando CP {cp}:')
        resultado = buscador.buscar_colonias(cp)
        
        if resultado['success']:
            print(f"   ✅ {resultado['estado']}, {resultado['municipio']}")
            print(f"   🏘️ Colonias: {resultado['colonias'][:3]}{'...' if len(resultado['colonias']) > 3 else ''}")
            print(f"   📊 {resultado['fuente']}")
        else:
            print(f"   ❌ {resultado['message']}")

if __name__ == '__main__':
    test_excel_search()