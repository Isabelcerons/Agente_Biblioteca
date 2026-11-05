# Calidad de voz local y transcripción previa

Se seleccionó `voces/es_MX-claude-high.onnx`, ya presente, con `PIPER_LENGTH_SCALE=0.92`. La evidencia previa comunicada por el coordinador favorecía su inteligibilidad al dictar números. Esta ejecución comprobó archivos y rendimiento, sin escucha humana ni evaluación perceptual: la naturalidad y la preferencia final deben confirmarse escuchando las muestras. No se descargaron modelos, no se instalaron dependencias ni se usaron APIs externas de voz.

## Configuración y límites

`app/config.py` conserva las otras opciones y admite escala entre 0.75 y 1.25 (valores no finitos también se rechazan). Por defecto usa Claude high; `.env` y `.env.example` seleccionan esa voz y escala 0.92. Para comparar sin acelerar usar 1.0; para volver al modelo anterior usar `PIPER_VOZ=voces/es_MX-ald-medium.onnx`. No se cambiaron credenciales ni parámetros STT/LLM.

Se inspeccionó `venv/Lib/site-packages/piper/config.py` y `voice.py`: `SynthesisConfig.length_scale` ajusta duración de fonemas sin remuestrear ni cambiar tono; esta versión no expone `sentence_silence`. Se preservan puntuación, prosodia y niveles de ruido originales del modelo, sin efectos añadidos ni silencios artificiales. La escala 0.92 ofrece una aceleración moderada; no garantiza exactamente 8 % menos duración porque hay variación estocástica y pausas propias del modelo.

`tts.sintetizar` conserva `wav_bytes`, `t_tts_ms`, `duracion_s`, entrada máxima de 600 caracteres, WAV en memoria, carga única con doble comprobación y candados separados para carga/síntesis. Se comprueba también el JSON del modelo para dar un error claro si falta. La función no registra texto, audio ni secretos. El cronómetro histórico mide síntesis después de cargar y adquirir candado: excluye carga inicial y espera en cola.

## Muestras y mediciones CPU

Ejecutar `venv/Scripts/python.exe evaluacion/voz_calidad_comparar.py`. Crea un directorio nuevo con fecha, nueve WAV y JSON; nunca sobrescribe audios existentes. Datos de esta ejecución: `evaluacion/voz_calidad_20261104_144855/voz_calidad_resultados.json`. Cada fila incluye texto sintético, modelo, escala, tiempo, duración, frecuencia y factor de tiempo real (RTF).

| Voz / escala | Bienvenida ms / duración s | Opciones ms / duración s | Números ms / duración s |
|---|---:|---:|---:|
| ald medium / 1.0 | 704 / 8.998 | 1055 / 14.571 | 779 / 11.714 |
| claude high / 1.0 | 559 / 7.837 | 994 / 13.433 | 820 / 11.146 |
| claude high / 0.92 | 547 / 7.477 | 990 / 12.968 | 757 / 10.728 |

Carga observada: ald 3668 ms y Claude 2484 ms en procesos ya iniciados y con cachés del sistema; no es un benchmark de disco frío. Todos los WAV son PCM mono, 16 bits, 22050 Hz, con frames y duración positivos. Claude 0.92 tuvo RTF 0.071–0.076: generó audio más rápido que tiempo real, con latencia de síntesis menor a un segundo en estos textos. Una pasada por texto; carga CPU compartida y aleatoriedad afectan cifras. Las muestras de números usan cantidades públicas ficticias, nunca PIN ni códigos de usuarios. No se hicieron afirmaciones de reconocimiento humano basadas solo en validez WAV.

## Endpoint de transcripción

Ampliación autorizada por el coordinador: `POST /api/transcribir`, multipart `audio` y `conversacion_id` opcional; responde `transcripcion`, `t_stt_ms`, `requiere_envio_seguro`. No ejecuta agente ni TTS, ni guarda transcripciones. Valida sesión y conversación antes y después de STT. UUID inválido: 400; inexistente: 404; ajena o estado con otro usuario: 403; fallo de validación: 503; audio inválido o mayor de 10 MB: 422, sin devolver detalles de excepciones.

Una conversación identificada exige el mismo usuario de sesión; invitado solo puede usar `usuario_id IS NULL` y estado sin otra identidad. Si antes o después de STT está esperando PIN, devuelve exclusivamente `[PIN oculto]` como transcripción y `requiere_envio_seguro=true`; el frontend reenvía el audio al `/api/voz` existente. No se alteró ese fallback. El contrato se comunicó al constructor del frontend por Orca. Sin conversación no hay estado PIN que consultar; el frontend debe conservar el ID. Los invitados no tienen token de propiedad de conversación individual en el esquema actual: el control distingue usuarios autenticados e invitados, no dos navegadores anónimos que conocen el mismo UUID. Tampoco se puede hacer atómica la lectura de estado y la respuesta HTTP: se revalida después de la operación lenta para reducir esa ventana.

## Selección de herramientas

Se omite solo la llamada LLM de decisión cuando los argumentos ya se reconstruyen de forma determinista: búsqueda exacta, disponibilidad, renovación, resumen, bibliografía y frases acotadas de cuenta personal. Conjunciones, negaciones y condiciones conservan LLM; también solicitudes genéricas de búsqueda semántica, reservas y reglamento. No se cambiaron las comprobaciones de autenticación, confirmación ni ejecución de operaciones. Las reglas existentes siguen fijando la herramienta prioritaria; la optimización evita pedir al LLM una decisión que esas reglas reemplazarían.

`evaluacion/voz_calidad_pruebas.py` compara rutas, argumentos y respuestas con decisión forzada previa y nueva para seis casos, usando mocks de persistencia/herramientas. Los 2500 ms de decisión de esa prueba son simulados y no se presentan como ahorro real. `evaluacion/voz_calidad_latencia.py` mide adicionalmente llamadas reales al LLM local sin ejecutar herramientas, y guarda `voz_calidad_latencia_llm.json`. En la ejecución real, «Mis préstamos» consumió 3458 ms de decisión LLM frente a 2.825 ms de selección local; la búsqueda de título consumió 5101 ms frente a 0.661 ms. Son dos solicitudes sin historial, una pasada cada una, y el LLM eligió disponibilidad para el título mientras la regla existente prevalecía con búsqueda exacta. No equivale a medir el tiempo total de una conversación con DB, búsqueda y redacción. Los resultados no prometen latencias bajo concurrencia.

## Validación e integración

`venv/Scripts/python.exe evaluacion/voz_calidad_pruebas.py`: 17 pruebas aisladas aprobadas; cubren PIN, cambio de estado durante STT, sesión que cambia, usuario propio/ajeno, invitado, UUID, DB no disponible, errores sin contenido sensible, selección comparable, ambigüedad carga concurrente única y límite/interfaz TTS. No invocan lifespan ni servidor compartido. La transcripción en estas pruebas está simulada; no constituye evaluación de precisión de Whisper.

No se reinició ni detuvo el servidor 8000. El coordinador debe reiniciarlo al integrar para cargar configuración y endpoint, y probar grabación/visualización/llamada en navegador. La preferencia de voz requiere escucha de la usuaria.
