# main.py
import logging
from config import settings
from src.utils import paths
from src.data import sentinel_downloader, climate_downloader
from src.features import image_processor, feature_builder
from src.models import train
from src.analysis import map_generator

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Pipeline de execução do projeto NAIÁ.
    """
    logging.info("Iniciando o pipeline do projeto NAIÁ...")

    # 1. Setup inicial: criar pastas
    paths.create_project_dirs()
    logging.info("Estrutura de diretórios verificada.")

    # 2. Aquisição de Dados
    logging.info("Iniciando download dos dados...")
    sentinel_downloader.download_s1_data(
        bbox=settings.STUDY_AREA_BBOX,
        time_interval=settings.TIME_INTERVAL,
        output_dir=paths.RAW_SENTINEL_DIR
    )
    climate_downloader.download_era5_data(
        area=settings.STUDY_AREA_BBOX,
        time_interval=settings.TIME_INTERVAL,
        output_dir=paths.RAW_CLIMATE_DIR
    )
    logging.info("Download de dados brutos concluído.")

    # 3. Processamento de Imagens e Extração de Features
    logging.info("Processando imagens e construindo features...")
    image_processor.clip_images_by_sector(
        raw_image_dir=paths.RAW_SENTINEL_DIR,
        geodata_path=settings.GEODATA_PATH,
        output_dir=paths.PROCESSED_IMAGES_DIR
    )
    feature_builder.create_feature_table(
        processed_images_dir=paths.PROCESSED_IMAGES_DIR,
        climate_dir=paths.RAW_CLIMATE_DIR,
        geodata_path=settings.GEODATA_PATH,
        output_path=paths.PROCESSED_DIR / "features.csv"
    )
    logging.info("Tabela de features criada com sucesso.")

    # 4. Treinamento do Modelo
    logging.info("Iniciando treinamento do modelo...")
    train.run_training(
        feature_path=paths.PROCESSED_DIR / "features.csv",
        model_output_dir=settings.MODELS_DIR
    )
    logging.info("Modelo treinado e salvo.")

    # 5. Geração de Análise e Mapas
    logging.info("Gerando mapas de risco...")
    map_generator.create_risk_map(
        predictions_path=settings.MODELS_DIR / "predictions.csv",
        output_dir=paths.OUTPUT_MAPS_DIR
    )
    logging.info("Pipeline concluído com sucesso!")


if __name__ == "__main__":
    main()