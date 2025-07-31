document.addEventListener('DOMContentLoaded', () => {
    const runBtn = document.getElementById('run-btn');
    const latInput = document.getElementById('lat-input');
    const lonInput = document.getElementById('lon-input');
    const statusDiv = document.getElementById('status-message');
    const mapFrame = document.getElementById('map-frame');

    // Mapeamento de IDs para elementos do painel
    const panelElements = {
        'pools-found': document.getElementById('pools-found'),
        'high-risk-sectors': document.getElementById('high-risk-sectors'),
        'avg-ndvi': document.getElementById('avg-ndvi'),
        'avg-temp': document.getElementById('avg-temp'),
        'total-precip': document.getElementById('total-precip')
    };

    runBtn.addEventListener('click', () => {
        const lat = latInput.value;
        const lon = lonInput.value;

        if (!lat || !lon) {
            statusDiv.textContent = 'Por favor, insira latitude e longitude.';
            return;
        }

        statusDiv.textContent = 'Iniciando análise... Isso pode levar vários minutos.';
        runBtn.disabled = true;

        fetch('/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: parseFloat(lat), lon: parseFloat(lon) })
        })
            .then(response => response.json())
            .then(data => {
                if (data.job_id) {
                    statusDiv.textContent = 'Análise em andamento... Verificando status.';
                    checkStatus(data.job_id);
                } else {
                    statusDiv.textContent = 'Erro ao iniciar a análise.';
                    runBtn.disabled = false;
                }
            });
    });

    function checkStatus(jobId) {
        const interval = setInterval(() => {
            fetch(`/status/${jobId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'complete') {
                        clearInterval(interval);
                        statusDiv.textContent = 'Análise concluída! Carregando resultados...';
                        updateDashboard(data.result);
                        runBtn.disabled = false;
                    } else if (data.status === 'error') {
                        clearInterval(interval);
                        // Mostra uma mensagem de erro mais útil
                        statusDiv.innerHTML = `<strong>Erro na análise:</strong><br><small>${data.message}</small>`;
                        runBtn.disabled = false;
                        console.error('Erro retornado pelo servidor:', data.message);
                    }
                });
        }, 5000);
    }

    function updateDashboard(summary) {
        mapFrame.src = summary.map_url;

        panelElements['pools-found'].textContent = summary.dirty_pools_found;
        panelElements['high-risk-sectors'].textContent = (summary.risk_distribution['Alto'] || 0) + (summary.risk_distribution['Crítico'] || 0);
        panelElements['avg-ndvi'].textContent = summary.avg_ndvi;
        panelElements['avg-temp'].textContent = `${summary.avg_temp_celsius} °C`;
        panelElements['total-precip'].textContent = `${summary.total_precip_mm} mm`;
        statusDiv.textContent = 'Resultados carregados.';
    }
});