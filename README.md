# NAIÁ
**Hackathon CopernicusLAC Panamá 2025**

O projeto **NAIÁ** utiliza dados dos satélites Sentinel-1 (radar) e Sentinel-2 (óptico) para análise geoespacial de setores censitários urbanos em Barão Geraldo, Campinas (SP). Desenvolvido no contexto do Hackathon CopernicusLAC Panamá 2025, o projeto processa imagens para extrair métricas ambientais e urbanas, fornecendo insights sobre a cobertura vegetal e características de superfície em áreas urbanas. O objetivo é apoiar análises de planejamento urbano e monitoramento ambiental usando dados do Copernicus Data Space Ecosystem (CDSE).

## O que o projeto faz

O NAIÁ processa imagens Sentinel-1 (polarizações VV/VH) e Sentinel-2 (bandas RGB+NIR) para a área de Barão Geraldo, definida pela bounding box `[-47.10, -22.85, -47.03, -22.78]`. As funcionalidades implementadas incluem:

- **Ingestão de dados**: Baixa e processa imagens Sentinel-1 e Sentinel-2 do CDSE, gerando arquivos TIFF com dados de backscatter (VV/VH) e bandas óticas (RGB+NIR), salvos em `data/sentinel1_unicamp.tiff` e `data/sentinel2_unicamp.tiff`.
- **Pré-processamento**: Recorta as imagens por setores censitários urbanos (filtrados por `SITUACAO = 'Urbana'` e `AREA_KM2 <= 1.0`) do arquivo `data/area_prova_barao.geojson`, produzindo ~88 TIFFs por sensor em `data/processed/s1_setor_<CD_SETOR>.tiff` e `data/processed/s2_setor_<CD_SETOR>.tiff`. Setores fora da área das imagens são pulados automaticamente.
- **Análise**: Calcula métricas por setor censitário:
  - **Sentinel-1**: Backscatter médio em dB para polarizações VV e VH, refletindo características de superfície (ex.: construções, vegetação).
  - **Sentinel-2**: NDVI médio (usando bandas NIR e Red), indicando a presença de vegetação.
- **Resultados**: Gera um arquivo `data/processed/metrics.csv` com colunas `CD_SETOR`, `VV_mean_dB`, `VH_mean_dB`, e `NDVI_mean`. Produz histogramas de validação (`ndvi_histogram.png`, `vv_histogram.png`, `vh_histogram.png`) para visualizar a distribuição das métricas.
- **Validação**: Gera imagens de validação (`s1_bbox_validation.png`, `s2_bbox_validation.png`, `s1_sectors_validation.png`, `s2_sectors_validation.png`) para confirmar a cobertura da área de interesse e o alinhamento dos setores censitários.

**Por que faz isso?**  
O projeto combina dados de radar (Sentinel-1) e óticos (Sentinel-2) para fornecer uma análise integrada de áreas urbanas. O backscatter (VV/VH) do Sentinel-1 permite mapear estruturas e superfícies independentemente das condições climáticas, enquanto o NDVI do Sentinel-2 quantifica a vegetação, essencial para avaliar áreas verdes em ambientes urbanos. Essas métricas apoiam o planejamento urbano sustentável, identificando áreas com baixa cobertura vegetal ou alta densidade de construções, contribuindo para decisões informadas em Barão Geraldo.

## Pré-requisitos

- [Python 3.12.7](https://www.python.org/downloads/)
- [pip](https://pip.pypa.io/en/stable/installation/)
- [Git](https://git-scm.com/downloads)

## Instalação

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/seu-usuario/CorpenicusHackthon.git
   cd CorpenicusHackthon
   ```

2. **Crie um ambiente virtual:**
   ```bash
   python3 -m venv naia-env
   source naia-env/bin/activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure as variáveis de ambiente:**
   - Renomeie o arquivo `.env.example` para `.env` e preencha com suas credenciais do Copernicus Data Space Ecosystem, ou crie um arquivo `.env` com:
     ```
     CLIENT_ID=seu_client_id
     CLIENT_SECRET_ID=sua_client_secret
     ```

## Uso

Ative o ambiente virtual sempre que for rodar o projeto:
```bash
source naia-env/bin/activate
```

Execute os notebooks na seguinte ordem:
1. `ingest_sentinel.ipynb`: Baixa e processa imagens Sentinel-1 e Sentinel-2.
2. `preprocess.ipynb`: Recorta imagens por setores censitários urbanos.
3. `analyze.ipynb`: Calcula métricas (NDVI, backscatter) e gera visualizações.

Comandos para executar:
```bash
jupyter notebook ingest_sentinel.ipynb
jupyter notebook preprocess.ipynb
jupyter notebook analyze.ipynb
```

## Requisitos

Para executar este projeto, você precisa:

1. **Credenciais do Copernicus CDSE**: Registre-se em [dataspace.copernicus.eu](https://dataspace.copernicus.eu) para obter `CLIENT_ID` e `CLIENT_SECRET_ID`.
2. **Arquivo .env** com:
   ```
   CLIENT_ID=seu_client_id_aqui
   CLIENT_SECRET_ID=seu_client_secret_aqui
   ```
3. **Arquivo requirements.txt**: Contém todas as bibliotecas necessárias (ex.: `geopandas`, `rasterio`, `matplotlib`, `pandas`, `numpy`, `sentinelhub`, `python-dotenv`, `requests`).

## Notas Importantes

- **Sentinel-1**: Satélite de radar que fornece dados de backscatter (VV/VH) em dB, ideal para análise de superfícies urbanas sob qualquer condição climática.
- **Sentinel-2**: Satélite óptico com bandas RGB e NIR, usado para calcular o NDVI, um indicador de vegetação.
- **CDSE**: Copernicus Data Space Ecosystem, portal oficial para acesso aos dados Sentinel.
- **Arquivos de saída**: Localizados em `data/processed/`, incluindo TIFFs recortados, `metrics.csv`, e histogramas.
- **Ambiente**: Use `naia-env` (Python 3.12.7) para consistência.

**Importante:**  
Não suba o arquivo `.env` nem a pasta `naia-env/` para o GitHub. Eles estão listados no `.gitignore`.