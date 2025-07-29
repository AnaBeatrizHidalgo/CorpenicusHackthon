# auth.py
import os
from dotenv import load_dotenv
from sentinelhub import SHConfig
import requests

def get_copernicus_config():
    """Configura e autentica no Copernicus Data Space Ecosystem."""
    load_dotenv()
    config = SHConfig()
    
    # Credenciais do seu .env
    config.sh_client_id = os.getenv("CLIENT_ID").strip()
    config.sh_client_secret = os.getenv("CLIENT_SECRET_ID").strip()
    
    # URLs específicas do CDSE (já definidas no seu código)
    config.sh_token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    config.sh_base_url = "https://sh.dataspace.copernicus.eu"
    
    # Testa a conexão (opcional, mas recomendado)
    try:
        response = requests.post(
            config.sh_token_url,
            data={
                'grant_type': 'client_credentials',
                'client_id': config.sh_client_id,
                'client_secret': config.sh_client_secret
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        response.raise_for_status()
        print("✓ Autenticação no Copernicus CDSE bem-sucedida!")
        return config
    
    except Exception as e:
        raise Exception(f"❌ Falha na autenticação: {e}")