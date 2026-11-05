r"""Edge real, micrófono sintético y endpoints locales controlados; no conversación humana.
Ejecutar: venv\Scripts\python.exe evaluacion\llamada_navegador.py
Requiere servidor compartido existente en localhost:8000 (no lo inicia ni reinicia).
"""
import base64
import io
import json
import math
import struct
import time
import wave
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
buf = io.BytesIO()
with wave.open(buf, "wb") as wav:
    wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
    wav.writeframes(b"".join(struct.pack("<h", int(1200 * math.sin(i * .15))) for i in range(16000)))
AUDIO = base64.b64encode(buf.getvalue()).decode()

HTML = '''<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/static/css/variables.css">
<link rel="stylesheet" href="/static/css/base.css">
<link rel="stylesheet" href="/static/css/componentes.css">
<link rel="stylesheet" href="/static/css/app.css">
<body><main id="chat"></main><script type="module">
import { montarChat } from '/static/js/chat.js';
window.chat = montarChat(document.querySelector('#chat'));
</script></body></html>'''

SIMULACION = r"""(() => {
  const Original = window.AudioContext;
  window.contextos = [];
  window.pistas = [];
  window.fases = [];
  window.apariciones = {};
  window.silencio = false;
  window.permisoDemorado = false;
  window.AudioContext = class extends Original {
    constructor(...args) { super(...args); window.contextos.push(this); }
  };
  navigator.mediaDevices.getUserMedia = async () => {
    const contexto = new window.AudioContext();
    const destino = contexto.createMediaStreamDestination();
    const oscilador = contexto.createOscillator();
    const gain = contexto.createGain();
    gain.gain.value = window.silencio ? 0 : .25;
    oscilador.connect(gain).connect(destino);
    oscilador.start();
    await contexto.resume();
    setTimeout(() => gain.gain.value = 0, 800);
    const pista = destino.stream.getAudioTracks()[0];
    window.pistas.push(pista);
    const detener = pista.stop.bind(pista);
    pista.stop = () => { detener(); oscilador.stop(); contexto.close(); };
    if (window.permisoDemorado) await new Promise(r => setTimeout(r, 800));
    return destino.stream;
  };
  new MutationObserver(() => {
    const estado = document.querySelector('.llamada')?.dataset.estado;
    if (estado && window.fases.at(-1) !== estado) window.fases.push(estado);
    for (const [nombre, selector] of [['transcripcion','.mensaje--usuario'],['tarjetas','.lomo-chat']]) {
      if (!window.apariciones[nombre] && document.querySelector(selector)) window.apariciones[nombre] = performance.now();
    }
  }).observe(document, {subtree:true, childList:true, attributes:true, attributeFilter:['data-estado']});
})();"""


def main():
    requests = []
    errors = []
    counters = {"chat": 0, "voz": 0}
    modo = {"transcribir": "normal"}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True,
                                    args=["--autoplay-policy=no-user-gesture-required"])
        context = browser.new_context(viewport={"width": 390, "height": 844})
        context.add_init_script(SIMULACION)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def route(r):
            path = r.request.url.split("8000", 1)[-1]
            if path == "/":
                r.fulfill(status=200, content_type="text/html", body=HTML)
                return
            if not path.startswith("/api/"):
                r.continue_()
                return
            requests.append({"ruta": path, "tiempo": time.monotonic(),
                             "datos": r.request.post_data if path == "/api/chat" else None})
            if path == "/api/transcribir":
                if modo["transcribir"] in ("fallback", "error"):
                    r.fulfill(status=404 if modo["transcribir"] == "fallback" else 503,
                              content_type="application/json", body='{"ok":false}')
                    return
                result = {"transcripcion": "Busco libros de redes", "t_stt_ms": 10}
            elif path == "/api/chat":
                counters["chat"] += 1
                time.sleep(.5)
                result = {"ok": True, "conversacion_id": "llamada-prueba", "respuesta": "Estas son las opciones",
                          "materiales": [{"material_id": 1, "tipo": "libro", "titulo": "Redes locales",
                                          "disponibles": 2, "total": 2, "autor": "Autora"}]}
                if counters["chat"] == 2:
                    result["esperando"] = "pin"
            elif path == "/api/tts":
                result = {"audio_wav_base64": AUDIO}
            elif path == "/api/voz":
                counters["voz"] += 1
                result = {"ok": True, "conversacion_id": "llamada-prueba", "transcripcion": "1234",
                          "entrada_oculta": True, "respuesta": "PIN recibido", "audio_wav_base64": AUDIO}
            else:
                result = {"ok": True}
            r.fulfill(status=200, content_type="application/json", body=json.dumps(result))

        page.route("http://127.0.0.1:8000/**", route)
        page.goto("http://127.0.0.1:8000/")
        start = page.get_by_role("button", name="Iniciar llamada", exact=True)
        start.wait_for()
        assert page.evaluate("pistas.length") == 0
        start.click()
        page.wait_for_function("document.querySelector('.llamada').dataset.estado === 'procesando'")
        page.wait_for_function("document.querySelector('.mensaje--usuario')?.textContent.includes('Busco libros')")
        page.wait_for_function("document.querySelector('.llamada').dataset.estado === 'hablando'")
        assert page.locator(".lomo-chat").count() == 1
        assert page.evaluate("apariciones.transcripcion < apariciones.tarjetas"), "Transcripción anterior a resultados"
        assert page.evaluate("pistas.every(p => p.readyState === 'ended')")
        page.screenshot(path=str(ROOT / "llamada_movil.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.wait_for_function("pistas.length >= 2")
        page.wait_for_function("document.querySelector('.llamada').dataset.estado === 'hablando'")
        page.wait_for_function("pistas.length >= 3")
        page.wait_for_function("document.querySelector('.chat-mensajes').textContent.includes('PIN recibido')")
        assert "1234" not in page.locator("body").inner_text()
        assert page.locator(".mensaje--usuario").count() == 3
        assert len([r for r in requests if r["ruta"] == "/api/transcribir"]) == 2
        assert counters["voz"] == 1
        page.get_by_role("button", name="Terminar llamada", exact=True).click()
        page.wait_for_timeout(500)
        assert page.evaluate("pistas.every(p => p.readyState === 'ended') && contextos.every(c => c.state === 'closed')")
        count = len(requests)
        page.wait_for_timeout(1400)
        assert len(requests) == count
        phases = page.evaluate("fases")
        assert ["escuchando", "procesando", "hablando"] == [f for f in phases if f != "conectando" and f != "reposo"][:3]
        assert phases.count("escuchando") >= 3
        # Navegar fuera del chat detiene recursos.
        start.click()
        page.wait_for_function("document.querySelector('.llamada').dataset.estado === 'escuchando'")
        page.evaluate("document.querySelector('#chat').hidden = true")
        page.wait_for_function("document.querySelector('.llamada').dataset.estado === 'reposo'")
        assert page.evaluate("pistas.every(p => p.readyState === 'ended')")
        page.evaluate("document.querySelector('#chat').hidden = false; window.permisoDemorado = true")
        start.click()
        page.get_by_role("button", name="Terminar llamada", exact=True).click()
        page.wait_for_timeout(1000)
        assert page.evaluate("pistas.every(p => p.readyState === 'ended')")
        # Silencio puro no se envía y termina con una indicación recuperable.
        page.evaluate("window.permisoDemorado = false; window.silencio = true")
        before = len(requests)
        start.click()
        page.wait_for_function("document.querySelector('.llamada').dataset.estado === 'reposo'", timeout=24000)
        assert "No se detectó voz" in page.locator(".llamada__estado").inner_text()
        assert len(requests) == before
        assert page.evaluate("pistas.every(p => p.readyState === 'ended') && contextos.every(c => c.state === 'closed')")
        # Micrófono manual conserva envío por gesto y transcripción temprana.
        page.evaluate("window.silencio = false; window.chat.limpiar()")
        page.get_by_role("button", name="Grabar pregunta por voz", exact=True).click()
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Detener y enviar", exact=True).click()
        page.wait_for_function("document.querySelector('.lomo-chat') && document.querySelector('.orbita-voz')")
        assert page.locator(".mensaje--usuario").count() == 1
        page.evaluate("window.chat.limpiar()")
        # Servidor sin endpoint temprano conserva /api/voz.
        modo["transcribir"] = "fallback"
        before_voz = counters["voz"]
        start.click()
        page.wait_for_function("document.querySelector('.chat-mensajes').textContent.includes('PIN recibido')")
        assert counters["voz"] == before_voz + 1
        page.get_by_role("button", name="Terminar llamada", exact=True).click()
        page.evaluate("window.chat.limpiar()")
        modo["transcribir"] = "error"
        start.click()
        page.wait_for_function("document.querySelector('.llamada').dataset.estado === 'reposo' && document.querySelector('.llamada__estado').textContent.includes('No pudimos')")
        assert page.locator("#entrada-chat").is_enabled()
        assert page.evaluate("pistas.every(p => p.readyState === 'ended') && contextos.every(c => c.state === 'closed')")
        # Ocultar la página o expirar la sesión también finaliza la llamada.
        modo["transcribir"] = "normal"
        for evento in ("pagehide", "biblioteca-sesion-expirada"):
            start.click()
            page.wait_for_function("document.querySelector('.llamada').dataset.estado === 'escuchando'")
            page.evaluate("evento => window.dispatchEvent(new Event(evento))", evento)
            page.wait_for_function("document.querySelector('.llamada').dataset.estado === 'reposo'")
            assert page.evaluate("pistas.every(p => p.readyState === 'ended')")
        assert not errors, errors
        # Comprobar además el encaje en la aplicación existente, sin enviar audio real.
        app = context.new_page()
        app.goto("http://127.0.0.1:8000/")
        app.locator("#entrar-invitado").click()
        app.get_by_role("button", name="Iniciar llamada", exact=True).click()
        app.wait_for_function("document.querySelector('.llamada').dataset.estado === 'escuchando'")
        assert app.evaluate("document.documentElement.scrollWidth <= innerWidth")
        app.screenshot(path=str(ROOT / "llamada_aplicacion_movil.png"), full_page=True)
        app.get_by_role("button", name="Terminar llamada", exact=True).click()
        assert app.evaluate("pistas.every(p => p.readyState === 'ended')")
        app.close()
        report = {"navegador": "Edge headless Windows", "microfono": "AudioContext sintético",
                  "fases": phases, "solicitudes": requests, "errores": errors,
                  "comprobaciones": ["sin captura inicial", "transcripción antes de respuesta", "tarjetas",
                    "escuchar/procesar/hablar/escuchar", "PIN sin DOM", "sin duplicados",
                    "sin captura durante TTS", "limpieza al terminar/navegar/permiso tardío", "silencio sin envío", "390px",
                    "micrófono manual", "fallback /api/voz", "error recuperable", "pagehide y sesión expirada",
                    "encaje en aplicación real a 390px"],
                  "aparicion_ui_ms": page.evaluate("apariciones")}
        (ROOT / "llamada_resultados.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        browser.close()


if __name__ == "__main__":
    main()
