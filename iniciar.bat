@echo off
REM Inicia la API y abre la interfaz local del agente.
cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo No se encontro el entorno virtual venv. Cree e instale las dependencias primero.
    pause
    exit /b 1
)

call "venv\Scripts\activate.bat"
python -c "from dotenv import load_dotenv; import os,urllib.request; load_dotenv(); urllib.request.urlopen(os.getenv('OLLAMA_HOST','http://localhost:11434').rstrip('/')+'/api/tags',timeout=3)" >nul 2>nul
if errorlevel 1 (
    echo AVISO: Ollama no responde. Inicie Ollama para habilitar las respuestas del modelo.
)

start "" "http://127.0.0.1:8000"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
