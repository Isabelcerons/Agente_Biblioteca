"""Integra Edge y backend real con audio sintético conocido; no usa micrófono humano."""
import base64
import io
import json
import time
import wave
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

CARPETA = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8000"


def main():
    with httpx.Client(base_url=BASE, timeout=120) as cliente:
        salud = cliente.get("/api/salud").json()
        assert salud["ok"], salud
        catalogo = cliente.get("/api/catalogo").json()
        assert catalogo["estadisticas"]["materiales"] == catalogo["total"]
        audio = cliente.post("/api/tts", json={"texto": "Busco libros sobre seguridad de redes."})
        audio.raise_for_status()
        raw = base64.b64decode(audio.json()["audio_wav_base64"])
        with wave.open(io.BytesIO(raw), "rb") as wav:
            params = wav.getparams()
            frames = wav.readframes(wav.getnframes())
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setparams(params)
            wav.writeframes(frames + bytes(params.framerate * params.sampwidth * params.nchannels * 2))
        audio64 = base64.b64encode(buf.getvalue()).decode()
        # El endpoint temprano jamás devuelve el PIN de una conversación que lo espera.
        codigo = cliente.post("/api/chat", json={"texto": "mi código es 101"}).json()
        pin = cliente.post("/api/transcribir", data={"conversacion_id": codigo["conversacion_id"]}, files={"audio": ("voz.wav", raw, "audio/wav")}).json()
        assert pin["transcripcion"] == "[PIN oculto]" and pin["requiere_envio_seguro"]
    guion = """(() => {
      window.fases = []; window.momentos = {};
      const audio64 = AUDIO;
      navigator.mediaDevices.getUserMedia = async () => {
        const ctx = new AudioContext();
        await ctx.resume();
        const destino = ctx.createMediaStreamDestination();
        const bytes = Uint8Array.from(atob(audio64), c => c.charCodeAt(0));
        const buffer = await ctx.decodeAudioData(bytes.buffer);
        const source = ctx.createBufferSource(); source.buffer = buffer;
        source.connect(destino); source.start();
        const pista = destino.stream.getAudioTracks()[0];
        const stop = pista.stop.bind(pista);
        pista.stop = () => { stop(); try {source.stop();} catch {} ctx.close(); };
        return destino.stream;
      };
      new MutationObserver(() => {
        const fase = document.querySelector('.llamada')?.dataset.estado;
        if (fase && window.fases.at(-1) !== fase) window.fases.push(fase);
        for (const [nombre, selector] of [['transcripcion','.mensaje--usuario'], ['opciones','.lomo-chat']]) {
          if (!window.momentos[nombre] && document.querySelector(selector)) window.momentos[nombre] = performance.now();
        }
      }).observe(document, {subtree:true, childList:true, attributes:true, attributeFilter:['data-estado']});
    })();""".replace("AUDIO", json.dumps(audio64))
    errores = []
    solicitudes = []
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="msedge", headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        contexto = navegador.new_context(viewport={"width": 1440, "height": 1000})
        contexto.add_init_script(guion)
        pagina = contexto.new_page()
        pagina.set_default_timeout(120000)
        pagina.on("pageerror", lambda error: errores.append(str(error)))
        pagina.on("response", lambda r: solicitudes.append({"ruta": r.url.split(BASE)[-1], "status": r.status, "tiempo": time.monotonic()}) if "/api/" in r.url else None)
        pagina.goto(BASE)
        pagina.locator("#entrar-invitado").click()
        pagina.get_by_role("button", name="Iniciar llamada", exact=True).click()
        pagina.locator(".lomo-chat").first.wait_for()
        assert not pagina.locator(".chat-mensajes .aviso--error").count()
        assert pagina.locator(".mensaje--usuario").count() == 1
        pagina.wait_for_function('window.fases.includes("hablando") && document.querySelector(".llamada").dataset.estado === "escuchando"')
        pagina.get_by_role("button", name="Terminar llamada", exact=True).click()
        assert pagina.get_by_role("button", name="Iniciar llamada", exact=True).is_visible()
        datos = {"salud": salud, "catalogo": catalogo["estadisticas"], "fases": pagina.evaluate("window.fases"), "momentos": pagina.evaluate("window.momentos"), "solicitudes": solicitudes, "errores": errores, "pin_oculto": True}
        assert datos["momentos"]["transcripcion"] < datos["momentos"]["opciones"]
        assert any(r["ruta"] == "/api/transcribir" and r["status"] == 200 for r in solicitudes)
        assert any(r["ruta"] == "/api/tts" and r["status"] == 200 for r in solicitudes)
        assert not errores, errores
        pagina.screenshot(path=str(CARPETA / "integracion_llamada_real.png"), full_page=True)
        navegador.close()
    (CARPETA / "integracion_llamada_real.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASA: catálogo actualizado, PIN oculto, transcripción antes de opciones y llamada completa con STT/LLM/TTS reales; sin errores de consola.")


if __name__ == "__main__":
    main()
