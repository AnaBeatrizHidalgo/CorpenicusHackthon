import numpy as np
import matplotlib.pyplot as plt
from scipy import ndimage
import os

# Carregar os dados salvos
if os.path.exists('sentinel1_unicamp_raw.npy'):
    print("📁 Carregando dados salvos...")
    img_data = np.load('sentinel1_unicamp_raw.npy')
    
    print(f"Shape: {img_data.shape}")
    print(f"Range: {img_data.min():.2f} a {img_data.max():.2f} dB")
    
    # Se for 3D, usar primeira banda
    if len(img_data.shape) == 3:
        img_data = img_data[:,:,0]
    
    # Criar visualizações aprimoradas
    fig, axes = plt.subplots(2, 3, figsize=(20, 14))
    
    # 1. Melhor stretch para radar SAR
    img_clean = img_data.copy()
    img_clean[img_clean == 0] = np.nan  # Remover zeros
    valid_data = img_clean[~np.isnan(img_clean)]
    
    if len(valid_data) > 0:
        # Percentis mais conservadores para SAR
        p5, p95 = np.percentile(valid_data, [5, 95])
        img_stretch = np.clip((img_data - p5) / (p95 - p5), 0, 1)
        
        im1 = axes[0,0].imshow(img_stretch, cmap='gray')
        axes[0,0].set_title(f'Stretch Otimizado SAR\n(5%-95%: {p5:.1f} a {p95:.1f} dB)')
        axes[0,0].axis('off')
        plt.colorbar(im1, ax=axes[0,0], fraction=0.046)
    
    # 2. Aplicar filtro para reduzir speckle (ruído do radar)
    img_filtered = ndimage.median_filter(img_data, size=3)
    p5, p95 = np.percentile(img_filtered[img_filtered != 0], [5, 95])
    img_filtered_stretch = np.clip((img_filtered - p5) / (p95 - p5), 0, 1)
    
    im2 = axes[0,1].imshow(img_filtered_stretch, cmap='gray')
    axes[0,1].set_title('Filtro Anti-Speckle\n(Mediana 3x3)')
    axes[0,1].axis('off')
    plt.colorbar(im2, ax=axes[0,1], fraction=0.046)
    
    # 3. Destaque de estruturas urbanas
    img_urban = img_data.copy()
    # Threshold para destacar estruturas com alta reflexão
    threshold = np.percentile(img_urban[img_urban != 0], 85)
    img_urban_binary = img_urban > threshold
    
    im3 = axes[0,2].imshow(img_urban_binary, cmap='Reds')
    axes[0,2].set_title(f'Estruturas Urbanas\n(Threshold: {threshold:.1f} dB)')
    axes[0,2].axis('off')
    plt.colorbar(im3, ax=axes[0,2], fraction=0.046)
    
    # 4. Colormap alternativo para melhor contraste
    im4 = axes[1,0].imshow(img_stretch, cmap='viridis')
    axes[1,0].set_title('Colormap Viridis\n(Melhor para análise)')
    axes[1,0].axis('off')
    plt.colorbar(im4, ax=axes[1,0], fraction=0.046)
    
    # 5. Equalização de histograma
    from scipy.stats import rankdata
    img_eq = img_data[img_data != 0]
    if len(img_eq) > 0:
        img_equalized = img_data.copy()
        mask = img_data != 0
        img_equalized[mask] = rankdata(img_data[mask]) / np.sum(mask)
        
        im5 = axes[1,1].imshow(img_equalized, cmap='plasma')
        axes[1,1].set_title('Equalização de Histograma\n(Máximo contraste)')
        axes[1,1].axis('off')
        plt.colorbar(im5, ax=axes[1,1], fraction=0.046)
    
    # 6. Análise de gradientes (bordas)
    sobel_x = ndimage.sobel(img_filtered, axis=1)
    sobel_y = ndimage.sobel(img_filtered, axis=0)
    img_edges = np.sqrt(sobel_x**2 + sobel_y**2)
    
    im6 = axes[1,2].imshow(img_edges, cmap='hot')
    axes[1,2].set_title('Detecção de Bordas\n(Filtro Sobel)')
    axes[1,2].axis('off')
    plt.colorbar(im6, ax=axes[1,2], fraction=0.046)
    
    plt.tight_layout()
    plt.suptitle('🛰️ Sentinel-1 SAR - UNICAMP - Julho 2024\nAnálises Avançadas de Radar', 
                 fontsize=18, y=0.98)
    
    # Salvar
    plt.savefig('s1_unicamp_analises_avancadas.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Estatísticas detalhadas
    print("\n📊 ESTATÍSTICAS DOS DADOS:")
    print(f"• Total de pixels: {img_data.size:,}")
    print(f"• Pixels válidos: {np.sum(img_data != 0):,}")
    print(f"• Média (dB): {np.mean(img_data[img_data != 0]):.2f}")
    print(f"• Desvio padrão: {np.std(img_data[img_data != 0]):.2f}")
    print(f"• Percentil 10%: {np.percentile(img_data[img_data != 0], 10):.2f} dB")
    print(f"• Percentil 90%: {np.percentile(img_data[img_data != 0], 90):.2f} dB")
    
    # Análise das estruturas urbanas
    urban_pixels = np.sum(img_urban_binary)
    urban_percentage = (urban_pixels / np.sum(img_data != 0)) * 100
    print(f"• Estruturas urbanas: {urban_pixels:,} pixels ({urban_percentage:.1f}%)")
    
    print("\n🏗️ INTERPRETAÇÃO PARA UNICAMP:")
    print("• Pontos brilhantes: Edifícios, laboratórios, estruturas metálicas")
    print("• Linhas geométricas: Estradas, caminhos do campus")
    print("• Áreas escuras: Vegetação, áreas verdes, lagos")
    print("• Textura granulada: Mistura de construções e vegetação")
    print("• Bordas detectadas: Contornos de edifícios e infraestrutura")
    
else:
    print("❌ Arquivo 'sentinel1_unicamp_raw.npy' não encontrado!")
    print("Execute primeiro o script 'sentinel1_simple.py' para gerar os dados.")