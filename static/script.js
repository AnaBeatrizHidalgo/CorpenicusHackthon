document.addEventListener('DOMContentLoaded', () => {
    const runBtn = document.getElementById('run-btn');
    const latInput = document.getElementById('lat-input');
    const lonInput = document.getElementById('lon-input');
    const statusDiv = document.getElementById('status-message');
    const mapFrame = document.getElementById('map-frame');
    const mapPlaceholder = document.getElementById('map-placeholder');
    const loadingOverlay = document.getElementById('loading-overlay');

    // Mapeamento de IDs para elementos do painel
    const panelElements = {
        'pools-found': document.getElementById('pools-found'),
        'high-risk-sectors': document.getElementById('high-risk-sectors'),
        'avg-ndvi': document.getElementById('avg-ndvi'),
        'avg-temp': document.getElementById('avg-temp'),
        'total-precip': document.getElementById('total-precip')
    };

    // Função para mostrar status com diferentes tipos
    function showStatus(message, type = 'info') {
        statusDiv.textContent = message;
        statusDiv.className = `status-${type}`;
        console.log(`[STATUS-${type.toUpperCase()}] ${message}`);
    }

    // Função para validar coordenadas
    function validateCoordinates(lat, lon) {
        const latNum = parseFloat(lat);
        const lonNum = parseFloat(lon);

        if (isNaN(latNum) || isNaN(lonNum)) {
            return { valid: false, error: 'Coordenadas devem ser números válidos' };
        }

        if (latNum < -90 || latNum > 90) {
            return { valid: false, error: 'Latitude deve estar entre -90 e 90' };
        }

        if (lonNum < -180 || lonNum > 180) {
            return { valid: false, error: 'Longitude deve estar entre -180 e 180' };
        }

        return { valid: true, lat: latNum, lon: lonNum };
    }

    // Event listener principal do botão
    runBtn.addEventListener('click', () => {
        const lat = latInput.value.trim();
        const lon = lonInput.value.trim();

        // Validação básica
        if (!lat || !lon) {
            showStatus('Por favor, insira latitude e longitude.', 'error');
            return;
        }

        // Validação avançada
        const validation = validateCoordinates(lat, lon);
        if (!validation.valid) {
            showStatus(validation.error, 'error');
            return;
        }

        // Inicia análise
        console.log(`[ANALYSIS] Iniciando análise para coordenadas: ${validation.lat}, ${validation.lon}`);
        showStatus('Iniciando análise... Isso pode levar vários minutos.', 'info');
        
        runBtn.disabled = true;
        if (loadingOverlay) loadingOverlay.style.display = 'flex';

        // Faz a requisição para o servidor
        fetch('/run', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ 
                lat: validation.lat, 
                lon: validation.lon,
                size: 3.0 // Tamanho padrão da área
            })
        })
        .then(response => {
            console.log(`[HTTP] Response status: ${response.status}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('[HTTP] Response data:', data);
            if (data.job_id) {
                showStatus('Análise em andamento... Verificando status.', 'info');
                checkStatus(data.job_id);
            } else {
                throw new Error('Servidor não retornou job_id');
            }
        })
        .catch(error => {
            console.error('[ERROR] Falha ao iniciar análise:', error);
            showStatus(`Erro ao iniciar análise: ${error.message}`, 'error');
            runBtn.disabled = false;
            if (loadingOverlay) loadingOverlay.style.display = 'none';
        });
    });

    function checkStatus(jobId) {
        console.log(`[STATUS-CHECK] Iniciando monitoramento do job: ${jobId}`);
        let attempts = 0;
        const maxAttempts = 120; // 10 minutos máximo (5s * 120 = 600s)

        const interval = setInterval(() => {
            attempts++;
            console.log(`[STATUS-CHECK] Tentativa ${attempts}/${maxAttempts}`);
            
            // Timeout de segurança
            if (attempts > maxAttempts) {
                clearInterval(interval);
                console.error('[TIMEOUT] Análise excedeu tempo limite');
                showStatus('Timeout: Análise demorou muito para completar.', 'error');
                runBtn.disabled = false;
                if (loadingOverlay) loadingOverlay.style.display = 'none';
                return;
            }

            // Verifica status no servidor
            fetch(`/status/${jobId}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log(`[STATUS-CHECK] Status atual: ${data.status}`, data);

                    if (data.status === 'complete') {
                        clearInterval(interval);
                        console.log('[SUCCESS] Análise concluída com sucesso');
                        showStatus('Análise concluída! Carregando resultados...', 'success');
                        
                        if (data.result) {
                            updateDashboard(data.result);
                        } else {
                            showStatus('Análise concluída, mas sem dados de resultado.', 'error');
                        }
                        
                        runBtn.disabled = false;
                        if (loadingOverlay) loadingOverlay.style.display = 'none';
                        
                    } else if (data.status === 'error') {
                        clearInterval(interval);
                        const errorMsg = data.message || 'Erro desconhecido na análise';
                        console.error('[ERROR] Análise falhou:', errorMsg);
                        showStatus(`Erro na análise: ${errorMsg}`, 'error');
                        runBtn.disabled = false;
                        if (loadingOverlay) loadingOverlay.style.display = 'none';
                        
                    } else if (data.status === 'not_found') {
                        clearInterval(interval);
                        console.error('[ERROR] Job não encontrado no servidor');
                        showStatus('Job não encontrado no servidor.', 'error');
                        runBtn.disabled = false;
                        if (loadingOverlay) loadingOverlay.style.display = 'none';
                        
                    } else if (data.status === 'running') {
                        // Continua monitorando
                        showStatus(`Análise em progresso... (${attempts}/${maxAttempts})`, 'info');
                    }
                })
                .catch(error => {
                    console.warn(`[WARNING] Erro na verificação de status (tentativa ${attempts}):`, error);
                    // Não para o monitoramento por erro de rede, tenta novamente
                    if (attempts % 10 === 0) {
                        showStatus(`Verificando status... Tentativa ${attempts}`, 'info');
                    }
                });
        }, 5000); // Verifica a cada 5 segundos
    }

    function updateDashboard(summary) {
        console.log('[DASHBOARD] Atualizando interface com dados:', summary);

        try {
            // === ATUALIZAÇÃO DO MAPA ===
            if (summary.map_url) {
                // Adiciona cache bust para forçar reload
                const mapUrl = summary.map_url + '?t=' + Date.now();
                console.log(`[MAP] Carregando mapa de: ${mapUrl}`);
                
                // Configura iframe do mapa
                if (mapFrame && mapPlaceholder) {
                    mapFrame.src = mapUrl;
                    
                    // Event listeners para debug
                    mapFrame.onload = () => {
                        console.log('[MAP] Mapa carregado com sucesso no iframe');
                        mapPlaceholder.style.display = 'none';
                        mapFrame.style.display = 'block';
                        
                        // Mostra elementos sobrepostos do mapa
                        const legend = document.getElementById('map-legend');
                        const stats = document.getElementById('map-stats');
                        if (legend) legend.style.display = 'block';
                        if (stats) stats.style.display = 'block';
                    };
                    
                    mapFrame.onerror = (error) => {
                        console.error('[MAP] Erro ao carregar mapa:', error);
                        showStatus('Mapa gerado, mas erro ao carregar na interface.', 'error');
                    };
                    
                    // Fallback: força exibição após timeout
                    setTimeout(() => {
                        if (mapFrame.src && mapPlaceholder.style.display !== 'none') {
                            console.log('[MAP] Forçando exibição do mapa (fallback)');
                            mapPlaceholder.style.display = 'none';
                            mapFrame.style.display = 'block';
                        }
                    }, 3000);
                }
            } else {
                console.warn('[MAP] URL do mapa não encontrada nos resultados');
            }

            // === ATUALIZAÇÃO DAS MÉTRICAS ===
            
            // Piscinas detectadas
            if (panelElements['pools-found']) {
                const poolsCount = summary.dirty_pools_found || 0;
                panelElements['pools-found'].textContent = poolsCount;
                console.log(`[METRICS] Piscinas detectadas: ${poolsCount}`);
            }

            // Setores de alto risco
            if (panelElements['high-risk-sectors']) {
                const highRisk = (summary.risk_distribution?.['Alto'] || 0) + 
                               (summary.risk_distribution?.['Crítico'] || 0);
                panelElements['high-risk-sectors'].textContent = highRisk;
                console.log(`[METRICS] Setores de alto risco: ${highRisk}`);
            }

            // NDVI médio
            if (panelElements['avg-ndvi']) {
                const ndvi = summary.avg_ndvi || 'N/D';
                panelElements['avg-ndvi'].textContent = ndvi;
                console.log(`[METRICS] NDVI médio: ${ndvi}`);
            }

            // Temperatura média
            if (panelElements['avg-temp']) {
                const temp = summary.avg_temp_celsius ? 
                    `${summary.avg_temp_celsius}°C` : 'N/D';
                panelElements['avg-temp'].textContent = temp;
                console.log(`[METRICS] Temperatura média: ${temp}`);
            }

            // Precipitação total
            if (panelElements['total-precip']) {
                const precip = summary.total_precip_mm ? 
                    `${summary.total_precip_mm} mm` : 'N/D';
                panelElements['total-precip'].textContent = precip;
                console.log(`[METRICS] Precipitação total: ${precip}`);
            }

            // === STATUS FINAL ===
            showStatus('Resultados carregados com sucesso!', 'success');
            console.log('[DASHBOARD] Interface atualizada com sucesso');

        } catch (error) {
            console.error('[ERROR] Erro ao atualizar dashboard:', error);
            showStatus('Erro ao atualizar interface com os resultados.', 'error');
        }
    }

    // === FUNCIONALIDADES EXTRAS ===

    // Interação com cards de métricas
    document.querySelectorAll('.metrics-card').forEach(card => {
        card.addEventListener('click', function() {
            const title = this.querySelector('.metrics-title')?.textContent || 'Métrica';
            console.log(`[UI] Clique na métrica: ${title}`);
            // Aqui poderia abrir modal com detalhes
        });
    });

    // Botão WhatsApp
    const whatsappBtn = document.querySelector('.whatsapp-btn');
    if (whatsappBtn) {
        whatsappBtn.addEventListener('click', function() {
            console.log('[UI] Clique no botão WhatsApp');
            alert('Funcionalidade de WhatsApp será implementada em breve!');
        });
    }

    // Atalho para coordenadas de teste (Ctrl+D)
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.key === 'd') {
            e.preventDefault();
            latInput.value = '-22.818';
            lonInput.value = '-47.069';
            console.log('[DEBUG] Coordenadas padrão inseridas (Indaiatuba, SP)');
            showStatus('Coordenadas de teste inseridas (Indaiatuba, SP)', 'info');
        }
    });

    // Log de inicialização
    console.log('[INIT] NAIA Dashboard inicializado com sucesso');
    console.log('[DEBUG] Use Ctrl+D para inserir coordenadas de teste');
    
    // Verificação de elementos críticos
    const criticalElements = {
        'runBtn': runBtn,
        'latInput': latInput,
        'lonInput': lonInput,
        'statusDiv': statusDiv,
        'mapFrame': mapFrame
    };
    
    Object.entries(criticalElements).forEach(([name, element]) => {
        if (!element) {
            console.error(`[INIT-ERROR] Elemento crítico não encontrado: ${name}`);
        }
    });
});