from flask import Flask, render_template, request, jsonify
from threading import Thread
import run_analysis
import time
import os
import traceback

# Serve a pasta raiz do projeto como estática
app = Flask(__name__, static_url_path='', static_folder=os.getcwd())
analysis_status = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run_analysis_endpoint():
    data = request.json
    lat, lon, size = data.get('lat'), data.get('lon'), data.get('size', 3.0)
    
    job_id = f"analysis_{lat}_{lon}_{int(time.time())}"
    analysis_status[job_id] = {"status": "running"}

    print(f"\n[SERVER] Nova análise requisitada. Job ID: {job_id}")
    thread = Thread(target=run_analysis_in_background, args=(job_id, lat, lon, size))
    thread.start()
    
    return jsonify({"status": "Analysis started", "job_id": job_id})

def run_analysis_in_background(job_id, lat, lon, size):
    try:
        summary_data = run_analysis.execute_pipeline(lat, lon, size, job_id)
        if summary_data:
            analysis_status[job_id] = {"status": "complete", "result": summary_data}
            print(f"[SERVER] Análise CONCLUÍDA com sucesso para o Job ID: {job_id}")
        else:
            raise Exception("Pipeline não retornou resultados.")
            
    except Exception as e:
        error_message = f"Erro interno no pipeline: {str(e)}"
        print(f"[SERVER] ERRO CRÍTICO na análise para o Job ID {job_id}: {error_message}")
        print(traceback.format_exc())
        analysis_status[job_id] = {"status": "error", "message": error_message}

@app.route('/status/<job_id>')
def get_status(job_id):
    return jsonify(analysis_status.get(job_id, {"status": "not_found"}))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)