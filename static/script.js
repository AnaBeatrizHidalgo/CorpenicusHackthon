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
        showStatus('Iniciando análise...', 'info');
        
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
                
                showStatus(`Verificando progresso... (${attempts}/${maxAttempts})`, 'info');
                
                if (data.status === 'complete') {
                    showStatus('Análise concluída!', 'success');
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
    
    // === ATUALIZAR DASHBOARD ===
    function updateDashboard(summary) {
        console.log('Atualizando dashboard:', summary);
        
        try {
            // Atualizar mapa
            if (summary.map_url) {
                const mapUrl = summary.map_url + '?t=' + Date.now();
                mapFrame.src = mapUrl;
                mapPlaceholder.style.display = 'none';
                mapFrame.style.display = 'block';
            }
            
            // Atualizar métricas
            if (poolsFound) poolsFound.textContent = summary.dirty_pools_found || 0;
            
            if (highRiskSectors) {
                const highRisk = (summary.risk_distribution?.Alto || 0) + 
                               (summary.risk_distribution?.Crítico || 0);
                highRiskSectors.textContent = highRisk;
            }
            
            if (avgNdvi) avgNdvi.textContent = summary.avg_ndvi || 'N/D';
            if (avgTemp) avgTemp.textContent = summary.avg_temp_celsius ? `${summary.avg_temp_celsius}°C` : 'N/D';
            if (totalPrecip) totalPrecip.textContent = summary.total_precip_mm ? `${summary.total_precip_mm} mm` : 'N/D';
            
            showStatus('Dashboard atualizado!', 'success');
            
        } catch (error) {
            console.error('Erro ao atualizar dashboard:', error);
            showStatus('Erro ao atualizar interface', 'error');
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
            showStatus('Coordenadas de teste inseridas', 'info');
        }
    });
    
    // === INICIALIZAÇÃO ===
    setTimeout(checkServer, 1000);
    
    console.log(`Servidor configurado para: ${SERVER_URL}`);
    console.log('Use Ctrl+D para coordenadas de teste');
});