document.addEventListener('DOMContentLoaded', () => {
    console.log('NAIA Dashboard carregado');
    
    // === ELEMENTOS DOM ===
    const runBtn = document.getElementById('run-btn');
    const latInput = document.getElementById('lat-input');
    const lonInput = document.getElementById('lon-input');
    const statusDiv = document.getElementById('status-message');
    const mapFrame = document.getElementById('map-frame');
    const mapPlaceholder = document.getElementById('map-placeholder');
    const loadingOverlay = document.getElementById('loading-overlay');
    
    // Métricas
    const poolsFound = document.getElementById('pools-found');
    const highRiskSectors = document.getElementById('high-risk-sectors');
    const avgNdvi = document.getElementById('avg-ndvi');
    const avgTemp = document.getElementById('avg-temp');
    const totalPrecip = document.getElementById('total-precip');
    
    // === CONFIGURAÇÃO ===
    const SERVER_URL = window.location.origin; // Auto-detecta a URL
    
    // === FUNÇÕES AUXILIARES ===
    function showStatus(message, type = 'info') {
        statusDiv.textContent = message;
        statusDiv.className = `status-${type}`;
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
    
    function showLoading(show) {
        loadingOverlay.style.display = show ? 'flex' : 'none';
        runBtn.disabled = show;
        
        if (show) {
            // Adiciona mensagem motivacional durante o carregamento
            const loadingMessages = [
                'Analisando dados climáticos...',
                'Processando imagens de satélite...',
                'Calculando riscos de dengue...',
                'Detectando piscinas e água parada...',
                'Gerando mapa interativo...'
            ];
            
            let messageIndex = 0;
            const messageInterval = setInterval(() => {
                const loadingDetail = document.getElementById('loading-detail');
                if (loadingDetail && show) {
                    loadingDetail.textContent = loadingMessages[messageIndex % loadingMessages.length];
                    messageIndex++;
                } else {
                    clearInterval(messageInterval);
                }
            }, 3000);
        }
    }
    
    // === VERIFICAÇÃO DO SERVIDOR ===
    async function checkServer() {
        try {
            const response = await fetch(`${SERVER_URL}/health`);
            const data = await response.json();
            
            if (data.status === 'online') {
                showStatus(`Servidor online - ${data.active_jobs || 0} jobs ativos`, 'success');
                return true;
            }
        } catch (error) {
            showStatus('Servidor offline. Verifique se o Flask está rodando.', 'error');
            return false;
        }
    }
    
    // === EXECUTAR ANÁLISE ===
    async function runAnalysis() {
        const lat = parseFloat(latInput.value);
        const lon = parseFloat(lonInput.value);
        
        // Validações
        if (!lat || !lon || isNaN(lat) || isNaN(lon)) {
            showStatus('Insira coordenadas válidas', 'error');
            return;
        }
        
        if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
            showStatus('Coordenadas fora do range válido', 'error');
            return;
        }
        
        // Verifica servidor
        const serverOk = await checkServer();
        if (!serverOk) return;
        
        showLoading(true);
        showStatus('Iniciando análise de risco de dengue...', 'info');
        
        try {
            // Inicia análise
            const response = await fetch(`${SERVER_URL}/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lat, lon, size: 3.0 })
            });
            
            const data = await response.json();
            
            if (data.job_id) {
                showStatus(`Análise iniciada - Job: ${data.job_id}`, 'info');
                monitorJob(data.job_id);
            } else {
                throw new Error('Job ID não retornado');
            }
            
        } catch (error) {
            showStatus(`Erro: ${error.message}`, 'error');
            showLoading(false);
        }
    }
    
    // === MONITORAR JOB ===
    async function monitorJob(jobId) {
        let attempts = 0;
        const maxAttempts = 120; // 10 minutos
        
        const checkStatus = async () => {
            attempts++;
            
            if (attempts > maxAttempts) {
                showStatus('Timeout: Análise demorou muito', 'error');
                showLoading(false);
                return;
            }
            
            try {
                const response = await fetch(`${SERVER_URL}/status/${jobId}`);
                const data = await response.json();
                
                // Mensagem de progresso mais informativa
                const timeElapsed = Math.floor(attempts * 5 / 60);
                showStatus(`Processando análise... ${attempts}/${maxAttempts} (${timeElapsed}min)`, 'info');
                
                if (data.status === 'complete') {
                    showStatus('✅ Análise de risco concluída!', 'success');
                    updateDashboard(data.result);
                    showLoading(false);
                    
                } else if (data.status === 'error') {
                    showStatus(`Erro na análise: ${data.message}`, 'error');
                    showLoading(false);
                    
                } else if (data.status === 'not_found') {
                    showStatus('Job não encontrado', 'error');
                    showLoading(false);
                    
                } else {
                    // Continua verificando
                    setTimeout(checkStatus, 5000);
                }
                
            } catch (error) {
                console.warn('Erro ao verificar status:', error);
                setTimeout(checkStatus, 5000);
            }
        };
        
        setTimeout(checkStatus, 2000);
    }
    
    // === ATUALIZAR DASHBOARD COM PORCENTAGEM ===
    function updateDashboard(summary) {
        console.log('Atualizando dashboard com dados:', summary);
        
        try {
            // Atualizar mapa
            if (summary.map_url) {
                const mapUrl = summary.map_url + '?t=' + Date.now();
                mapFrame.src = mapUrl;
                mapPlaceholder.style.display = 'none';
                mapFrame.style.display = 'block';
                
                console.log('✅ Mapa carregado:', mapUrl);
            }
            
            // === ATUALIZAR MÉTRICAS COM FOCO NA PORCENTAGEM ===
            
            // Piscinas detectadas
            if (poolsFound) {
                const poolCount = summary.dirty_pools_found || 0;
                poolsFound.textContent = poolCount;
                
                // Adiciona indicador visual se piscinas foram encontradas
                if (poolCount > 0) {
                    poolsFound.style.color = '#FF5722';
                    poolsFound.style.fontWeight = 'bold';
                } else {
                    poolsFound.style.color = '#4CAF50';
                }
            }
            
            // Setores de alto risco
            if (highRiskSectors) {
                const highRisk = (summary.risk_distribution?.Alto || 0) + 
                               (summary.risk_distribution?.Crítico || 0);
                highRiskSectors.textContent = highRisk;
                
                // Adiciona indicador de cor baseado no número
                if (highRisk > 10) {
                    highRiskSectors.style.color = '#FF5722';
                } else if (highRisk > 5) {
                    highRiskSectors.style.color = '#FF9800';
                } else {
                    highRiskSectors.style.color = '#4CAF50';
                }
            }
            
            // NDVI médio
            if (avgNdvi) {
                avgNdvi.textContent = summary.avg_ndvi || 'N/D';
            }
            
            // Temperatura média
            if (avgTemp) {
                avgTemp.textContent = summary.avg_temp_celsius ? `${summary.avg_temp_celsius}°C` : 'N/D';
            }
            
            // Precipitação total
            if (totalPrecip) {
                totalPrecip.textContent = summary.total_precip_mm ? `${summary.total_precip_mm} mm` : 'N/D';
            }
            
            showRiskStatistics(summary);
            
            createSuccessNotification(summary);
            
            showStatus('✅ Dashboard atualizado com análise de risco!', 'success');
            
        } catch (error) {
            console.error('Erro ao atualizar dashboard:', error);
            showStatus('Erro ao atualizar interface', 'error');
        }
    }
    
    function showRiskStatistics(summary) {
        try {
            // Cria ou atualiza painel de estatísticas de risco
            let riskStatsPanel = document.getElementById('risk-stats-panel');
            
            if (!riskStatsPanel) {
                // Cria novo painel se não existir
                riskStatsPanel = document.createElement('div');
                riskStatsPanel.id = 'risk-stats-panel';
                riskStatsPanel.className = 'sidebar-panel';
                
                // Adiciona ao sidebar antes do community panel
                const sidebar = document.querySelector('.sidebar');
                const communityPanel = document.querySelector('.community-section');
                sidebar.insertBefore(riskStatsPanel, communityPanel);
            }
            
            // Conteúdo do painel de estatísticas
            const avgRisk = summary.avg_risk_percentage || '0%';
            const maxRisk = summary.max_risk_percentage || '0%';
            const totalSectors = summary.total_sectors || 0;
            
            riskStatsPanel.innerHTML = `
                <h3 class="panel-title">
                    <i class="fas fa-percentage"></i>
                    Estatísticas de Risco
                </h3>
                
                <div class="metrics-card" style="background: linear-gradient(135deg, #FF5722, #FF7043); color: white;">
                    <div style="display: flex; align-items: center;">
                        <i class="fas fa-chart-line" style="color: white; margin-right: 12px; font-size: 1.2em;"></i>
                        <div class="metrics-text">
                            <div class="metrics-title" style="color: rgba(255,255,255,0.9);">Risco Médio da Área</div>
                            <div class="metrics-value" style="color: white; font-size: 1.4em;">${avgRisk}</div>
                        </div>
                    </div>
                </div>

                <div class="metrics-card" style="background: linear-gradient(135deg, #D32F2F, #F44336); color: white;">
                    <div style="display: flex; align-items: center;">
                        <i class="fas fa-exclamation-triangle" style="color: white; margin-right: 12px; font-size: 1.2em;"></i>
                        <div class="metrics-text">
                            <div class="metrics-title" style="color: rgba(255,255,255,0.9);">Risco Máximo Detectado</div>
                            <div class="metrics-value" style="color: white; font-size: 1.4em;">${maxRisk}</div>
                        </div>
                    </div>
                </div>

                <div class="metrics-card">
                    <div style="display: flex; align-items: center;">
                        <i class="fas fa-map" style="color: #2196F3; margin-right: 12px;"></i>
                        <div class="metrics-text">
                            <div class="metrics-title">Total de Setores Analisados</div>
                            <div class="metrics-value">${totalSectors}</div>
                        </div>
                    </div>
                </div>
                
                <div style="margin-top: 15px; padding: 10px; background: rgba(255, 124, 51, 0.1); border-radius: 8px; border-left: 4px solid #FF7C33;">
                    <p style="margin: 0; font-size: 12px; color: #666;">
                        💡 <strong>Dica:</strong> Clique nas áreas do mapa para ver a porcentagem exata de risco de dengue em cada setor.
                    </p>
                </div>
            `;
            
            // Adiciona animação de entrada
            riskStatsPanel.style.animation = 'slideInUp 0.5s ease-out';
            
        } catch (error) {
            console.error('Erro ao mostrar estatísticas de risco:', error);
        }
    }
    
    function createSuccessNotification(summary) {
        try {
            // Remove notificação anterior se existir
            const existingNotification = document.querySelector('.success-notification');
            if (existingNotification) {
                existingNotification.remove();
            }
            
            // Cria nova notificação
            const notification = document.createElement('div');
            notification.className = 'success-notification';
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: linear-gradient(135deg, #4CAF50, #45a049);
                color: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 20px rgba(76, 175, 80, 0.3);
                z-index: 10000;
                min-width: 300px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                animation: slideInRight 0.5s ease-out;
            `;
            
            const avgRisk = summary.avg_risk_percentage || '0%';
            const poolsFound = summary.dirty_pools_found || 0;
            
            notification.innerHTML = `
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <i class="fas fa-check-circle" style="font-size: 1.5em; margin-right: 10px;"></i>
                    <h4 style="margin: 0; font-size: 1.1em;">Análise Concluída!</h4>
                    <button onclick="this.parentElement.parentElement.remove()" style="
                        background: none; 
                        border: none; 
                        color: white; 
                        font-size: 1.2em; 
                        margin-left: auto; 
                        cursor: pointer;
                        opacity: 0.7;
                    ">×</button>
                </div>
                <p style="margin: 5px 0; font-size: 14px;">
                    🎯 <strong>Risco médio:</strong> ${avgRisk}<br>
                    🏊 <strong>Piscinas detectadas:</strong> ${poolsFound}<br>
                    🗺️ <strong>Clique no mapa</strong> para ver detalhes por área
                </p>
            `;
            
            document.body.appendChild(notification);
            
            // Remove automaticamente após 8 segundos
            setTimeout(() => {
                if (notification.parentElement) {
                    notification.style.animation = 'slideOutRight 0.5s ease-in';
                    setTimeout(() => notification.remove(), 500);
                }
            }, 8000);
            
        } catch (error) {
            console.error('Erro ao criar notificação:', error);
        }
    }
    
    // === EVENT LISTENERS ===
    runBtn.addEventListener('click', runAnalysis);
    
    // Atalho Ctrl+D para coordenadas de teste
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'd') {
            e.preventDefault();
            latInput.value = '-22.818';
            lonInput.value = '-47.069';
            showStatus('📍 Coordenadas de teste inseridas (Indaiatuba, SP)', 'info');
        }
        
        // Atalho Ctrl+R para executar análise
        if (e.ctrlKey && e.key === 'r' && !runBtn.disabled) {
            e.preventDefault();
            runAnalysis();
        }
    });
    
    // Melhora a UX com validação em tempo real
    [latInput, lonInput].forEach(input => {
        input.addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            const isLat = e.target === latInput;
            
            // Remove estilo de erro anterior
            e.target.style.borderColor = '';
            
            if (e.target.value && !isNaN(value)) {
                if (isLat && (value < -90 || value > 90)) {
                    e.target.style.borderColor = '#FF5722';
                } else if (!isLat && (value < -180 || value > 180)) {
                    e.target.style.borderColor = '#FF5722';
                } else {
                    e.target.style.borderColor = '#4CAF50';
                }
            }
        });
    });
    
    // === CSS DINÂMICO ===
    const dynamicStyles = document.createElement('style');
    dynamicStyles.textContent = `
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
        
        @keyframes slideInUp {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        
        .success-notification {
            backdrop-filter: blur(10px);
        }
        
        .metrics-card:hover {
            transform: translateY(-2px);
            transition: transform 0.2s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        
        input:focus {
            outline: 2px solid #FF7C33;
            outline-offset: 2px;
        }
    `;
    document.head.appendChild(dynamicStyles);
    
    // === INICIALIZAÇÃO ===
    setTimeout(checkServer, 1000);
    
    console.log(`🚀 NAIA Dashboard inicializado`);
    console.log(`📡 Servidor: ${SERVER_URL}`);
    console.log(`⌨️ Atalhos:`);
    console.log(`   Ctrl+D = Coordenadas de teste`);
    console.log(`   Ctrl+R = Executar análise`);
    console.log(`💡 Clique nas áreas do mapa para ver porcentagem de risco!`);
});