# debug.py
import os
from pathlib import Path

# --- Início da Ferramenta de Diagnóstico NAIÁ ---

print("="*60)
print("🕵️  INICIANDO SCRIPT DE DIAGNÓSTICO DO PROJETO NAIÁ 🕵️")
print("="*60)

project_root = Path.cwd()
print(f"Diretório Raiz do Projeto: {project_root}\n")

# --- 1. Verificando Estrutura de Pastas Essenciais ---
print("--- 1. Verificando Estrutura de Pastas ---")
required_dirs = ['src', 'config', 'output', 'templates', 'static', 'data/raw/sentinel', 'data/raw/climate']
all_ok = True
for dir_path in required_dirs:
    full_path = project_root / dir_path
    if full_path.exists() and full_path.is_dir():
        print(f"[OK]      Pasta '{dir_path}' encontrada.")
    else:
        print(f"[FALHA]   Pasta '{dir_path}' NÃO encontrada.")
        all_ok = False
if all_ok:
    print(">> Estrutura de pastas parece correta.\n")
else:
    print(">> ATENÇÃO: Verifique a estrutura de pastas do seu projeto.\n")


# --- 2. Verificando Arquivos de Configuração e Dados Críticos ---
print("--- 2. Verificando Arquivos Essenciais ---")
# Tenta carregar o run_analysis para ler os parâmetros
try:
    from run_analysis import NATIONAL_SHAPEFILE_PATH
    shapefile_path_str = str(NATIONAL_SHAPEFILE_PATH)
except (ImportError, AttributeError):
    shapefile_path_str = "D:/data/dados geologicos/Dados IBGE/BR_setores_CD2022.shp" # Valor padrão
    print("[AVISO] Não foi possível ler NATIONAL_SHAPEFILE_PATH do run_analysis.py. Usando valor padrão.")

required_files = {
    'config/settings.py': "Arquivo de configurações do projeto.",
    '.env': "Arquivo de chaves de API (essencial para as APIs).",
    shapefile_path_str: "Shapefile nacional do IBGE."
}
all_ok = True
for file_path_str, desc in required_files.items():
    full_path = Path(file_path_str)
    # Se o caminho não for absoluto, considera-o relativo à raiz do projeto
    if not full_path.is_absolute():
        full_path = project_root / file_path_str
        
    if full_path.exists() and full_path.is_file():
        print(f"[OK]      Arquivo '{file_path_str}' encontrado. ({desc})")
    else:
        print(f"[FALHA]   Arquivo '{file_path_str}' NÃO encontrado. ({desc})")
        all_ok = False
if all_ok:
    print(">> Arquivos essenciais parecem estar no lugar.\n")
else:
    print(">> ATENÇÃO: Verifique se os arquivos essenciais existem e os caminhos estão corretos.\n")


# --- 3. Verificando o Módulo 'paths.py' ---
print("--- 3. Verificando src/utils/paths.py ---")
try:
    from src.utils import paths
    print("[OK]      Módulo 'paths.py' importado com sucesso.")
    path_vars = [v for v in dir(paths) if not v.startswith('__') and isinstance(getattr(paths, v), Path)]
    if not path_vars:
        print("[FALHA]   Nenhuma variável de caminho (Path) foi encontrada em 'paths.py'.")
    else:
        print("  Variáveis de caminho encontradas:")
        for var in path_vars:
            print(f"    - paths.{var} = {getattr(paths, var)}")
        print(">> O módulo 'paths.py' parece estar configurado.\n")

except ImportError:
    print("[FALHA]   Não foi possível importar 'src.utils.paths'. Verifique se o arquivo existe e não contém erros.\n")
except Exception as e:
    print(f"[FALHA]   Ocorreu um erro ao inspecionar 'src.utils.paths': {e}\n")


# --- 4. Lembrete Manual ---
print("--- 4. Ação Manual Necessária ---")
print("Por favor, verifique o seu arquivo 'run_analysis.py' e confirme os valores das seguintes flags:")
print("  - SKIP_DOWNLOADS_AND_PROCESSING")
print("  - SKIP_POOL_DETECTION")
print("Lembre-se: Para a primeira execução numa nova área, 'SKIP_DOWNLOADS_AND_PROCESSING' deve ser 'False'.\n")


# --- Fim do Diagnóstico ---
print("="*60)
print("🕵️  DIAGNÓSTICO CONCLUÍDO 🕵️")
print("="*60)
print("Por favor, copie e cole a SAÍDA COMPLETA deste script na nossa conversa.")