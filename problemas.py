#!/usr/bin/env python3
"""
Script de Debug para diagnóstico completo do projeto NAIA
Versão: 1.0
"""
import pandas as pd
import numpy as np
import geopandas as gpd
import xarray as xr
from pathlib import Path
import json
import traceback
from datetime import datetime
import rasterio
import warnings
warnings.filterwarnings('ignore')

class NAIADebugger:
    def __init__(self, output_dir="output"):
        self.output_dir = Path(output_dir)
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "issues": [],
            "data_quality": {},
            "file_checks": {},
            "recommendations": []
        }
    
    def log_issue(self, category, description, severity="WARNING"):
        """Registra um problema encontrado"""
        self.report["issues"].append({
            "category": category,
            "description": description,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        })
        print(f"[{severity}] {category}: {description}")
    
    def check_file_structure(self):
        """Verifica a estrutura de arquivos"""
        print("\n=== VERIFICAÇÃO DA ESTRUTURA DE ARQUIVOS ===")
        
        # Procura por jobs de análise
        job_dirs = list(self.output_dir.glob("analysis_*"))
        if not job_dirs:
            self.log_issue("FILE_STRUCTURE", "Nenhum diretório de análise encontrado", "ERROR")
            return
        
        latest_job = max(job_dirs, key=lambda x: x.stat().st_mtime)
        print(f"📁 Analisando job mais recente: {latest_job.name}")
        
        # Arquivos esperados
        expected_files = [
            "area_of_interest.geojson",
            "climate_features.csv", 
            "image_features.csv",
            "final_features.csv",
            "summary.json",
            "mapa_de_risco_e_priorizacao.html"
        ]
        
        for file in expected_files:
            file_path = latest_job / file
            exists = file_path.exists()
            self.report["file_checks"][file] = {
                "exists": exists,
                "size": file_path.stat().st_size if exists else 0,
                "path": str(file_path)
            }
            
            if not exists:
                self.log_issue("MISSING_FILE", f"Arquivo obrigatório não encontrado: {file}", "ERROR")
            else:
                print(f"✅ {file} - {file_path.stat().st_size} bytes")
        
        return latest_job
    
    def analyze_climate_data(self, job_dir):
        """Analisa problemas nos dados climáticos"""
        print("\n=== ANÁLISE DOS DADOS CLIMÁTICOS ===")
        
        climate_file = job_dir / "climate_features.csv"
        if not climate_file.exists():
            self.log_issue("CLIMATE_DATA", "Arquivo de dados climáticos não encontrado", "ERROR")
            return
        
        try:
            df = pd.read_csv(climate_file)
            print(f"📊 Dados climáticos carregados: {df.shape}")
            print(f"📊 Colunas: {list(df.columns)}")
            
            # Verifica temperatura
            temp_cols = [col for col in df.columns if 't2m' in col.lower() or 'temp' in col.lower()]
            for col in temp_cols:
                temp_stats = df[col].describe()
                print(f"\n🌡️ Estatísticas de {col}:")
                print(temp_stats)
                
                # Verifica se temperatura está em Kelvin
                if df[col].min() > 200 and df[col].max() > 200:
                    self.log_issue("CLIMATE_DATA", f"Temperatura em {col} parece estar em Kelvin (min: {df[col].min():.1f}K)", "WARNING")
                    self.report["data_quality"]["temperature_unit"] = "Kelvin"
                    
                # Verifica valores negativos suspeitos
                if df[col].min() < -100:
                    self.log_issue("CLIMATE_DATA", f"Temperatura suspeita em {col}: {df[col].min():.1f}", "ERROR")
                
                # Verifica se há muitos NaN
                nan_pct = df[col].isna().sum() / len(df) * 100
                if nan_pct > 50:
                    self.log_issue("CLIMATE_DATA", f"Muitos valores NaN em {col}: {nan_pct:.1f}%", "WARNING")
            
            # Verifica precipitação
            precip_cols = [col for col in df.columns if 'tp' in col.lower() or 'precip' in col.lower()]
            for col in precip_cols:
                precip_stats = df[col].describe()
                print(f"\n🌧️ Estatísticas de {col}:")
                print(precip_stats)
                
                # Verifica se precipitação está em m/s (ERA5 padrão)
                if df[col].max() < 0.01:  # Valores muito pequenos
                    self.log_issue("CLIMATE_DATA", f"Precipitação em {col} parece estar em m/s - necessária conversão para mm", "WARNING")
                    self.report["data_quality"]["precipitation_unit"] = "m/s"
                
                nan_pct = df[col].isna().sum() / len(df) * 100
                if nan_pct > 50:
                    self.log_issue("CLIMATE_DATA", f"Muitos valores NaN em {col}: {nan_pct:.1f}%", "WARNING")
            
            self.report["data_quality"]["climate_summary"] = {
                "total_sectors": len(df),
                "columns": list(df.columns),
                "temperature_cols": temp_cols,
                "precipitation_cols": precip_cols
            }
            
        except Exception as e:
            self.log_issue("CLIMATE_DATA", f"Erro ao analisar dados climáticos: {str(e)}", "ERROR")
    
    def analyze_risk_calculation(self, job_dir):
        """Analisa o cálculo de risco"""
        print("\n=== ANÁLISE DO CÁLCULO DE RISCO ===")
        
        final_features_file = job_dir / "final_features.csv"
        if not final_features_file.exists():
            self.log_issue("RISK_CALC", "Arquivo final_features.csv não encontrado", "ERROR")
            return
        
        try:
            df = pd.read_csv(final_features_file)
            print(f"📊 Features finais carregadas: {df.shape}")
            
            # Verifica se há coluna de risk_score
            if 'risk_score' in df.columns:
                risk_stats = df['risk_score'].describe()
                print(f"\n⚠️ Estatísticas do Risk Score:")
                print(risk_stats)
                
                # Verifica distribuição do risco
                if df['risk_score'].nunique() <= 1:
                    self.log_issue("RISK_CALC", "Todos os valores de risk_score são iguais - falta variabilidade", "ERROR")
                
                # Verifica se há muitos valores extremos
                high_risk_pct = (df['risk_score'] > 0.8).sum() / len(df) * 100
                if high_risk_pct > 80:
                    self.log_issue("RISK_CALC", f"Muitos setores com risco alto: {high_risk_pct:.1f}% - critérios podem estar incorretos", "WARNING")
                
                self.report["data_quality"]["risk_distribution"] = {
                    "mean": float(df['risk_score'].mean()),
                    "std": float(df['risk_score'].std()),
                    "min": float(df['risk_score'].min()),
                    "max": float(df['risk_score'].max()),
                    "high_risk_percentage": float(high_risk_pct)
                }
            
            # Verifica features individuais
            feature_cols = ['ndvi_mean', 't2m_mean', 'tp_mean', 'vv_mean', 'vh_mean']
            for col in feature_cols:
                if col in df.columns:
                    nan_pct = df[col].isna().sum() / len(df) * 100
                    if nan_pct > 20:
                        self.log_issue("FEATURES", f"Muitos NaN em {col}: {nan_pct:.1f}%", "WARNING")
                    
                    # Verifica se há variabilidade
                    if df[col].nunique() <= 1:
                        self.log_issue("FEATURES", f"Feature {col} sem variabilidade", "WARNING")
                
        except Exception as e:
            self.log_issue("RISK_CALC", f"Erro ao analisar cálculo de risco: {str(e)}", "ERROR")
    
    def check_raw_climate_files(self, job_dir):
        """Verifica arquivos climáticos brutos"""
        print("\n=== VERIFICAÇÃO DE ARQUIVOS CLIMÁTICOS BRUTOS ===")
        
        # Procura arquivos NetCDF
        nc_files = list(Path("data/raw/climate").glob("*.nc"))
        nc_files.extend(list(job_dir.glob("*era5*.nc")))
        
        if not nc_files:
            self.log_issue("RAW_CLIMATE", "Nenhum arquivo NetCDF encontrado", "WARNING")
            return
        
        for nc_file in nc_files:
            try:
                print(f"🔍 Analisando: {nc_file.name}")
                ds = xr.open_dataset(nc_file)
                
                print(f"   Dimensões: {dict(ds.dims)}")
                print(f"   Variáveis: {list(ds.data_vars)}")
                print(f"   Coordenadas: {list(ds.coords)}")
                
                # Verifica extensão espacial
                if 'latitude' in ds.coords:
                    lat_range = ds.latitude.max().values - ds.latitude.min().values
                    lon_range = ds.longitude.max().values - ds.longitude.min().values
                    print(f"   Extensão: {lat_range:.4f}° lat x {lon_range:.4f}° lon")
                    
                    if lat_range < 0.01 or lon_range < 0.01:
                        self.log_issue("RAW_CLIMATE", f"Área muito pequena no arquivo {nc_file.name}: {lat_range:.4f}°x{lon_range:.4f}°", "WARNING")
                
                # Verifica dados de temperatura
                if 't2m' in ds.data_vars:
                    temp_data = ds.t2m
                    temp_min = float(temp_data.min().values)
                    temp_max = float(temp_data.max().values)
                    print(f"   Temperatura: {temp_min:.1f} a {temp_max:.1f}")
                    
                    if temp_min > 200:  # Provavelmente Kelvin
                        self.report["data_quality"]["raw_temperature_unit"] = "Kelvin"
                
                ds.close()
                
            except Exception as e:
                self.log_issue("RAW_CLIMATE", f"Erro ao ler {nc_file.name}: {str(e)}", "ERROR")
    
    def generate_recommendations(self):
        """Gera recomendações baseadas nos problemas encontrados"""
        print("\n=== RECOMENDAÇÕES ===")
        
        # Recomendações baseadas nos problemas encontrados
        if any("Kelvin" in issue["description"] for issue in self.report["issues"]):
            self.report["recommendations"].append({
                "priority": "HIGH",
                "category": "CLIMATE_DATA",
                "action": "Converter temperatura de Kelvin para Celsius",
                "code_location": "climate_feature_builder.py - função aggregate_climate_by_sector",
                "description": "Adicionar conversão: temp_celsius = temp_kelvin - 273.15"
            })
        
        if any("m/s" in issue["description"] for issue in self.report["issues"]):
            self.report["recommendations"].append({
                "priority": "HIGH", 
                "category": "CLIMATE_DATA",
                "action": "Converter precipitação de m/s para mm/dia",
                "code_location": "climate_feature_builder.py - função aggregate_climate_by_sector",
                "description": "Multiplicar por 1000 (m para mm) e por período (segundos para dia)"
            })
        
        if any("sem variabilidade" in issue["description"] for issue in self.report["issues"]):
            self.report["recommendations"].append({
                "priority": "MEDIUM",
                "category": "RISK_CALC",
                "action": "Revisar critérios de cálculo de risco",
                "code_location": "risk_assessor.py - função calculate_risk_score",
                "description": "Implementar critérios baseados em literatura científica"
            })
        
        if any("Muitos setores com risco alto" in issue["description"] for issue in self.report["issues"]):
            self.report["recommendations"].append({
                "priority": "HIGH",
                "category": "RISK_METHODOLOGY",
                "action": "Calibrar thresholds de risco",
                "code_location": "risk_assessor.py",
                "description": "Revisar os pesos e limiares para classificação de risco"
            })
        
        # Exibe recomendações
        for i, rec in enumerate(self.report["recommendations"], 1):
            print(f"{i}. [{rec['priority']}] {rec['action']}")
            print(f"   📍 {rec['code_location']}")
            print(f"   💡 {rec['description']}\n")
    
    def save_report(self):
        """Salva o relatório completo"""
        report_file = self.output_dir / "debug_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📋 Relatório salvo em: {report_file}")
        
        # Cria resumo em texto
        summary_file = self.output_dir / "debug_summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("=== NAIA DEBUG REPORT ===\n\n")
            f.write(f"Timestamp: {self.report['timestamp']}\n")
            f.write(f"Total de problemas encontrados: {len(self.report['issues'])}\n\n")
            
            f.write("PROBLEMAS:\n")
            for issue in self.report["issues"]:
                f.write(f"[{issue['severity']}] {issue['category']}: {issue['description']}\n")
            
            f.write("\nRECOMENDAÇÕES:\n")
            for i, rec in enumerate(self.report["recommendations"], 1):
                f.write(f"{i}. [{rec['priority']}] {rec['action']}\n")
                f.write(f"   {rec['code_location']}\n")
                f.write(f"   {rec['description']}\n\n")
        
        print(f"📋 Resumo salvo em: {summary_file}")
    
    def run_full_diagnosis(self):
        """Executa diagnóstico completo"""
        print("🔍 INICIANDO DIAGNÓSTICO COMPLETO DO PROJETO NAIA")
        print("=" * 50)
        
        try:
            # 1. Verificar estrutura
            latest_job = self.check_file_structure()
            if not latest_job:
                return
            
            # 2. Analisar dados climáticos
            self.analyze_climate_data(latest_job)
            
            # 3. Analisar cálculo de risco
            self.analyze_risk_calculation(latest_job)
            
            # 4. Verificar arquivos brutos
            self.check_raw_climate_files(latest_job)
            
            # 5. Gerar recomendações
            self.generate_recommendations()
            
            # 6. Salvar relatório
            self.save_report()
            
            print("\n✅ DIAGNÓSTICO CONCLUÍDO!")
            print(f"📊 Problemas encontrados: {len(self.report['issues'])}")
            print(f"💡 Recomendações geradas: {len(self.report['recommendations'])}")
            
        except Exception as e:
            print(f"\n❌ ERRO NO DIAGNÓSTICO: {str(e)}")
            print(traceback.format_exc())

if __name__ == "__main__":
    debugger = NAIADebugger()
    debugger.run_full_diagnosis()