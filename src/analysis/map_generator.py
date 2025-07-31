# src/analysis/map_generator.py
"""
Módulo para gerar mapas interativos de risco e detecções - Versão Corrigida.
"""
import logging
import folium
import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path

def validate_map_data(gdf, data_name="data"):
    """Valida e limpa dados para o mapa"""
    logger = logging.getLogger(__name__)
    logger.info(f"Validando dados: {data_name}")
    
    if gdf is None or gdf.empty:
        logger.error(f"{data_name} está vazio ou é None")
        return None
    
    # Remove colunas duplicadas
    if gdf.columns.duplicated().any():
        logger.warning(f"Removendo colunas duplicadas em {data_name}")
        gdf = gdf.loc[:, ~gdf.columns.duplicated()]
    
    # Valida geometrias
    if 'geometry' not in gdf.columns:
        logger.error(f"Coluna 'geometry' não encontrada em {data_name}")
        return None
    
    # Remove geometrias inválidas
    invalid_geoms = gdf.geometry.isnull() | (~gdf.geometry.is_valid)
    if invalid_geoms.any():
        logger.warning(f"Removendo {invalid_geoms.sum()} geometrias inválidas de {data_name}")
        gdf = gdf[~invalid_geoms].copy()
    
    if gdf.empty:
        logger.error(f"{data_name} ficou vazio após limpeza")
        return None
    
    logger.info(f"{data_name} validado. Shape: {gdf.shape}")
    return gdf

def prepare_sectors_data(sectors_gdf):
    """Prepara dados dos setores para o mapa"""
    logger = logging.getLogger(__name__)
    
    # Valida dados básicos
    clean_gdf = validate_map_data(sectors_gdf, "setores")
    if clean_gdf is None:
        return None
    
    # Garante que CD_SETOR existe e é string
    if 'CD_SETOR' not in clean_gdf.columns:
        logger.error("Coluna CD_SETOR não encontrada")
        return None
    
    clean_gdf['CD_SETOR'] = clean_gdf['CD_SETOR'].astype(str)
    
    # Garante que risk_score existe e é numérico
    if 'risk_score' not in clean_gdf.columns:
        logger.warning("Coluna risk_score não encontrada, usando valores padrão")
        clean_gdf['risk_score'] = 0.5
    else:
        # Limpa risk_score
        clean_gdf['risk_score'] = pd.to_numeric(clean_gdf['risk_score'], errors='coerce')
        clean_gdf['risk_score'] = clean_gdf['risk_score'].fillna(0.5)
        clean_gdf['risk_score'] = clean_gdf['risk_score'].clip(0, 1)
    
    # Garante que final_risk_level existe
    if 'final_risk_level' not in clean_gdf.columns:
        logger.warning("Coluna final_risk_level não encontrada, criando baseada no risk_score")
        clean_gdf['final_risk_level'] = pd.cut(
            clean_gdf['risk_score'],
            bins=[0, 0.33, 0.66, 1.0],
            labels=['Baixo', 'Médio', 'Alto'],
            include_lowest=True
        ).astype(str)
    else:
        clean_gdf['final_risk_level'] = clean_gdf['final_risk_level'].astype(str)
    
    # Adiciona contagem de piscinas se não existir
    if 'dirty_pool_count' not in clean_gdf.columns:
        clean_gdf['dirty_pool_count'] = 0
    else:
        clean_gdf['dirty_pool_count'] = pd.to_numeric(clean_gdf['dirty_pool_count'], errors='coerce').fillna(0)
    
    logger.info(f"Dados dos setores preparados. Range risk_score: {clean_gdf['risk_score'].min():.3f} - {clean_gdf['risk_score'].max():.3f}")
    return clean_gdf

def prepare_pools_data(pools_gdf):
    """Prepara dados das piscinas para o mapa"""
    logger = logging.getLogger(__name__)
    
    if pools_gdf is None or pools_gdf.empty:
        logger.info("Nenhum dado de piscinas para preparar")
        return None
    
    clean_pools = validate_map_data(pools_gdf, "piscinas")
    if clean_pools is None:
        return None
    
    # Converte colunas categóricas para string
    for col in clean_pools.columns:
        if hasattr(clean_pools[col], 'cat'):
            clean_pools[col] = clean_pools[col].astype(str)
    
    # Garante colunas essenciais
    if 'sector_id' not in clean_pools.columns:
        logger.warning("Coluna sector_id não encontrada em piscinas")
        clean_pools['sector_id'] = 'N/A'
    else:
        clean_pools['sector_id'] = clean_pools['sector_id'].astype(str)
    
    if 'risk_level' not in clean_pools.columns:
        logger.warning("Coluna risk_level não encontrada em piscinas")
        clean_pools['risk_level'] = 'Médio'
    else:
        clean_pools['risk_level'] = clean_pools['risk_level'].astype(str)
    
    if 'pool_confidence' not in clean_pools.columns:
        clean_pools['pool_confidence'] = 0.5
    else:
        clean_pools['pool_confidence'] = pd.to_numeric(clean_pools['pool_confidence'], errors='coerce').fillna(0.5)
    
    logger.info(f"Dados das piscinas preparados. Total: {len(clean_pools)}")
    return clean_pools

def create_priority_map(
    sectors_risk_gdf: gpd.GeoDataFrame,
    dirty_pools_gdf: gpd.GeoDataFrame | None,
    output_html_path: Path
):
    """
    Cria um mapa interativo com camadas de risco por setor e pontos de piscinas sujas.
    Versão robusta com melhor tratamento de erros.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Gerando mapa de priorização para {output_html_path.name}...")
    
    try:
        # Prepara dados dos setores
        clean_sectors = prepare_sectors_data(sectors_risk_gdf)
        if clean_sectors is None:
            logger.error("Não foi possível preparar dados dos setores")
            return False
        
        # Prepara dados das piscinas
        clean_pools = prepare_pools_data(dirty_pools_gdf)
        
        # Calcula centro do mapa
        try:
            bounds = clean_sectors.total_bounds
            center_lat = (bounds[1] + bounds[3]) / 2
            center_lon = (bounds[0] + bounds[2]) / 2
            map_center = [center_lat, center_lon]
            logger.info(f"Centro do mapa: {map_center}")
        except Exception as e:
            logger.warning(f"Erro ao calcular centro do mapa: {e}. Usando centro padrão.")
            map_center = [-22.818, -47.069]
        
        # Cria o mapa base
        m = folium.Map(
            location=map_center, 
            zoom_start=15, 
            tiles="CartoDB positron"
        )
        
        # --- Camada 1: Risco por Setor (Choropleth) ---
        try:
            logger.info("Adicionando camada choropleth...")
            
            # Prepara dados para choropleth
            choropleth_data = clean_sectors[['CD_SETOR', 'risk_score']].copy()
            choropleth_data['CD_SETOR'] = choropleth_data['CD_SETOR'].astype(str)
            
            # Verifica se há variação nos dados
            if choropleth_data['risk_score'].nunique() <= 1:
                logger.warning("Todos os valores de risk_score são iguais. Usando mapa simples.")
                # Usa GeoJson simples em vez de Choropleth
                folium.GeoJson(
                    clean_sectors.to_json(),
                    name='Setores Censitários',
                    style_function=lambda x: {
                        'fillColor': 'orange',
                        'color': 'black',
                        'weight': 1,
                        'fillOpacity': 0.6,
                    },
                    popup=folium.GeoJsonPopup(
                        fields=['CD_SETOR', 'final_risk_level', 'dirty_pool_count'],
                        labels=['Setor:', 'Nível de Risco:', 'Piscinas:'],
                        style="background-color: white; color: black; font-family: arial; font-size: 12px; padding: 10px;"
                    )
                ).add_to(m)
            else:
                # Usa Choropleth normal
                folium.Choropleth(
                    geo_data=clean_sectors.to_json(),
                    name='Risco por Setor Censitário',
                    data=choropleth_data,
                    columns=['CD_SETOR', 'risk_score'],
                    key_on='feature.properties.CD_SETOR',
                    fill_color='YlOrRd',
                    fill_opacity=0.6,
                    line_opacity=0.2,
                    legend_name='Score de Risco Ambiental',
                    highlight=True
                ).add_to(m)
                
                # Adiciona popups informativos
                for idx, row in clean_sectors.iterrows():
                    try:
                        centroid = row.geometry.centroid
                        popup_html = f"""
                        <div style="font-family: Arial, sans-serif; min-width: 200px;">
                            <h4 style="margin: 0; color: #d73027;">📍 Setor {row['CD_SETOR']}</h4>
                            <hr style="margin: 5px 0;">
                            <p><b>Nível de Risco:</b> <span style="color: #d73027;">{row['final_risk_level']}</span></p>
                            <p><b>Score de Risco:</b> {row['risk_score']:.3f}</p>
                            <p><b>Piscinas Detectadas:</b> {int(row['dirty_pool_count'])}</p>
                        </div>
                        """
                        folium.Marker(
                            location=[centroid.y, centroid.x],
                            popup=folium.Popup(popup_html, max_width=300),
                            icon=folium.Icon(color='red', icon='info-sign', prefix='glyphicon')
                        ).add_to(m)
                    except Exception as e:
                        logger.warning(f"Erro ao adicionar popup para setor {row.get('CD_SETOR', 'unknown')}: {e}")
                        continue
            
            logger.info("Camada de setores adicionada com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao adicionar camada de setores: {e}")
            # Fallback: adiciona apenas as geometrias
            try:
                folium.GeoJson(
                    clean_sectors.to_json(),
                    name='Setores (Fallback)',
                    style_function=lambda x: {
                        'fillColor': 'blue',
                        'color': 'black',
                        'weight': 1,
                        'fillOpacity': 0.3,
                    }
                ).add_to(m)
                logger.info("Camada fallback adicionada")
            except Exception as e2:
                logger.error(f"Falha também no fallback: {e2}")
        
        # --- Camada 2: Piscinas Sujas Detectadas ---
        if clean_pools is not None and not clean_pools.empty:
            try:
                logger.info(f"Adicionando {len(clean_pools)} piscinas ao mapa...")
                
                pools_layer = folium.FeatureGroup(name='Piscinas Sujas Detectadas')
                
                added_pools = 0
                for idx, pool in clean_pools.iterrows():
                    try:
                        # Extrai coordenadas de forma segura
                        if hasattr(pool.geometry, 'y') and hasattr(pool.geometry, 'x'):
                            lat, lon = pool.geometry.y, pool.geometry.x
                        else:
                            logger.warning(f"Geometria inválida para piscina no índice {idx}")
                            continue
                        
                        # Valida coordenadas
                        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                            logger.warning(f"Coordenadas inválidas para piscina: lat={lat}, lon={lon}")
                            continue
                        
                        # Extrai atributos de forma segura
                        sector_id = str(pool.get('sector_id', 'N/A'))
                        risk_level = str(pool.get('risk_level', 'N/A'))
                        confidence = pool.get('pool_confidence', 0.5)
                        
                        # Formata confiança
                        if isinstance(confidence, (int, float)):
                            confidence_str = f"{confidence:.1%}" if confidence <= 1 else f"{confidence:.1f}"
                        else:
                            confidence_str = str(confidence)
                        
                        # Define cor baseada no nível de risco
                        color_map = {
                            'Baixo': 'green',
                            'Médio': 'orange', 
                            'Alto': 'red',
                            'Crítico': 'darkred'
                        }
                        marker_color = color_map.get(risk_level, 'blue')
                        
                        popup_html = f"""
                        <div style="font-family: Arial, sans-serif; min-width: 200px;">
                            <h4 style="margin: 0; color: {marker_color};">🏊 Piscina de Risco</h4>
                            <hr style="margin: 5px 0;">
                            <p><b>Setor:</b> {sector_id}</p>
                            <p><b>Nível de Risco do Setor:</b> <span style="color: {marker_color};">{risk_level}</span></p>
                            <p><b>Confiança da Detecção:</b> {confidence_str}</p>
                            <p><small><i>Coordenadas: {lat:.4f}, {lon:.4f}</i></small></p>
                        </div>
                        """
                        
                        folium.CircleMarker(
                            location=[lat, lon],
                            radius=8,
                            color=marker_color,
                            fill=True,
                            fill_color=marker_color,
                            fill_opacity=0.8,
                            popup=folium.Popup(popup_html, max_width=300),
                            tooltip=f"Piscina - Setor {sector_id} ({risk_level})"
                        ).add_to(pools_layer)
                        
                        added_pools += 1
                        
                    except Exception as e:
                        logger.warning(f"Erro ao adicionar piscina no índice {idx}: {e}")
                        continue
                
                if added_pools > 0:
                    pools_layer.add_to(m)
                    logger.info(f"Adicionadas {added_pools} piscinas ao mapa")
                else:
                    logger.warning("Nenhuma piscina foi adicionada ao mapa")
                
            except Exception as e:
                logger.error(f"Erro ao processar camada de piscinas: {e}")
        
        # Adiciona controle de camadas
        try:
            folium.LayerControl().add_to(m)
        except Exception as e:
            logger.warning(f"Erro ao adicionar controle de camadas: {e}")
        
        # Adiciona mini mapa
        try:
            from folium.plugins import MiniMap
            minimap = MiniMap(toggle_display=True)
            m.add_child(minimap)
        except Exception as e:
            logger.info(f"Mini mapa não disponível: {e}")
        
        # Salva o mapa
        try:
            output_html_path.parent.mkdir(parents=True, exist_ok=True)
            m.save(str(output_html_path))
            logger.info(f"✅ Mapa interativo salvo com sucesso em: {output_html_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar mapa: {e}")
            return False
    
    except Exception as e:
        logger.error(f"Erro geral na criação do mapa: {e}")
        logger.error(f"Traceback: {__import__('traceback').format_exc()}")
        return False

def create_simple_map(sectors_gdf: gpd.GeoDataFrame, output_path: Path):
    """Cria um mapa simples apenas com os setores (fallback)"""
    logger = logging.getLogger(__name__)
    logger.info("Criando mapa simples (fallback)...")
    
    try:
        # Calcula centro
        bounds = sectors_gdf.total_bounds
        center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
        
        # Cria mapa básico
        m = folium.Map(location=center, zoom_start=15)
        
        # Adiciona setores
        folium.GeoJson(
            sectors_gdf.to_json(),
            style_function=lambda x: {
                'fillColor': 'lightblue',
                'color': 'black',
                'weight': 1,
                'fillOpacity': 0.5,
            }
        ).add_to(m)
        
        # Salva
        output_path.parent.mkdir(parents=True, exist_ok=True)
        m.save(str(output_path))
        logger.info(f"Mapa simples salvo em: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao criar mapa simples: {e}")
        return False