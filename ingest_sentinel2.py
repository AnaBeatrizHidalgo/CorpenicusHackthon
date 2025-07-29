# ingest_sentinel2.py
from auth import get_copernicus_config
from sentinelhub import SentinelHubRequest, BBox, CRS, MimeType, DataCollection

# Configuração autenticada
config = get_copernicus_config()
config.sh_base_url = "https://sh.dataspace.copernicus.eu"

# Define a área da Unicamp (bbox NW/SE)
unicamp_bbox = BBox(bbox=[-47.0725, -22.8270, -47.0550, -22.8145], crs=CRS.WGS84)

# Use a coleção correta para CDSE
data_collection = DataCollection.SENTINEL2_L2A
request = SentinelHubRequest(
    evalscript="""
        //VERSION=3
        function setup() {
            return {
                input: ["B02", "B03", "B04", "B08"],
                output: { bands: 4 }
            };
        }
        function evaluatePixel(sample) {
            return [sample.B04, sample.B03, sample.B02, sample.B08];
        }
    """,
    input_data=[
        SentinelHubRequest.input_data(
            data_collection=data_collection,
            time_interval=("2025-06-29", "2025-07-29"),
            mosaicking_order="leastCC"
        )
    ],
    responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
    bbox=unicamp_bbox,
    size=[512, 512],
    config=config
)

# Download e salvamento
image = request.get_data()[0]  # Executa a requisição
print("Imagem baixada com sucesso!")