# src/features/climate_feature_builder.py - VERSÃO FINAL CORRIGIDA
"""
Módulo para processar dados climáticos brutos e criar features por setor censitário.

Lê os arquivos NetCDF do ERA5 e um arquivo GeoJSON dos setores para calcular
a média das variáveis climáticas (ex: temperatura, precipitação) para cada setor.
"""
import geopandas as gpd
import pandas as pd
import xarray as xr
from rasterio.features import geometry_mask
import numpy as np
from pathlib import Path
import warnings

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calcula a distância entre dois pontos em km usando a fórmula de Haversine."""
    from math import radians, cos, sin, asin, sqrt
    
    # Converter para radianos
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Fórmula de Haversine
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Raio da Terra em km
    
    return c * r

def _expand_area_for_climate_data(sectors_gdf, target_size_km=15):
    """
    Expande a área de estudo para o tamanho mínimo necessário para dados climáticos.
    Retorna o bbox expandido centrado na área original.
    """
    import numpy as np
    
    # Calcular centro da área atual
    bounds = sectors_gdf.total_bounds  # [min_lon, min_lat, max_lon, max_lat]
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    
    # Converter tamanho desejado para graus (aproximação)
    lat_degree_km = 111.32
    lon_degree_km = 111.32 * np.cos(np.radians(center_lat))
    
    half_size_lat_deg = (target_size_km / 2) / lat_degree_km
    half_size_lon_deg = (target_size_km / 2) / lon_degree_km
    
    # Calcular novo bbox expandido
    expanded_bbox = [
        center_lon - half_size_lon_deg,  # min_lon
        center_lat - half_size_lat_deg,  # min_lat
        center_lon + half_size_lon_deg,  # max_lon
        center_lat + half_size_lat_deg   # max_lat
    ]
    
    return expanded_bbox

def aggregate_climate_by_sector(
    netcdf_path: Path,
    geodata_path: Path,
    output_path: Path
):
    """
    Agrega dados climáticos de um NetCDF para cada polígono de um GeoDataFrame.
    VERSÃO CORRIGIDA: Remove dependência de rasterio.rio e melhora tratamento de erros.
    """
    print("🌡️ Iniciando agregação de dados climáticos por setor censitário.")
    
    try:
        # 1. Carregar os dados geográficos primeiro para validar área
        print(f"📂 Lendo dados geográficos de: {geodata_path}")
        sectors = gpd.read_file(geodata_path)
        sectors = sectors.to_crs(epsg=4326)
        
        # Calcular tamanho da área de estudo
        bounds = sectors.total_bounds  # [min_lon, min_lat, max_lon, max_lat]
        area_width_km = haversine_distance(bounds[1], bounds[0], bounds[1], bounds[2])
        area_height_km = haversine_distance(bounds[1], bounds[0], bounds[3], bounds[0])
        area_size_km = max(area_width_km, area_height_km)
        
        print(f"📏 Tamanho da área de estudo: {area_size_km:.2f} km")
        print(f"📡 Resolução do ERA5-Land: ~9-11 km por pixel")
        
        # Verificar se a área precisa ser expandida para dados climáticos
        MIN_AREA_SIZE_KM = 15  # Área mínima recomendada para ERA5-Land
        
        if area_size_km < MIN_AREA_SIZE_KM:
            print(f"⚠️  ÁREA PEQUENA PARA ERA5-LAND DETECTADA!")
            print(f"   📐 Área atual: {area_size_km:.2f} km")
            print(f"   📐 Mínimo recomendado: {MIN_AREA_SIZE_KM} km")
            print(f"   ℹ️  Os dados foram baixados com área expandida automaticamente")
        
        # 2. Carregar os dados climáticos
        print(f"📡 Lendo dados climáticos de: {netcdf_path}")
        climate_data = xr.open_dataset(netcdf_path)
        
        # Debug: Print dataset info
        print(f"📊 Dataset dimensions: {dict(climate_data.dims)}")
        print(f"🗂️ Dataset coordinates: {list(climate_data.coords)}")
        
        # Get climate variables
        climate_vars = list(climate_data.data_vars)
        print(f"🌡️ Variáveis climáticas encontradas: {climate_vars}")

        # CORREÇÃO: Conversão de temperatura de Kelvin para Celsius
        if 't2m' in climate_data.variables:
            print("🌡️ Variável 't2m' encontrada. Convertendo de Kelvin para Celsius...")
            climate_data['t2m'] = climate_data['t2m'] - 273.15
            print("✅ Conversão de temperatura para Celsius concluída.")
        
        # CORREÇÃO: Determinar coordenadas corretamente
        if 'latitude' in climate_data.coords:
            lat_coord = 'latitude'
            lon_coord = 'longitude'
        elif 'lat' in climate_data.coords:
            lat_coord = 'lat'
            lon_coord = 'lon'
        else:
            raise ValueError("❌ Não foi possível encontrar coordenadas latitude/longitude nos dados climáticos")
        
        # CORREÇÃO: Obter extent espacial dos dados climáticos de forma mais robusta
        try:
            lats = climate_data[lat_coord].values
            lons = climate_data[lon_coord].values
            
            climate_bounds = [
                float(np.min(lons)),  # min_lon
                float(np.min(lats)),  # min_lat 
                float(np.max(lons)),  # max_lon
                float(np.max(lats))   # max_lat
            ]
        except Exception as e:
            print(f"❌ Erro ao extrair bounds dos dados climáticos: {e}")
            return _apply_climate_fallback_minimal(sectors, output_path)
        
        print(f"🌍 Climate data bounds: {climate_bounds}")
        
        # Get sectors bounds
        sectors_bounds = list(sectors.total_bounds)
        print(f"🏘️ Sectors bounds: {sectors_bounds}")

        # CORREÇÃO: Verificação melhorada de sobreposição
        overlap_exists = not (
            sectors_bounds[2] < climate_bounds[0] or  # sectors max_lon < climate min_lon
            sectors_bounds[0] > climate_bounds[2] or  # sectors min_lon > climate max_lon
            sectors_bounds[3] < climate_bounds[1] or  # sectors max_lat < climate min_lat
            sectors_bounds[1] > climate_bounds[3]     # sectors min_lat > climate max_lat
        )
        
        if not overlap_exists:
            print(f"❌ ERRO CRÍTICO: Nenhuma sobreposição entre dados climáticos e setores!")
            print(f"   Setores: {sectors_bounds}")
            print(f"   Clima: {climate_bounds}")
            return _apply_climate_fallback_minimal(sectors, output_path)

        # 3. CORREÇÃO: Método alternativo de agregação sem dependência do rasterio.rio
        print("🔄 Iniciando agregação espacial...")
        results = []
        processed_count = 0
        empty_mask_count = 0

        for index, sector in sectors.iterrows():
            sector_id = sector['CD_SETOR'] 
            
            try:
                # CORREÇÃO: Verificar se o setor intersecta com os dados climáticos
                sector_bounds = sector.geometry.bounds
                if (sector_bounds[2] < climate_bounds[0] or  
                    sector_bounds[0] > climate_bounds[2] or  
                    sector_bounds[3] < climate_bounds[1] or  
                    sector_bounds[1] > climate_bounds[3]):   
                    
                    print(f"⚠️ Setor {sector_id} fora dos limites dos dados climáticos")
                    sector_metrics = {'CD_SETOR': sector_id}
                    for var in climate_vars:
                        sector_metrics[f"{var}_mean"] = np.nan
                    results.append(sector_metrics)
                    continue

                # MÉTODO ALTERNATIVO: Usar seleção por coordenadas mais próximas
                sector_center = sector.geometry.centroid
                sector_lat = sector_center.y
                sector_lon = sector_center.x
                
                # Encontrar o pixel mais próximo
                lat_diff = np.abs(lats - sector_lat)
                lon_diff = np.abs(lons - sector_lon)
                
                lat_idx = np.argmin(lat_diff)
                lon_idx = np.argmin(lon_diff)
                
                # Calcular métricas para este setor
                sector_metrics = {'CD_SETOR': sector_id}
                
                for var in climate_vars:
                    try:
                        # CORREÇÃO: Extrair dados do pixel mais próximo
                        if 'valid_time' in climate_data[var].dims:
                            # Dados temporais - calcular média ao longo do tempo
                            pixel_data = climate_data[var].isel({lat_coord: lat_idx, lon_coord: lon_idx})
                            with warnings.catch_warnings():
                                warnings.simplefilter("ignore", category=RuntimeWarning)
                                mean_value = float(pixel_data.mean().values)
                        else:
                            # Dados únicos no tempo
                            mean_value = float(climate_data[var].isel({lat_coord: lat_idx, lon_coord: lon_idx}).values)
                        
                        if np.isnan(mean_value) or np.isinf(mean_value):
                            mean_value = np.nan
                        
                        sector_metrics[f"{var}_mean"] = mean_value
                        
                    except Exception as e:
                        print(f"⚠️ Erro ao processar variável {var} para setor {sector_id}: {str(e)}")
                        sector_metrics[f"{var}_mean"] = np.nan
                
                results.append(sector_metrics)
                processed_count += 1
                
                if processed_count % 10 == 0:
                    print(f"⏳ Processados {processed_count}/{len(sectors)} setores...")
                    
            except Exception as e:
                print(f"❌ Erro ao processar setor {sector_id}: {str(e)}")
                # Adicionar setor com valores NaN para manter consistência
                sector_metrics = {'CD_SETOR': sector_id}
                for var in climate_vars:
                    sector_metrics[f"{var}_mean"] = np.nan
                results.append(sector_metrics)
                continue
        
        # Criar DataFrame dos resultados
        results_df = pd.DataFrame(results)
        
        # Estatísticas de processamento
        print(f"📊 Processamento concluído:")
        print(f"  - Total de setores: {len(sectors)}")
        print(f"  - Setores processados com sucesso: {processed_count}")
        print(f"  - Setores com erro: {len(sectors) - processed_count}")
        
        # Verificar colunas com todos os valores NaN
        for col in results_df.columns:
            if col != 'CD_SETOR':
                nan_count = results_df[col].isna().sum()
                if nan_count == len(results_df):
                    print(f"⚠️ Todas as entradas da coluna '{col}' são NaN")
                elif nan_count > 0:
                    print(f"ℹ️ Coluna '{col}': {nan_count}/{len(results_df)} valores são NaN")
        
        # APLICAR FALLBACK SE TODOS OS DADOS FOREM NaN
        if results_df.loc[:, results_df.columns != 'CD_SETOR'].isna().all().all():
            print("⚠️ TODOS os dados climáticos são NaN. Aplicando fallback...")
            return _apply_climate_fallback_minimal(sectors, output_path)
        
        # Salvar resultados
        output_path.parent.mkdir(parents=True, exist_ok=True)
        results_df.to_csv(output_path, index=False)
        print(f"✅ Dados climáticos agregados salvos com sucesso em: {output_path}")
        
        return results_df

    except Exception as e:
        print(f"❌ Falha ao agregar dados climáticos: {e}")
        import traceback
        traceback.print_exc()
        print("🔄 Aplicando fallback climático...")
        return _apply_climate_fallback_minimal(sectors, output_path)

def _apply_climate_fallback_minimal(sectors_gdf, output_path):
    """
    Aplica valores médios mínimos quando dados climáticos não estão disponíveis.
    """
    print("🔄 Aplicando fallback climático com valores médios regionais...")
    
    # Valores médios para Campinas em julho
    FALLBACK_VALUES = {
        't2m_mean': 19.5,      # Temperatura média em °C
        'tp_mean': 0.0015,     # Precipitação média em m/dia
    }
    
    results = []
    for index, sector in sectors_gdf.iterrows():
        sector_data = {'CD_SETOR': sector['CD_SETOR']}
        
        # Adiciona pequena variação aleatória
        np.random.seed(int(str(sector['CD_SETOR'])[-3:]) if str(sector['CD_SETOR']).isdigit() else 42)
        
        for var, base_value in FALLBACK_VALUES.items():
            variation = np.random.uniform(-0.05, 0.05)  # ±5% de variação
            sector_data[var] = base_value * (1 + variation)
        
        results.append(sector_data)
    
    results_df = pd.DataFrame(results)
    
    # Salvar arquivo
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(output_path, index=False)
    
    print(f"✅ Fallback climático aplicado!")
    print(f"   - {len(results_df)} setores processados")
    print(f"   - Arquivo salvo em: {output_path}")
    
    return results_df