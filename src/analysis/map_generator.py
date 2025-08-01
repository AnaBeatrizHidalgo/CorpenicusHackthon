# src/analysis/map_generator.py
"""
Módulo para gerar mapas interativos de risco e detecções - Versão com Imagens nos Popups.
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

def get_risk_color(risk_level, risk_score):
    """Retorna cores baseadas no nível de risco"""
    color_map = {
        'Baixo': '#4CAF50',      # Verde
        'Médio': '#FF9800',      # Laranja
        'Alto': '#FF5722',       # Vermelho
        'Crítico': '#D32F2F'     # Vermelho escuro
    }
    return color_map.get(risk_level, '#2196F3')  # Azul como fallback

def create_modern_popup_with_image(title, data_dict, image_base64=None, color="#FF7C33"):
    """Cria popup moderno com imagem incluída"""
    data_rows = ""
    for key, value in data_dict.items():
        data_rows += f"<p style='margin: 5px 0;'><strong>{key}:</strong> {value}</p>"
    
    # Adiciona seção da imagem se disponível
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
        min-width: 320px;
        max-width: 400px;
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
            Dados atualizados em tempo real
        </p>
    </div>
    """
    return popup_html

def create_modern_popup(title, data_dict, color="#FF7C33"):
    """Cria popup moderno sem imagem (versão original)"""
    return create_modern_popup_with_image(title, data_dict, None, color)

def create_priority_map(
    sectors_risk_gdf: gpd.GeoDataFrame,
    dirty_pools_gdf: gpd.GeoDataFrame | None,
    output_html_path: Path
):
    """
    Cria um mapa interativo com design moderno e elegante, incluindo imagens nos popups das piscinas.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Gerando mapa de priorização com imagens para {output_html_path.name}...")
    
    try:
        # Determina diretório de imagens detectadas baseado no output_html_path
        detected_images_dir = output_html_path.parent / "google_detected_images"
        logger.info(f"Diretório de imagens detectadas: {detected_images_dir}")
        
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
        
        # Cria o mapa base com tema dark
        m = folium.Map(
            location=map_center, 
            zoom_start=15, 
            tiles=None  # Vamos adicionar tiles customizados
        )
        
        # Adiciona tile layer dark similar ao index_old.html
        folium.TileLayer(
            'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            name='Dark Theme',
            overlay=False,
            control=True
        ).add_to(m)
        
        # --- Camada 1: Risco por Setor (APENAS CORES, SEM MARCADORES) ---
        try:
            logger.info("Adicionando camada de setores...")
            
            # Verifica se há variação nos dados
            if clean_sectors['risk_score'].nunique() <= 1:
                logger.warning("Todos os valores de risk_score são iguais. Usando cores uniformes.")
                # Usa cores baseadas no nível de risco
                for idx, row in clean_sectors.iterrows():
                    try:
                        risk_color = get_risk_color(row['final_risk_level'], row['risk_score'])
                        
                        # Popup moderno
                        popup_data = {
                            'Setor': row['CD_SETOR'],
                            'Nível de Risco': f"<span style='color: {risk_color}; font-weight: bold;'>{row['final_risk_level']}</span>",
                            'Score de Risco': f"{row['risk_score']:.3f}",
                            'Piscinas Detectadas': f"{int(row['dirty_pool_count'])}"
                        }
                        popup_html = create_modern_popup(
                            f"📍 Setor Censitário", 
                            popup_data, 
                            risk_color
                        )
                        
                        # Adiciona apenas o polígono colorido (SEM marcador)
                        folium.GeoJson(
                            row.geometry,
                            style_function=lambda x, color=risk_color: {
                                'fillColor': color,
                                'color': color,
                                'weight': 2,
                                'fillOpacity': 0.6,
                                'opacity': 0.8
                            },
                            popup=folium.Popup(popup_html, max_width=420),
                            tooltip=f"Setor {row['CD_SETOR']} - {row['final_risk_level']}"
                        ).add_to(m)
                        
                    except Exception as e:
                        logger.warning(f"Erro ao processar setor {row.get('CD_SETOR', 'unknown')}: {e}")
                        continue
            else:
                # Usa Choropleth para variação de cores
                choropleth_data = clean_sectors[['CD_SETOR', 'risk_score']].copy()
                choropleth_data['CD_SETOR'] = choropleth_data['CD_SETOR'].astype(str)
                
                folium.Choropleth(
                    geo_data=clean_sectors.to_json(),
                    name='Mapa de Risco Ambiental',
                    data=choropleth_data,
                    columns=['CD_SETOR', 'risk_score'],
                    key_on='feature.properties.CD_SETOR',
                    fill_color='YlOrRd',
                    fill_opacity=0.7,
                    line_opacity=0.8,
                    line_weight=2,
                    legend_name='Score de Risco (0-1)',
                    highlight=True
                ).add_to(m)
                
                # Adiciona APENAS popups (SEM marcadores de ícone)
                for idx, row in clean_sectors.iterrows():
                    try:
                        centroid = row.geometry.centroid
                        risk_color = get_risk_color(row['final_risk_level'], row['risk_score'])
                        
                        popup_data = {
                            'Setor': row['CD_SETOR'],
                            'Nível de Risco': f"<span style='color: {risk_color}; font-weight: bold;'>{row['final_risk_level']}</span>",
                            'Score de Risco': f"{row['risk_score']:.3f}",
                            'Piscinas Detectadas': f"{int(row['dirty_pool_count'])}"
                        }
                        popup_html = create_modern_popup(
                            f"📍 Setor Censitário", 
                            popup_data, 
                            risk_color
                        )
                        
                        # Marcador invisível apenas para o popup
                        folium.CircleMarker(
                            location=[centroid.y, centroid.x],
                            radius=0.1,  # Muito pequeno, quase invisível
                            color='transparent',
                            fill=False,
                            popup=folium.Popup(popup_html, max_width=420),
                            tooltip=f"Setor {row['CD_SETOR']}"
                        ).add_to(m)
                        
                    except Exception as e:
                        logger.warning(f"Erro ao adicionar popup para setor {row.get('CD_SETOR', 'unknown')}: {e}")
                        continue
            
            logger.info("Camada de setores adicionada com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao adicionar camada de setores: {e}")
            # Fallback simples
            try:
                folium.GeoJson(
                    clean_sectors.to_json(),
                    name='Setores (Fallback)',
                    style_function=lambda x: {
                        'fillColor': '#FF7C33',
                        'color': '#FF7C33',
                        'weight': 2,
                        'fillOpacity': 0.5,
                        'opacity': 0.8
                    }
                ).add_to(m)
                logger.info("Camada fallback adicionada")
            except Exception as e2:
                logger.error(f"Falha também no fallback: {e2}")
        
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
                        
                        # NOVA FUNCIONALIDADE: Busca a imagem da piscina
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
                            popup=folium.Popup(popup_html, max_width=420),
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
        </style>
        """
        m.get_root().html.add_child(folium.Element(custom_css))
        
        # Salva o mapa
        try:
            output_html_path.parent.mkdir(parents=True, exist_ok=True)
            m.save(str(output_html_path))
            logger.info(f"✅ Mapa com imagens salvo com sucesso em: {output_html_path}")
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
        
        # Cria mapa básico com tema dark
        m = folium.Map(location=center, zoom_start=15, tiles=None)
        
        # Adiciona tema dark
        folium.TileLayer(
            'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            attr='&copy; OpenStreetMap &copy; CARTO',
            name='Dark Theme'
        ).add_to(m)
        
        # Adiciona setores
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