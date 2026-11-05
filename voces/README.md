# Modelos de voz Piper

- `es_MX-claude-high`: voz mexicana predeterminada, modelo de [Piper voices](https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_MX/claude/high). El modelo declara MIT y su conjunto de entrenamiento, Apache 2.0.
- `es_MX-ald-medium`: voz alternativa mexicana, disponible desde [Piper voices](https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_MX/ald/medium).
- `es_ES-sharvard-medium`: voz de dos hablantes en español de España: `speaker_id=1` femenina y `speaker_id=0` masculina. [Modelo y tarjeta](https://huggingface.co/rhasspy/piper-voices/tree/main/es/es_ES/sharvard/medium). El modelo declara MIT y los datos de entrenamiento, CC BY 3.0; conserva la atribución indicada en esa tarjeta.

Los JSON junto a cada ONNX contienen la configuración de Piper. Si falta Sharvard, descárgalo con `python -m piper.download_voices es_ES-sharvard-medium --data-dir voces`.

`PIPER-LICENSE.md` conserva la licencia del motor Piper. La voz personalizada usa XTTS-v2 de forma local y requiere aceptar su licencia no comercial; el modelo se descarga desde [Coqui](https://huggingface.co/coqui/XTTS-v2). El audio personal de referencia no se incluye en el repositorio.
