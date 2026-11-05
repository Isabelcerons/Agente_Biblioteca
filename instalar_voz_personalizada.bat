@echo off
setlocal
set "PYTHON=%~dp0venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo No se encontro el entorno del proyecto. Crea primero venv e instala requirements.txt.
  exit /b 1
)
echo Instalando PyTorch para CPU...
"%PYTHON%" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 exit /b 1
echo Instalando Coqui TTS para la voz personalizada...
"%PYTHON%" -m pip install "coqui-tts[codec]==0.28.0"
if errorlevel 1 exit /b 1
"%PYTHON%" -m pip install six
if errorlevel 1 exit /b 1
echo Listo. La primera prueba descargara el modelo XTTS-v2.
endlocal
