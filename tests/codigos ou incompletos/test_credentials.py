import os
from dotenv import load_dotenv
from sentinelhub import SHConfig
import requests

def test_credentials():
    """Testa as credenciais do Copernicus Data Space Ecosystem"""
    
    print("🔍 TESTANDO CREDENCIAIS DO COPERNICUS DATA SPACE ECOSYSTEM")
    print("=" * 60)
    
    # Carregar variáveis do .env
    load_dotenv()
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET_ID")
    
    print("1. Verificando arquivo .env...")
    if not client_id:
        print("❌ CLIENT_ID não encontrado no arquivo .env")
        return False
    else:
        print(f"✓ CLIENT_ID encontrado: {client_id[:8]}...")
    
    if not client_secret:
        print("❌ CLIENT_SECRET_ID não encontrado no arquivo .env")
        return False
    else:
        print(f"✓ CLIENT_SECRET_ID encontrado: {client_secret[:8]}...")
    
    print("\n2. Configurando Sentinel Hub...")
    config = SHConfig()
    config.sh_client_id = client_id.strip()
    config.sh_client_secret = client_secret.strip()
    config.sh_token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    config.sh_base_url = "https://sh.dataspace.copernicus.eu"
    
    print("✓ Configuração criada")
    
    print("\n3. Testando autenticação...")
    try:
        # Tentar obter token de acesso
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': config.sh_client_id,
            'client_secret': config.sh_client_secret
        }
        
        response = requests.post(
            config.sh_token_url,
            data=token_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if response.status_code == 200:
            token_info = response.json()
            print("✓ Token de acesso obtido com sucesso!")
            print(f"  - Tipo: {token_info.get('token_type', 'N/A')}")
            print(f"  - Expira em: {token_info.get('expires_in', 'N/A')} segundos")
            return True
        else:
            print(f"❌ Falha na autenticação: {response.status_code}")
            print(f"   Resposta: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erro durante o teste de autenticação: {e}")
        return False

def create_env_template():
    """Cria um template do arquivo .env"""
    template = """# Copernicus Data Space Ecosystem Credentials
# Obtenha suas credenciais em: https://shapps.dataspace.copernicus.eu/dashboard/#/
CLIENT_ID=seu_client_id_aqui
CLIENT_SECRET_ID=seu_client_secret_aqui
"""
    
    with open('.env.template', 'w') as f:
        f.write(template)
    
    print("📝 Arquivo '.env.template' criado!")
    print("   Copie este arquivo para '.env' e preencha suas credenciais")

def main():
    if not os.path.exists('.env'):
        print("⚠️  Arquivo .env não encontrado!")
        create_env_template()
        print("\n📋 PASSOS PARA CONFIGURAR:")
        print("1. Acesse: https://shapps.dataspace.copernicus.eu/dashboard/#/")
        print("2. Faça login ou crie uma conta")
        print("3. Vá em 'User Settings' > 'OAuth Clients'")
        print("4. Clique em 'Create New OAuth Client'")
        print("5. Copie o Client ID e Client Secret")
        print("6. Crie um arquivo .env com essas credenciais")
        return
    
    success = test_credentials()
    
    if success:
        print("\n🎉 SUCESSO! Suas credenciais estão funcionando corretamente!")
        print("   Você pode executar o script principal agora.")
    else:
        print("\n❌ FALHA! Verifique suas credenciais.")
        print("\n🔧 SOLUÇÃO DE PROBLEMAS:")
        print("1. Confirme que você copiou corretamente:")
        print("   - CLIENT_ID (sem espaços)")
        print("   - CLIENT_SECRET_ID (sem espaços)")
        print("2. Verifique se sua conta está ativa")
        print("3. Confirme que o OAuth Client está habilitado")
        print("4. Tente recriar o OAuth Client se necessário")

if __name__ == "__main__":
    main()