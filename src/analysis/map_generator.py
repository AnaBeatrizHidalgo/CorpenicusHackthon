# src/analysis/map_generator.py
"""
Módulo para gerar mapas interativos de risco e detecções - Versão CORRIGIDA com Consistência de Risco.
"""
import logging
import folium
import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path
import base64
import os

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

def encode_image_to_base64(image_path: Path) -> str:
    """Converte uma imagem para base64 para embedar no HTML"""
    try:
        if not image_path.exists():
            return None
        
        with open(image_path, "rb") as img_file:
            encoded_string = base64.b64encode(img_file.read()).decode('utf-8')
            return f"data:image/png;base64,{encoded_string}"
    except Exception as e:
        logging.getLogger(__name__).warning(f"Erro ao codificar imagem {image_path}: {e}")
        return None

def find_pool_image(sector_id: str, detected_images_dir: Path) -> str:
    """Encontra a imagem detectada para uma piscina específica"""
    logger = logging.getLogger(__name__)
    
    if not detected_images_dir.exists():
        logger.warning(f"Diretório de imagens detectadas não existe: {detected_images_dir}")
        return None
    
    # Padrões possíveis de nome de arquivo
    possible_patterns = [
        f"{sector_id}_dirty_pool_detected.png",
        f"{sector_id}_detected.png",
        f"{sector_id}_pool_detected.png"
    ]
    
    for pattern in possible_patterns:
        image_path = detected_images_dir / pattern
        if image_path.exists():
            logger.info(f"Imagem encontrada para setor {sector_id}: {image_path.name}")
            return encode_image_to_base64(image_path)
    
    # Se não encontrar com padrões específicos, procura qualquer arquivo que contenha o sector_id
    for image_file in detected_images_dir.glob("*.png"):
        if str(sector_id) in image_file.name:
            logger.info(f"Imagem encontrada por busca genérica para setor {sector_id}: {image_file.name}")
            return encode_image_to_base64(image_file)
    
    logger.warning(f"Nenhuma imagem encontrada para setor {sector_id}")
    return None

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
    
    risk_score_columns = ['risk_score', 'amplified_risk_score', 'final_risk_score']
    risk_score_col = None
    
    for col in risk_score_columns:
        if col in clean_gdf.columns:
            risk_score_col = col
            logger.info(f"Usando coluna de risco: {col}")
            break
    
    if risk_score_col is None:
        logger.warning("Nenhuma coluna de risk_score encontrada, criando valores padrão")
        clean_gdf['risk_score'] = 0.5
        risk_score_col = 'risk_score'
    else:
        # Limpa risk_score
        clean_gdf['risk_score'] = pd.to_numeric(clean_gdf[risk_score_col], errors='coerce')
        clean_gdf['risk_score'] = clean_gdf['risk_score'].fillna(0.5)
        clean_gdf['risk_score'] = clean_gdf['risk_score'].clip(0, 1)
    
    risk_level_columns = ['final_risk_level', 'risk_level', 'risk_category']
    risk_level_col = None
    
    for col in risk_level_columns:
        if col in clean_gdf.columns:
            risk_level_col = col
            logger.info(f"Usando coluna de nível: {col}")
            break
    
    if risk_level_col is None:
        logger.warning("Nenhuma coluna de nível de risco encontrada, criando baseada no risk_score")
        clean_gdf['final_risk_level'] = pd.cut(
            clean_gdf['risk_score'],
            bins=[0, 0.33, 0.66, 1.0],
            labels=['Baixo', 'Médio', 'Alto'],
            include_lowest=True
        ).astype(str)
    else:
        clean_gdf['final_risk_level'] = clean_gdf[risk_level_col].astype(str)
    
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

def get_risk_color(risk_level, risk_score):
    """Retorna cores baseadas no nível de risco"""
    color_map = {
        'Baixo': '#4CAF50',      # Verde
        'Médio': '#FF9800',      # Laranja
        'Alto': '#FF5722',       # Vermelho
        'Crítico': '#D32F2F'     # Vermelho escuro
    }
    return color_map.get(risk_level, '#2196F3')  # Azul como fallback

def calculate_risk_percentiles(sectors_gdf):
    logger = logging.getLogger(__name__)
    
    if 'risk_score' not in sectors_gdf.columns:
        logger.warning("Coluna risk_score não encontrada para calcular percentis")
        return {'p90': 0.75, 'p70': 0.50}
    
    try:
        percentile_90 = sectors_gdf['risk_score'].quantile(0.90)  # Top 10%
        percentile_70 = sectors_gdf['risk_score'].quantile(0.70)  # Top 30%
        
        logger.info(f"📊 Percentis calculados - P90: {percentile_90:.4f}, P70: {percentile_70:.4f}")
        
        return {
            'p90': percentile_90,
            'p70': percentile_70
        }
    except Exception as e:
        logger.warning(f"Erro ao calcular percentis: {e}")
        return {'p90': 0.75, 'p70': 0.50}  # Valores padrão

def format_risk_percentage(risk_score, risk_level, percentiles):
 
    if pd.isna(risk_score):
        return "N/A"
    
    percentage = risk_score * 100
    
    if risk_level == 'Alto':
        interpretation = "🔴 Alto Risco"
        bar_color = "#FF5722"
        description = f"Setor no top 10% de risco da região"
    elif risk_level == 'Médio':
        interpretation = "🟠 Risco Médio"
        bar_color = "#FF9800"
        description = f"Setor no top 30% de risco da região"
    elif risk_level == 'Crítico':
        interpretation = "🔴 Risco Crítico"
        bar_color = "#D32F2F"
        description = f"Setor de risco extremo"
    else:  # Baixo
        interpretation = "🟢 Baixo Risco"
        bar_color = "#4CAF50"
        description = f"Setor com risco abaixo da média regional"
    
    percentil_info = ""
    if risk_score >= percentiles['p90']:
        percentil_info = f"(Top 10% - Acima de {percentiles['p90']*100:.1f}%)"
    elif risk_score >= percentiles['p70']:
        percentil_info = f"(Top 30% - Acima de {percentiles['p70']*100:.1f}%)"
    else:
        percentil_info = f"(Abaixo do percentil 70)"
    
    bar_width = int(percentage)
    progress_bar = f"""
    <div style="margin: 10px 0;">
        <div style="
            background: rgba(255,255,255,0.2); 
            border-radius: 10px; 
            height: 20px; 
            overflow: hidden;
            position: relative;
        ">
            <div style="
                background: {bar_color}; 
                height: 100%; 
                width: {bar_width}%; 
                border-radius: 10px;
                transition: width 0.3s ease;
            "></div>
            <span style="
                position: absolute; 
                top: 50%; 
                left: 50%; 
                transform: translate(-50%, -50%); 
                color: white; 
                font-weight: bold; 
                font-size: 12px;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.8);
            ">{percentage:.1f}%</span>
        </div>
        <p style="
            margin: 5px 0; 
            text-align: center; 
            font-weight: bold; 
            color: {bar_color};
        ">{interpretation}</p>
        <p style="
            margin: 2px 0; 
            text-align: center; 
            font-size: 10px; 
            color: #cccccc;
        ">{description}</p>
        <p style="
            margin: 2px 0; 
            text-align: center; 
            font-size: 9px; 
            color: #aaaaaa;
        ">{percentil_info}</p>
    </div>
    """
    
    return progress_bar

def create_modern_popup_with_image(title, data_dict, image_base64=None, color="#FF7C33"):
    data_rows = ""
    for key, value in data_dict.items():
        data_rows += f"<p style='margin: 5px 0;'><strong>{key}:</strong> {value}</p>"
    
    image_section = ""
    if image_base64:
        image_section = f"""
        <div style="margin: 15px 0; text-align: center;">
            <h5 style="color: {color}; margin-bottom: 10px; font-size: 1.1rem;">📸 Imagem da Detecção</h5>
            <img src="{image_base64}" 
                 style="
                     max-width: 300px; 
                     max-height: 200px; 
                     border-radius: 10px; 
                     border: 2px solid {color}; 
                     box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
                     object-fit: contain;
                 " 
                 alt="Piscina Detectada"
                 onclick="this.style.maxWidth = this.style.maxWidth === '600px' ? '300px' : '600px'; this.style.maxHeight = this.style.maxHeight === '400px' ? '200px' : '400px';"
                 title="Clique para ampliar/reduzir"
            />
            <p style="font-size: 10px; color: #cccccc; margin-top: 5px;">
                💡 Clique na imagem para ampliar
            </p>
        </div>
        """
    
    popup_html = f"""
    <div style="
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background: linear-gradient(135deg, rgba(26, 36, 68, 0.95) 0%, rgba(10, 22, 40, 0.95) 100%);
        color: #ffffff;
        padding: 20px;
        border-radius: 15px;
        min-width: 350px;
        max-width: 450px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 124, 51, 0.3);
    ">
        <h4 style="
            margin: 0 0 15px 0; 
            color: {color}; 
            display: flex; 
            align-items: center;
            font-size: 1.2rem;
            font-weight: bold;
        ">
            {title}
        </h4>
        <hr style="
            margin: 15px 0; 
            border: none; 
            height: 1px; 
            background: rgba(255, 124, 51, 0.3);
        ">
        {data_rows}
        {image_section}
        <hr style="
            margin: 15px 0; 
            border: none; 
            height: 1px; 
            background: rgba(255, 124, 51, 0.3);
        ">
        <p style="
            margin: 0; 
            font-size: 11px; 
            color: #cccccc;
            display: flex;
            align-items: center;
        ">
            <i class="fas fa-clock" style="margin-right: 5px;"></i>
            Análise baseada em dados satelitais e climáticos
        </p>
    </div>
    """
    return popup_html

def create_modern_popup(title, data_dict, color="#FF7C33"):
    return create_modern_popup_with_image(title, data_dict, None, color)

def create_priority_map(
    sectors_risk_gdf: gpd.GeoDataFrame,
    dirty_pools_gdf: gpd.GeoDataFrame | None,
    output_html_path: Path
):

    logger = logging.getLogger(__name__)
    logger.info(f"Gerando mapa de priorização com porcentagem de risco CONSISTENTE para {output_html_path.name}...")
    
    try:
        detected_images_dir = output_html_path.parent / "google_detected_images"
        logger.info(f"Diretório de imagens detectadas: {detected_images_dir}")
        
        clean_sectors = prepare_sectors_data(sectors_risk_gdf)
        if clean_sectors is None:
            logger.error("Não foi possível preparar dados dos setores")
            return False
        
        percentiles = calculate_risk_percentiles(clean_sectors)
        logger.info(f"📊 Usando percentis para consistência: {percentiles}")
        
        logger.info(f"Range de risk_score nos setores: {clean_sectors['risk_score'].min():.3f} - {clean_sectors['risk_score'].max():.3f}")
        logger.info(f"Distribuição de níveis de risco: {clean_sectors['final_risk_level'].value_counts().to_dict()}")
        
        clean_pools = prepare_pools_data(dirty_pools_gdf)
        
        try:
            bounds = clean_sectors.total_bounds
            center_lat = (bounds[1] + bounds[3]) / 2
            center_lon = (bounds[0] + bounds[2]) / 2
            map_center = [center_lat, center_lon]
            logger.info(f"Centro do mapa: {map_center}")
        except Exception as e:
            logger.warning(f"Erro ao calcular centro do mapa: {e}. Usando centro padrão.")
            map_center = [-22.818, -47.069]
        
        m = folium.Map(
            location=map_center, 
            zoom_start=15, 
            tiles=None  
        )
        
        folium.TileLayer(
            'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            name='Dark Theme',
            overlay=False,
            control=True
        ).add_to(m)
        
        try:
            logger.info("Adicionando camada de setores com popups de porcentagem CONSISTENTES...")
            
            sectors_layer = folium.FeatureGroup(name='🎯 Setores de Risco')
            
            for idx, row in clean_sectors.iterrows():
                try:
                    risk_color = get_risk_color(row['final_risk_level'], row['risk_score'])
                    
                    risk_percentage_html = format_risk_percentage(
                        row['risk_score'], 
                        row['final_risk_level'], 
                        percentiles
                    )
                    
                    popup_data = {
                        'Código do Setor': row['CD_SETOR'],
                        'Nível de Risco': f"<span style='color: {risk_color}; font-weight: bold; font-size: 14px;'>{row['final_risk_level']}</span>",
                        'Análise de Risco': risk_percentage_html,
                        'Piscinas Detectadas': f"<span style='color: #FF7C33; font-weight: bold;'>{int(row['dirty_pool_count'])}</span>",
                    }
                    
                    if 't2m_mean' in row and pd.notna(row['t2m_mean']):
                        popup_data['Temperatura Média'] = f"{row['t2m_mean']:.1f}°C"
                    
                    if 'tp_mean' in row and pd.notna(row['tp_mean']):
                        precip_mm = row['tp_mean'] * 1000 * 30  # Converte para mm/mês
                        popup_data['Precipitação'] = f"{precip_mm:.1f} mm/mês"
                    
                    if 'ndvi_mean' in row and pd.notna(row['ndvi_mean']):
                        popup_data['Índice de Vegetação'] = f"{row['ndvi_mean']:.3f}"
                    
                    popup_html = create_modern_popup(
                        f"🎯 Análise de Risco - Setor {row['CD_SETOR']}", 
                        popup_data, 
                        risk_color
                    )
                    
                    folium.GeoJson(
                        row.geometry,
                        style_function=lambda x, color=risk_color: {
                            'fillColor': color,
                            'color': color,
                            'weight': 2,
                            'fillOpacity': 0.7,
                            'opacity': 0.9
                        },
                        popup=folium.Popup(popup_html, max_width=500),
                        tooltip=f"🎯 Setor {row['CD_SETOR']} - Risco: {row['risk_score']*100:.1f}% ({row['final_risk_level']})"
                    ).add_to(sectors_layer)
                    
                except Exception as e:
                    logger.warning(f"Erro ao processar setor {row.get('CD_SETOR', 'unknown')}: {e}")
                    continue
            
            sectors_layer.add_to(m)
            logger.info("✅ Camada de setores com porcentagem de risco CONSISTENTE adicionada com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao adicionar camada de setores: {e}")
            return False
        
        # --- Camada 2: Piscinas com Imagens nos Popups ---
        if clean_pools is not None and not clean_pools.empty:
            try:
                logger.info(f"Adicionando {len(clean_pools)} piscinas com imagens nos popups...")
                
                pools_layer = folium.FeatureGroup(name='🏊 Piscinas de Risco Detectadas')
                
                added_pools = 0
                for idx, pool in clean_pools.iterrows():
                    try:
                        # Extrai coordenadas
                        if hasattr(pool.geometry, 'y') and hasattr(pool.geometry, 'x'):
                            lat, lon = pool.geometry.y, pool.geometry.x
                        else:
                            logger.warning(f"Geometria inválida para piscina no índice {idx}")
                            continue
                        
                        # Valida coordenadas
                        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                            logger.warning(f"Coordenadas inválidas para piscina: lat={lat}, lon={lon}")
                            continue
                        
                        # Extrai atributos
                        sector_id = str(pool.get('sector_id', 'N/A'))
                        risk_level = str(pool.get('risk_level', 'Médio'))
                        confidence = pool.get('pool_confidence', 0.5)
                        
                        # Define cor baseada no risco
                        risk_color = get_risk_color(risk_level, 0)
                        
                        # Formata confiança
                        if isinstance(confidence, (int, float)):
                            confidence_str = f"{confidence:.1%}" if confidence <= 1 else f"{confidence:.1f}"
                        else:
                            confidence_str = str(confidence)
                        
                        # Determina status baseado no risco
                        status_map = {
                            'Baixo': 'Monitorado',
                            'Médio': 'Ativo', 
                            'Alto': 'Em Tratamento',
                            'Crítico': 'Crítico'
                        }
                        status = status_map.get(risk_level, 'Ativo')
                        
                        pool_image_base64 = find_pool_image(sector_id, detected_images_dir)
                        
                        # Popup moderno com imagem
                        popup_data = {
                            'Localização': f"Setor {sector_id}",
                            'Confiança da Detecção': confidence_str,
                            'Nível de Risco do Setor': f"<span style='color: {risk_color}; font-weight: bold;'>{risk_level}</span>",
                            'Status': f"""<span style="
                                padding: 3px 10px; 
                                border-radius: 12px; 
                                font-size: 12px; 
                                background: {risk_color}; 
                                color: white;
                                font-weight: bold;
                            ">{status}</span>""",
                            'Coordenadas': f"{lat:.4f}, {lon:.4f}"
                        }
                        
                        # Usa o popup com imagem se disponível
                        popup_html = create_modern_popup_with_image(
                            "🏊 Piscina de Risco Detectada", 
                            popup_data, 
                            pool_image_base64,
                            risk_color
                        )
                        
                        # Cria marcador customizado
                        custom_icon = folium.DivIcon(
                            html=f"""
                            <div style="
                                background: {risk_color}; 
                                color: white; 
                                border-radius: 50%; 
                                width: 30px; 
                                height: 30px; 
                                display: flex; 
                                align-items: center; 
                                justify-content: center; 
                                font-weight: bold; 
                                font-size: 14px; 
                                border: 3px solid white; 
                                box-shadow: 0 4px 15px rgba({int(risk_color[1:3], 16)}, {int(risk_color[3:5], 16)}, {int(risk_color[5:7], 16)}, 0.5);
                                font-family: 'Font Awesome 5 Free';
                            ">
                                🏊
                            </div>
                            """,
                            icon_size=(30, 30),
                            icon_anchor=(15, 15)
                        )
                        
                        folium.Marker(
                            location=[lat, lon],
                            icon=custom_icon,
                            popup=folium.Popup(popup_html, max_width=500),
                            tooltip=f"Piscina - Setor {sector_id} ({risk_level})"
                        ).add_to(pools_layer)
                        
                        added_pools += 1
                        
                        # Log se encontrou imagem
                        if pool_image_base64:
                            logger.info(f"✅ Piscina no setor {sector_id} adicionada COM imagem")
                        else:
                            logger.info(f"⚠️ Piscina no setor {sector_id} adicionada SEM imagem")
                        
                    except Exception as e:
                        logger.warning(f"Erro ao adicionar piscina no índice {idx}: {e}")
                        continue
                
                if added_pools > 0:
                    pools_layer.add_to(m)
                    logger.info(f"✅ Adicionadas {added_pools} piscinas ao mapa com funcionalidade de imagem")
                else:
                    logger.warning("Nenhuma piscina foi adicionada ao mapa")
                
            except Exception as e:
                logger.error(f"Erro ao processar camada de piscinas: {e}")
        
        # Adiciona controle de camadas
        try:
            folium.LayerControl(position='topright').add_to(m)
        except Exception as e:
            logger.warning(f"Erro ao adicionar controle de camadas: {e}")
        
        # Adiciona mini mapa
        try:
            from folium.plugins import MiniMap
            minimap = MiniMap(
                tile_layer='https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
                toggle_display=True,
                width=150,
                height=150
            )
            m.add_child(minimap)
        except Exception as e:
            logger.info(f"Mini mapa não disponível: {e}")
        
        # Adiciona CSS customizado para melhorar o visual
        custom_css = """
        <style>
        .leaflet-popup-content-wrapper {
            background: transparent !important;
            box-shadow: none !important;
            border-radius: 15px !important;
        }
        .leaflet-popup-content {
            margin: 0 !important;
            line-height: 1.4 !important;
        }
        .leaflet-popup-tip {
            background: rgba(26, 36, 68, 0.95) !important;
            border: 1px solid rgba(255, 124, 51, 0.3) !important;
        }
        .leaflet-control-layers {
            background: rgba(26, 36, 68, 0.9) !important;
            color: white !important;
            border-radius: 10px !important;
            backdrop-filter: blur(10px) !important;
        }
        .leaflet-control-layers-expanded {
            padding: 15px !important;
        }
        .leaflet-control-layers label {
            color: white !important;
        }
        /* Estilo para as imagens nos popups */
        .leaflet-popup-content img {
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .leaflet-popup-content img:hover {
            opacity: 0.8;
            transform: scale(1.02);
        }
        /* Estilo para as barras de progresso */
        .risk-progress-bar {
            animation: fillBar 1s ease-in-out;
        }
        @keyframes fillBar {
            from { width: 0%; }
            to { width: var(--target-width); }
        }
        </style>
        """
        m.get_root().html.add_child(folium.Element(custom_css))
        
        # Adiciona JavaScript para interatividade extra
        interactive_js = """
        <script>
        // Adiciona funcionalidade de clique nos setores para mostrar mais detalhes
        document.addEventListener('DOMContentLoaded', function() {
            console.log('🎯 Mapa de Risco de Dengue carregado com funcionalidade de porcentagem CONSISTENTE');
            
            // Adiciona evento para copiar coordenadas ao clicar
            document.addEventListener('click', function(e) {
                if (e.target.closest('.leaflet-popup-content')) {
                    const coordElement = e.target.closest('.leaflet-popup-content').querySelector('[data-coords]');
                    if (coordElement && e.shiftKey) {
                        navigator.clipboard.writeText(coordElement.textContent);
                        alert('Coordenadas copiadas: ' + coordElement.textContent);
                    }
                }
            });
        });
        </script>
        """
        m.get_root().html.add_child(folium.Element(interactive_js))
        
        legend_html = f"""
        <div style="
            position: fixed; 
            top: 10px; left: 10px; width: 220px; height: auto; 
            background: rgba(26, 36, 68, 0.9); 
            border: 1px solid rgba(255, 124, 51, 0.3);
            border-radius: 10px; 
            z-index: 9999; 
            font-size: 12px;
            backdrop-filter: blur(10px);
            padding: 15px;
            color: white;
        ">
        <h4 style="margin: 0 0 10px 0; color: #FF7C33;">📊 Legenda de Risco (Baseada em Percentis)</h4>
        <div style="margin: 8px 0;">
            <span style="background: #4CAF50; width: 15px; height: 15px; display: inline-block; border-radius: 3px; margin-right: 8px;"></span>
            Baixo (< {percentiles['p70']*100:.1f}%)
        </div>
        <div style="margin: 8px 0;">
            <span style="background: #FF9800; width: 15px; height: 15px; display: inline-block; border-radius: 3px; margin-right: 8px;"></span>
            Médio ({percentiles['p70']*100:.1f}% - {percentiles['p90']*100:.1f}%)
        </div>
        <div style="margin: 8px 0;">
            <span style="background: #FF5722; width: 15px; height: 15px; display: inline-block; border-radius: 3px; margin-right: 8px;"></span>
            Alto (≥ {percentiles['p90']*100:.1f}%)
        </div>
        <hr style="border: none; height: 1px; background: rgba(255, 124, 51, 0.3); margin: 10px 0;">
        <p style="margin: 5px 0; font-size: 10px; color: #cccccc;">
            💡 <strong>Classificação por Percentis:</strong><br>
            • Alto = Top 10% da região<br>
            • Médio = Top 30% da região<br>
            • Baixo = Demais setores<br><br>
            🏊 Círculos coloridos = Piscinas detectadas<br>
            ⌨️ Shift+Click = Copiar coordenadas
        </p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Salva o mapa
        try:
            output_html_path.parent.mkdir(parents=True, exist_ok=True)
            m.save(str(output_html_path))
            logger.info(f"✅ Mapa com porcentagem de risco CONSISTENTE salvo com sucesso em: {output_html_path}")
            
            total_sectors = len(clean_sectors)
            high_risk_sectors = len(clean_sectors[clean_sectors['final_risk_level'] == 'Alto'])
            medium_risk_sectors = len(clean_sectors[clean_sectors['final_risk_level'] == 'Médio'])
            avg_risk = clean_sectors['risk_score'].mean() * 100
            
            logger.info(f"📊 Estatísticas CORRIGIDAS do mapa:")
            logger.info(f"   Total de setores: {total_sectors}")
            logger.info(f"   Setores de alto risco (percentil ≥90%): {high_risk_sectors}")
            logger.info(f"   Setores de médio risco (percentil 70-90%): {medium_risk_sectors}")
            logger.info(f"   Risco médio geral: {avg_risk:.1f}%")
            logger.info(f"   Percentil 90% (Alto): {percentiles['p90']*100:.1f}%")
            logger.info(f"   Percentil 70% (Médio): {percentiles['p70']*100:.1f}%")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar mapa: {e}")
            return False
    
    except Exception as e:
        logger.error(f"Erro geral na criação do mapa: {e}")
        logger.error(f"Traceback: {__import__('traceback').format_exc()}")
        return False

def create_simple_map(sectors_gdf: gpd.GeoDataFrame, output_path: Path):
    logger = logging.getLogger(__name__)
    logger.info("Criando mapa simples (fallback)...")
    
    try:
        bounds = sectors_gdf.total_bounds
        center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
        
        m = folium.Map(location=center, zoom_start=15, tiles=None)
        
        folium.TileLayer(
            'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            attr='&copy; OpenStreetMap &copy; CARTO',
            name='Dark Theme'
        ).add_to(m)
        
        folium.GeoJson(
            sectors_gdf.to_json(),
            style_function=lambda x: {
                'fillColor': '#FF7C33',
                'color': '#FF7C33',
                'weight': 2,
                'fillOpacity': 0.6,
                'opacity': 0.8
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