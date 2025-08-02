# app.py
from flask import Flask, render_template, request, jsonify, send_from_directory
from threading import Thread
import run_analysis
import time
import os
import traceback
from pathlib import Path
import logging

# Configurar logging
log_file = Path(__file__).resolve().parent / 'pipeline.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='a'),  # Usa caminho absoluto e modo append
        logging.StreamHandler()
    ]
)

try:
    with open(log_file, 'a') as f:
        f.write('')  # Testa permissões de escrita
except Exception as e:
    logging.error(f"Erro ao acessar pipeline.log: {e}")

# Configuração correta para servir arquivos estáticos
app = Flask(__name__, 
            static_url_path='/static',
            static_folder='static',
            template_folder='templates')

analysis_status = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health_check():
    """Endpoint de verificação de saúde do servidor"""
    active_jobs = len([job for job in analysis_status.values() if job.get('status') == 'running'])
    return jsonify({
        "status": "online",
        "active_jobs": active_jobs,
        "total_jobs": len(analysis_status)
    })

@app.route('/output/<path:filename>')
def serve_output_files(filename):
    """Serve arquivos gerados na pasta output"""
    try:
        output_dir = Path('output')
        if not output_dir.exists():
            return "Output directory not found", 404
        return send_from_directory(output_dir, filename)
    except Exception as e:
        logging.error(f"[SERVER] Erro ao servir arquivo de output {filename}: {str(e)}")
        return "File not found", 404

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Serve arquivos da pasta assets"""
    try:
        assets_dir = Path('assets')
        if not assets_dir.exists():
            return "Assets directory not found", 404
        return send_from_directory(assets_dir, filename)
    except Exception as e:
        logging.error(f"[SERVER] Erro ao servir arquivo de assets {filename}: {str(e)}")
        return "File not found", 404

@app.route('/<path:filename>')
def serve_root_files(filename):
    """Serve arquivos da raiz do projeto"""
    try:
        return app.send_static_file(f'../{filename}')
    except:
        return "File not found", 404

@app.route('/run', methods=['POST'])
def run_analysis_endpoint():
    data = request.json
    lat, lon, size = data.get('lat'), data.get('lon'), data.get('size', 15.0)
    
    job_id = f"analysis_{lat}_{lon}_{int(time.time())}"
    analysis_status[job_id] = {"status": "running"}

    logging.info(f"[SERVER] Nova análise requisitada. Job ID: {job_id}")
    thread = Thread(target=run_analysis_in_background, args=(job_id, lat, lon, size))
    thread.start()
    
    return jsonify({"status": "Analysis started", "job_id": job_id})

def run_analysis_in_background(job_id, lat, lon, size):
    try:
        summary_data = run_analysis.execute_pipeline(lat, lon, size, job_id)
        if summary_data:
            analysis_status[job_id] = {"status": "complete", "result": summary_data}
            logging.info(f"[SERVER] Análise CONCLUÍDA com sucesso para o Job ID: {job_id}")
        else:
            raise Exception("Pipeline não retornou resultados.")
    except Exception as e:
        error_message = f"Erro interno no pipeline: {str(e)}"
        logging.error(f"[SERVER] ERRO CRÍTICO na análise para o Job ID {job_id}: {error_message}")
        logging.error(traceback.format_exc())
        analysis_status[job_id] = {"status": "error", "message": error_message}

@app.route('/status/<job_id>')
def get_status(job_id):
    return jsonify(analysis_status.get(job_id, {"status": "not_found"}))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)