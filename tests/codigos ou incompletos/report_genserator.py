# ================================
# GERADOR DE RELATÓRIO VISUAL PROFISSIONAL
# Integração com os dados do script completo.py
# ================================

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime

# Configurações de estilo baseadas na referência visual
STYLE_CONFIG = {
    'background_color': '#0e1a2b',
    'card_color': '#1e2a3a',
    'accent_color': '#FFA500',
    'text_primary': '#ffffff',
    'text_secondary': '#b8c5d1',
    'success_color': '#44ff44',
    'warning_color': '#FFA500',
    'danger_color': '#ff4444',
    'font_main': 'Arial',
    'font_title': 'Arial',
}

def create_professional_report(analysis_results, target_coords, bbox, area_size):
    """
    Criar relatório visual profissional usando os dados reais da análise
    """
    print("🎨 Gerando relatório profissional...")
    
    # Configurar figura principal com o estilo desejado
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(20, 24), facecolor=STYLE_CONFIG['background_color'])
    
    # Criar grid layout complexo
    gs = GridSpec(6, 4, figure=fig, hspace=0.4, wspace=0.3)
    
    # ================================
    # TÍTULO E CABEÇALHO
    # ================================
    ax_header = fig.add_subplot(gs[0, :])
    ax_header.set_facecolor(STYLE_CONFIG['card_color'])
    ax_header.axis('off')
    
    # Título principal
    ax_header.text(0.5, 0.8, '🦟 ANÁLISE GEOESPACIAL DE FOCOS DE DENGUE', 
                   ha='center', va='center', fontsize=28, fontweight='bold',
                   color=STYLE_CONFIG['accent_color'], transform=ax_header.transAxes)
    
    # Subtítulo
    ax_header.text(0.5, 0.5, 'Monitoramento por Satélite e Inteligência Geoespacial', 
                   ha='center', va='center', fontsize=16,
                   color=STYLE_CONFIG['text_secondary'], transform=ax_header.transAxes)
    
    # Localização
    lat, lon = target_coords
    ax_header.text(0.5, 0.2, f'📍 {lat:.6f}, {lon:.6f} (22°53\'17"S, 47°04\'07"W)', 
                   ha='center', va='center', fontsize=14, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.5", facecolor=STYLE_CONFIG['accent_color'], alpha=0.8),
                   color=STYLE_CONFIG['background_color'], transform=ax_header.transAxes)
    
    # ================================
    # SEÇÃO DE IMAGENS COMPARATIVAS
    # ================================
    
    # Google Earth
    ax_google = fig.add_subplot(gs[1, :2])
    ax_google.set_facecolor(STYLE_CONFIG['card_color'])
    
    # Tentar carregar imagem real do Google Earth
    try:
        if os.path.exists('google_earth_raw.png'):
            google_img = Image.open('google_earth_raw.png')
            ax_google.imshow(google_img)
            ax_google.set_title('🌍 GOOGLE EARTH - Alta Resolução', 
                               fontsize=16, fontweight='bold', color=STYLE_CONFIG['accent_color'], 
                               pad=20)
        else:
            # Imagem placeholder
            ax_google.text(0.5, 0.5, '🌍 Google Earth\nImagem não encontrada\ngoogle_earth_raw.png', 
                          ha='center', va='center', fontsize=14, 
                          color=STYLE_CONFIG['text_secondary'], transform=ax_google.transAxes)
            ax_google.set_title('🌍 GOOGLE EARTH', fontsize=16, fontweight='bold', 
                               color=STYLE_CONFIG['accent_color'])
    except Exception as e:
        ax_google.text(0.5, 0.5, f'Erro ao carregar\nGoogle Earth\n{str(e)[:50]}', 
                      ha='center', va='center', fontsize=12, 
                      color=STYLE_CONFIG['text_secondary'], transform=ax_google.transAxes)
    
    ax_google.axis('off')
    
    # Copernicus Sentinel
    ax_sentinel = fig.add_subplot(gs[1, 2:])
    ax_sentinel.set_facecolor(STYLE_CONFIG['card_color'])
    
    try:
        if os.path.exists('sentinel_processed.png'):
            sentinel_img = Image.open('sentinel_processed.png')
            ax_sentinel.imshow(sentinel_img)
            ax_sentinel.set_title('🛰️ COPERNICUS SENTINEL-2 Processada', 
                                 fontsize=16, fontweight='bold', color=STYLE_CONFIG['accent_color'], 
                                 pad=20)
        else:
            ax_sentinel.text(0.5, 0.5, '🛰️ Copernicus Sentinel-2\nImagem não encontrada\nsentinel_processed.png', 
                            ha='center', va='center', fontsize=14, 
                            color=STYLE_CONFIG['text_secondary'], transform=ax_sentinel.transAxes)
            ax_sentinel.set_title('🛰️ COPERNICUS SENTINEL-2', fontsize=16, fontweight='bold', 
                                 color=STYLE_CONFIG['accent_color'])
    except Exception as e:
        ax_sentinel.text(0.5, 0.5, f'Erro ao carregar\nSentinel-2\n{str(e)[:50]}', 
                        ha='center', va='center', fontsize=12, 
                        color=STYLE_CONFIG['text_secondary'], transform=ax_sentinel.transAxes)
    
    ax_sentinel.axis('off')
    
    # ================================
    # MÉTRICAS PRINCIPAIS
    # ================================
    
    metrics_data = [
        ('Área Total', f'{area_size*111:.1f}km²', '🗺️'),
        ('Áreas Aquáticas', f'{analysis_results.get("water_percentage", 0):.1f}%', '💧'),
        ('Água Estagnada', f'{analysis_results.get("stagnant_percentage", 0):.1f}%', '🟢'),
        ('Zoom Level', '16', '🔍')
    ]
    
    for i, (label, value, icon) in enumerate(metrics_data):
        ax_metric = fig.add_subplot(gs[2, i])
        ax_metric.set_facecolor(STYLE_CONFIG['card_color'])
        ax_metric.axis('off')
        
        # Valor principal
        ax_metric.text(0.5, 0.6, value, ha='center', va='center', 
                      fontsize=24, fontweight='bold', color=STYLE_CONFIG['accent_color'],
                      transform=ax_metric.transAxes)
        
        # Label
        ax_metric.text(0.5, 0.3, f'{icon} {label}', ha='center', va='center', 
                      fontsize=12, color=STYLE_CONFIG['text_secondary'],
                      transform=ax_metric.transAxes)
        
        # Borda decorativa
        rect = patches.Rectangle((0.05, 0.05), 0.9, 0.9, linewidth=2, 
                               edgecolor=STYLE_CONFIG['accent_color'], 
                               facecolor='none', transform=ax_metric.transAxes)
        ax_metric.add_patch(rect)
    
    # ================================
    # ALERTA DE RISCO
    # ================================
    
    ax_risk = fig.add_subplot(gs[3, :])
    ax_risk.axis('off')
    
    # Determinar cor do risco
    risk_level = analysis_results.get('risk_level', '🟡 MÉDIO')
    if 'ALTO' in risk_level:
        risk_color = STYLE_CONFIG['danger_color']
        risk_bg = '#ff4444'
    elif 'MÉDIO' in risk_level:
        risk_color = STYLE_CONFIG['warning_color']
        risk_bg = '#FFA500'
    else:
        risk_color = STYLE_CONFIG['success_color']
        risk_bg = '#44ff44'
    
    # Caixa de alerta principal
    risk_rect = patches.FancyBboxPatch((0.1, 0.2), 0.8, 0.6, 
                                      boxstyle="round,pad=0.02", 
                                      facecolor=risk_bg, alpha=0.9,
                                      edgecolor=risk_color, linewidth=3,
                                      transform=ax_risk.transAxes)
    ax_risk.add_patch(risk_rect)
    
    # Texto do alerta
    ax_risk.text(0.5, 0.65, f'⚠️ NÍVEL DE RISCO: {risk_level.split()[-1]}', 
                ha='center', va='center', fontsize=20, fontweight='bold',
                color='white', transform=ax_risk.transAxes)
    
    ax_risk.text(0.5, 0.35, 'Monitoramento e ações preventivas recomendadas', 
                ha='center', va='center', fontsize=14,
                color='white', transform=ax_risk.transAxes)
    
    # ================================
    # ANÁLISE COMBINADA
    # ================================
    
    ax_combined = fig.add_subplot(gs[4, :])
    ax_combined.set_facecolor(STYLE_CONFIG['card_color'])
    
    try:
        if os.path.exists('analise_combinada_dengue.png'):
            combined_img = Image.open('analise_combinada_dengue.png')
            ax_combined.imshow(combined_img)
            ax_combined.set_title('🔍 ANÁLISE DE DIFERENÇAS ESPECTRAIS', 
                                 fontsize=16, fontweight='bold', color=STYLE_CONFIG['accent_color'], 
                                 pad=20)
        else:
            ax_combined.text(0.5, 0.5, '🔍 Análise Combinada\nImagem não encontrada\nanalise_combinada_dengue.png', 
                            ha='center', va='center', fontsize=14, 
                            color=STYLE_CONFIG['text_secondary'], transform=ax_combined.transAxes)
            ax_combined.set_title('🔍 ANÁLISE COMBINADA', fontsize=16, fontweight='bold', 
                                 color=STYLE_CONFIG['accent_color'])
    except Exception as e:
        ax_combined.text(0.5, 0.5, f'Erro ao carregar\nAnálise Combinada\n{str(e)[:50]}', 
                        ha='center', va='center', fontsize=12, 
                        color=STYLE_CONFIG['text_secondary'], transform=ax_combined.transAxes)
    
    ax_combined.axis('off')
    
    # ================================
    # SEÇÃO DE RECOMENDAÇÕES E INFORMAÇÕES TÉCNICAS
    # ================================
    
    ax_info = fig.add_subplot(gs[5, :])
    ax_info.set_facecolor(STYLE_CONFIG['card_color'])
    ax_info.axis('off')
    
    # Informações técnicas (lado esquerdo)
    lat, lon = target_coords
    tech_info = f"""
📊 ESPECIFICAÇÕES TÉCNICAS:
• Coordenadas: {lat:.6f}, {lon:.6f}
• Área de Cobertura: {area_size*111:.1f}km × {area_size*111:.1f}km
• Período: 01/07/2025 - 27/07/2025
• Fontes: Google Earth + Copernicus Sentinel-2
• Zoom Level: 16
• Resolução: 800x600 pixels

📈 RESULTADOS DA ANÁLISE:
• Pixels de água: {analysis_results.get("water_pixels", 0):,}
• Pixels de água estagnada: {analysis_results.get("stagnant_pixels", 0):,}
• Percentual aquático: {analysis_results.get("water_percentage", 0):.2f}%
• Percentual estagnado: {analysis_results.get("stagnant_percentage", 0):.2f}%
    """
    
    ax_info.text(0.02, 0.98, tech_info, ha='left', va='top', fontsize=10,
                color=STYLE_CONFIG['text_secondary'], transform=ax_info.transAxes,
                bbox=dict(boxstyle="round,pad=0.5", facecolor=STYLE_CONFIG['background_color'], alpha=0.8))
    
    # Recomendações (lado direito)
    risk_level_clean = risk_level.split()[-1] if risk_level else 'MÉDIO'
    
    if 'ALTO' in risk_level_clean:
        recommendations = """
💡 RECOMENDAÇÕES - RISCO ALTO:
• Inspeção presencial URGENTE da área
• Eliminação imediata de recipientes com água parada
• Aplicação de larvicida em pontos críticos
• Monitoramento SEMANAL da região
• Educação intensiva da população local
• Ações de controle vetorial imediatas
• Notificação às autoridades sanitárias
• Acompanhamento médico da população
        """
    elif 'MÉDIO' in risk_level_clean:
        recommendations = """
💡 RECOMENDAÇÕES - RISCO MÉDIO:
• Inspeção da área em 7-10 dias
• Verificação de recipientes suspeitos
• Orientação aos moradores locais
• Monitoramento quinzenal da região
• Verificar piscinas, caixas d'água e reservatórios
• Eliminar pneus, vasos e recipientes descobertos
• Limpeza de calhas e sistemas de drenagem
• Monitorar terrenos baldios com acúmulo de água
        """
    else:
        recommendations = """
💡 RECOMENDAÇÕES - RISCO BAIXO:
• Inspeção mensal de rotina da área
• Manutenção preventiva de sistemas de água
• Educação continuada da população
• Monitoramento trimestral por satélite
• Verificação preventiva de criadouros comuns
• Manutenção de sistemas de drenagem
• Campanhas educativas sazonais
• Monitoramento meteorológico para prevenção
        """
    
    ax_info.text(0.52, 0.98, recommendations, ha='left', va='top', fontsize=10,
                color=STYLE_CONFIG['text_primary'], transform=ax_info.transAxes,
                bbox=dict(boxstyle="round,pad=0.5", facecolor=STYLE_CONFIG['accent_color'], alpha=0.1))
    
    # ================================
    # RODAPÉ
    # ================================
    
    footer_text = f"""
📅 Data da Análise: {datetime.now().strftime('%d de %B de %Y')} | 
🛰️ Fontes: Google Maps API, Copernicus Sentinel-2 | 
🔬 Metodologia: Análise Multiespectral e Processamento Digital de Imagens | 
📍 Localização: Indaiatuba, São Paulo, Brasil
    """
    
    fig.text(0.5, 0.02, footer_text, ha='center', va='bottom', fontsize=10,
            color=STYLE_CONFIG['text_secondary'],
            bbox=dict(boxstyle="round,pad=0.5", facecolor=STYLE_CONFIG['card_color'], alpha=0.8))
    
    # ================================
    # SALVAR RELATÓRIO
    # ================================
    
    plt.tight_layout()
    
    # Salvar como PNG de alta qualidade
    plt.savefig('relatorio_dengue_profissional.png', 
                dpi=300, bbox_inches='tight', facecolor=STYLE_CONFIG['background_color'])
    
    # Salvar como PDF
    plt.savefig('relatorio_dengue_profissional.pdf', 
                dpi=300, bbox_inches='tight', facecolor=STYLE_CONFIG['background_color'])
    
    plt.show()
    
    print("✅ Relatório profissional gerado com sucesso!")
    print("📁 Arquivos criados:")
    print("  • relatorio_dengue_profissional.png (alta qualidade)")
    print("  • relatorio_dengue_profissional.pdf (impressão)")
    
    return True

def create_compact_infographic(analysis_results, target_coords):
    """
    Criar infográfico compacto para redes sociais/apresentações rápidas
    """
    print("📱 Gerando infográfico compacto...")
    
    fig, ax = plt.subplots(figsize=(12, 16), facecolor=STYLE_CONFIG['background_color'])
    ax.set_facecolor(STYLE_CONFIG['background_color'])
    ax.axis('off')
    
    # Título
    ax.text(0.5, 0.95, '🦟 ALERTA DENGUE', ha='center', va='center', 
            fontsize=32, fontweight='bold', color=STYLE_CONFIG['accent_color'],
            transform=ax.transAxes)
    
    ax.text(0.5, 0.90, 'Análise por Satélite', ha='center', va='center', 
            fontsize=18, color=STYLE_CONFIG['text_secondary'],
            transform=ax.transAxes)
    
    # Coordenadas
    lat, lon = target_coords
    ax.text(0.5, 0.85, f'📍 {lat:.4f}, {lon:.4f}', ha='center', va='center', 
            fontsize=16, fontweight='bold', color=STYLE_CONFIG['text_primary'],
            bbox=dict(boxstyle="round,pad=0.5", facecolor=STYLE_CONFIG['accent_color'], alpha=0.8),
            transform=ax.transAxes)
    
    # Nível de risco (grande destaque)
    risk_level = analysis_results.get('risk_level', '🟡 MÉDIO')
    if 'ALTO' in risk_level:
        risk_color = STYLE_CONFIG['danger_color']
    elif 'MÉDIO' in risk_level:
        risk_color = STYLE_CONFIG['warning_color']
    else:
        risk_color = STYLE_CONFIG['success_color']
    
    # Círculo de risco
    circle = patches.Circle((0.5, 0.65), 0.15, facecolor=risk_color, alpha=0.8,
                           transform=ax.transAxes)
    ax.add_patch(circle)
    
    ax.text(0.5, 0.65, risk_level.split()[-1], ha='center', va='center', 
            fontsize=24, fontweight='bold', color='white',
            transform=ax.transAxes)
    
    ax.text(0.5, 0.47, 'NÍVEL DE RISCO', ha='center', va='center', 
            fontsize=14, fontweight='bold', color=STYLE_CONFIG['text_primary'],
            transform=ax.transAxes)
    
    # Métricas rápidas
    metrics_compact = [
        ('💧 Áreas Aquáticas', f'{analysis_results.get("water_percentage", 0):.1f}%'),
        ('🟢 Água Estagnada', f'{analysis_results.get("stagnant_percentage", 0):.1f}%'),
        ('🗺️ Área Total', '2.0km²'),
    ]
    
    y_pos = 0.35
    for label, value in metrics_compact:
        ax.text(0.2, y_pos, label, ha='left', va='center', 
                fontsize=12, color=STYLE_CONFIG['text_secondary'],
                transform=ax.transAxes)
        ax.text(0.8, y_pos, value, ha='right', va='center', 
                fontsize=14, fontweight='bold', color=STYLE_CONFIG['accent_color'],
                transform=ax.transAxes)
        y_pos -= 0.05
    
    # Call to action
    ax.text(0.5, 0.12, '⚠️ AÇÃO NECESSÁRIA', ha='center', va='center', 
            fontsize=16, fontweight='bold', color=STYLE_CONFIG['danger_color'],
            transform=ax.transAxes)
    
    ax.text(0.5, 0.07, 'Eliminação de criadouros\nMonitoramento contínuo', 
            ha='center', va='center', fontsize=12, color=STYLE_CONFIG['text_primary'],
            transform=ax.transAxes)
    
    # Rodapé
    ax.text(0.5, 0.02, f'🛰️ Análise: {datetime.now().strftime("%d/%m/%Y")} | Google Earth + Sentinel-2', 
            ha='center', va='center', fontsize=10, color=STYLE_CONFIG['text_secondary'],
            transform=ax.transAxes)
    
    plt.tight_layout()
    plt.savefig('infografico_dengue_compacto.png', 
                dpi=300, bbox_inches='tight', facecolor=STYLE_CONFIG['background_color'])
    plt.show()
    
    print("✅ Infográfico compacto gerado!")
    print("📁 Arquivo criado: infografico_dengue_compacto.png")
    
    return True

# ================================
# FUNÇÃO PRINCIPAL DE INTEGRAÇÃO
# ================================

def generate_complete_report_suite():
    """
    Função principal para gerar todos os relatórios
    Integra com os dados do script completo.py
    """
    print("🚀 INICIANDO GERAÇÃO COMPLETA DE RELATÓRIOS")
    print("="*60)
    
    # Simular dados do analysis_results (substitua pelos dados reais)
    # Em produção, estes dados virão da variável analysis_results do script principal
    analysis_results_sample = {
        'water_pixels': 7200,
        'stagnant_pixels': 3840,
        'water_percentage': 1.5,
        'stagnant_percentage': 0.8,
        'risk_level': '🟡 MÉDIO'
    }
    
    # Coordenadas do script principal
    target_coords_sample = (-22.888056, -47.068611)
    area_size_sample = 0.018
    bbox_sample = [-47.077611, -22.897056, -47.059611, -22.879056]
    
    try:
        # Gerar relatório profissional completo
        create_professional_report(
            analysis_results_sample, 
            target_coords_sample, 
            bbox_sample, 
            area_size_sample
        )
        
        # Gerar infográfico compacto
        create_compact_infographic(
            analysis_results_sample, 
            target_coords_sample
        )
        
        print("\n🎉 TODOS OS RELATÓRIOS GERADOS COM SUCESSO!")
        print("="*60)
        print("📁 Arquivos disponíveis:")
        print("  • relatorio_dengue_profissional.png (PNG alta qualidade)")
        print("  • relatorio_dengue_profissional.pdf (PDF para impressão)")
        print("  • infografico_dengue_compacto.png (Infográfico compacto)")
        print("\n💡 Para integrar com dados reais:")
        print("  • Substitua 'analysis_results_sample' pelos dados reais")
        print("  • Execute após rodar o script completo.py")
        print("  • Certifique-se de que as imagens estão disponíveis")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na geração dos relatórios: {e}")
        return False

# ================================
# EXECUÇÃO PARA TESTE
# ================================

if __name__ == "__main__":
    generate_complete_report_suite()
