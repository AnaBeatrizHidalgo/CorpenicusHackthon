from src.data_acquisition import sentinel_downloader
from src.preprocessing import image_processor, climate_processor
from src.analysis import metrics_calculator, pool_detector
from src.visualization import map_generator
from src.config.settings import STUDY_AREA

def run_naia_pipeline():
    """Pipeline principal do NAIÁ"""
    print("🚀 NAIÁ - Iniciando pipeline completo")
    
    # 1. Coleta de dados
    sentinel_downloader.download_images(STUDY_AREA)
    
    # 2. Pré-processamento
    image_processor.process_all_images()
    climate_processor.integrate_climate_data()
    
    # 3. Análise
    metrics = metrics_calculator.calculate_all_metrics()
    pools = pool_detector.detect_pools()
    
    # 4. Visualização
    map_generator.create_risk_map(pools)
    
    print("✅ Pipeline concluído!")

if __name__ == "__main__":
    run_naia_pipeline()