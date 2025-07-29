# NAIA 
Hackathon da Copernicus

## Pré-requisitos

- [Python 3.8+](https://www.python.org/downloads/)
- [pip](https://pip.pypa.io/en/stable/installation/)

## Instalação

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/seu-usuario/seu-repositorio.git
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
   - Renomeie o arquivo `.env.example` para `.env` e preencha com suas credenciais, ou crie um arquivo `.env` com as seguintes variáveis:
     ```
     CLIENT_ID=seu_client_id
     CLIENT_SECRET_ID=sua_client_secret
     GOOGLE=sua_google_api_key
     ```

## Uso

Ative o ambiente virtual sempre que for rodar o projeto:
```bash
source naia-env/bin/activate
```

Depois, execute seus scripts normalmente.

---

**Importante:**  
Não suba o arquivo `.env` nem a pasta do ambiente virtual (`naia-env/`) para o GitHub. Eles já estão listados no `.gitignore`.

## Requisitos

Para executar este notebook, você precisa:

1. **Credenciais do Copernicus CDSE**: Registre-se em [dataspace.copernicus.eu](https://dataspace.copernicus.eu)

2. **Arquivo .env** com suas credenciais:
   ```
   CLIENT_ID=seu_client_id_aqui
   CLIENT_SECRET_ID=seu_client_secret_aqui
   ```

3. **Bibliotecas Python**:
   ```bash
   pip install sentinelhub matplotlib rasterio python-dotenv requests
   ```

## Notas Importantes

- **Sentinel-1**: Satélite de radar que funciona independentemente das condições climáticas
- **Banda VV**: Polarização vertical para transmissão e recepção
- **Backscatter**: Valores em dB que indicam a intensidade do sinal refletido
- **CDSE**: Copernicus Data Space Ecosystem é o novo portal oficial para dados Copernicus