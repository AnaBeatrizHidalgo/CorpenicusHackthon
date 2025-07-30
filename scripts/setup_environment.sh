#!/bin/bash
echo "🔧 Configurando ambiente NAIÁ..."

# Criar estrutura de pastas
mkdir -p data/{raw/{satellite,geospatial,climate},processed/{metrics,images,maps},external/{ibge,copernicus}}
mkdir -p output/{reports,maps,data_exports}
mkdir -p tests logs

# Instalar dependências
pip install -r requirements.txt

# Copiar arquivo de configuração
cp .env.example .env

echo "✅ Ambiente configurado!"