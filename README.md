# Agente de biblioteca y repositorio académico — UniPutumayo

Agente conversacional multimodal (texto y voz) para el taller *Diseño de agentes conversacionales con PostgreSQL, pgvector, embeddinggemma, STT y TTS*.
Todo corre en local y en CPU: Ollama (`qwen2.5:3b`), embeddinggemma (768 dimensiones), faster-whisper (`base`, int8), Piper (`es_MX-claude-high`, configurable), FastAPI y PostgreSQL 17 + pgvector.

## Puesta en marcha

### Voz y modo llamada

En **Voz del agente** puedes seleccionar Claude o Ald (es-MX), o las voces femenina y masculina Sharvard (es-ES), y escuchar una muestra. Las voces Piper funcionan localmente. Para activar la voz personalizada, coloca un audio autorizado en `voz que quiero/` y ejecuta `instalar_voz_personalizada.bat`; XTTS-v2 se descarga al probarla por primera vez, se procesa localmente y su licencia solo permite uso no comercial. El audio de referencia no se incluye en Git. Las voces son perfiles sintéticos propios; no son copias de Alexa ni Siri.

En una instalación nueva, descarga las voces extra con `venv\Scripts\python -m piper.download_voices es_MX-ald-medium --data-dir voces` y `venv\Scripts\python -m piper.download_voices es_ES-sharvard-medium --data-dir voces`.

El micrófono manual muestra la transcripción antes de buscar y presenta las opciones antes de generar el audio. En el chat, **Iniciar llamada** permite seguir conversando sin pulsar el micrófono en cada turno: al hacer una pausa se envía la consulta, se muestran los resultados y, al terminar de hablar el agente, vuelve a escuchar. **Terminar llamada**, salir del chat u ocultar la página detiene la captura. Se solicita permiso de micrófono únicamente al iniciar; el audio se procesa localmente.

La voz seleccionada es Claude high de Piper, con velocidad moderada (`PIPER_LENGTH_SCALE=0.92`). El PIN conserva su ruta protegida y nunca se muestra en la transcripción. Véanse `docs/voz_calidad.md` y `evaluacion/llamada_informe.md` para las pruebas y límites. La integración real con audio sintético y Edge se comprueba con `python evaluacion/integracion_llamada_real.py`; la conversación humana y el ruido de cada micrófono deben probarse en el equipo de uso.

Requiere Python 3.13, PostgreSQL 17 con pgvector, Ollama y los modelos de voz locales.

1. Crea el entorno con `python -m venv venv` e instala `venv\Scripts\python -m pip install -r requirements.txt`.
2. Copia `.env.example` a `.env` y configura las credenciales locales.
3. En una instalación nueva, ejecuta `sql/00_crear_bd.sql`, `sql/schema.sql` y `sql/seed.sql`. Aplica después las migraciones `sql/migracion_01.sql`, `sql/migracion_02.sql` y `sql/migracion_03.sql` en orden. En una instalación existente conserva sus datos y aplica las migraciones pendientes.
4. Descarga en Ollama `qwen2.5:3b`, `qwen2.5:1.5b` y `embeddinggemma`; configura `PIPER_VOZ` con un modelo disponible en `voces/`.
5. Con el entorno activado, ejecuta `python asignar_pines_demo.py`, `python ingestar.py` y `python verificar_entorno.py`.
6. Inicia `iniciar.bat` y abre http://127.0.0.1:8000.

La interfaz llama a FastAPI. El agente selecciona herramientas con Qwen y reglas de respaldo; SQL resuelve disponibilidad y trámites, mientras pgvector recupera documentos y materiales por significado. Whisper transcribe la entrada y Piper sintetiza la respuesta. Los PIN se verifican con PBKDF2 y las operaciones de préstamo y reserva usan transacciones.

El reconocimiento de voz puede confundir nombres y números, especialmente con ruido o voces sintéticas. Repite el código si no lo entiende o utiliza el formulario. Para las muestras de login de evaluación se usa `es_MX-claude-high`; se conservan las muestras originales de la voz rápida en `evaluacion/audios/respaldo_login_ald/`. La configuración de voz de la aplicación sigue siendo independiente. Los PDF escaneados necesitan OCR externo; el repositorio solo procesa texto seleccionable.
> Los datos de usuarios, tesis y préstamos son **datos de demostración**.

---

## Mapa del conocimiento

Vista que dibuja el acervo como un mapa: **cada punto es un libro o tesis; los que hablan de temas parecidos quedan cerca. Así funciona pgvector.**

**Cómo se construye**
1. Para cada material se promedian los embeddings (768 dimensiones) de sus fragmentos de resumen o reseña guardados en `conocimiento.fragmentos`, y se normaliza el promedio.
2. Se reduce a 2D con **PCA** usando solo numpy (centrado + SVD). No se usan librerías pesadas.
3. Las coordenadas se guardan en `conocimiento.mapa_materiales`, y la proyección (media y dos componentes) en `conocimiento.mapa_pca`, para no recalcular en cada visita.
4. `python calcular_mapa.py` recalcula solo si cambió el conocimiento (compara una firma de los documentos). `--forzar` obliga a recalcular. `ingestar.py` lo llama automáticamente al final.

**Cómo se usa**
- Página: `http://127.0.0.1:8000/static/mapa.html`. En la interfaz rediseñada aparece como una vista del menú.
- Los colores indican el programa académico; las tesis tienen otra forma para no depender solo del color.
- Al pasar el mouse aparecen el título, el autor y la disponibilidad. Al hacer clic se abre la ficha del material.
- Al buscar, la consulta se proyecta en el mismo plano como una **estrella**, con líneas hacia los materiales más cercanos.

**Endpoints**
| Método | Ruta | Respuesta |
|---|---|---|
| GET | `/api/mapa` | puntos (`material_id`, título, autor, programa, x, y, disponibilidad), límites y varianza explicada |
| GET | `/api/mapa/proyectar?q=...&k=5` | posición `x, y` de la consulta y los `k` materiales más cercanos con su similitud |

**Limitación importante:** el plano 2D conserva solo una parte de la información de los 768 números de cada embedding; la vista muestra ese porcentaje. Por eso los "más cercanos" **se calculan en las 768 dimensiones** (distancia coseno, como pgvector) y no en el dibujo. Dos puntos que se ven cerca en 2D pueden no ser los más parecidos de verdad.

---

## Bibliografía en APA o IEEE

Herramienta del agente `generar_bibliografia(tema, cantidad, norma)`:
- `norma`: `"APA"` (por defecto) o `"IEEE"`; `cantidad`: de 1 a 15 (por defecto 5).
- Busca los materiales más relevantes con **pgvector** y arma cada referencia **solo con los datos de la tabla `material`**: autor, año, título y editorial. Sigue los formatos de `conocimiento/guia_apa7.md` y `conocimiento/guia_ieee.md`.
- **Nunca inventa datos:** si falta uno, se omite. En APA, un año ausente se escribe "(s. f.)", que es la convención de la norma. Tampoco agrega DOI, URL, ciudad ni páginas.
- La lista sale **ordenada alfabéticamente** por el primer apellido. En IEEE las referencias se numeran en ese orden; en un documento real, IEEE numera por orden de aparición en el texto.
- En la interfaz, el botón **Copiar** copia la lista con las cursivas.
- **Por voz** solo se dice cuántas referencias encontró y los títulos.

**Ejemplos**
- "Genera una bibliografía en APA sobre seguridad de redes"
- "Dame 3 referencias IEEE sobre agroforestería"
- "¿Cómo cito un libro en APA?" → **no** genera bibliografía; explica la norma con la guía indexada.

---

## Cancelar una reserva

### Recogida y avisos de disponibilidad

Preguntas como «¿Cuándo puedo recoger “Plan de negocios”?» consultan únicamente las reservas de la sesión. Si hay una copia apartada, indican el plazo de recogida y que se debe llevar el carné al mostrador durante el horario de atención. Si sigue en espera, lo explican sin prometer una fecha.

Al consultar Mis reservas o los avisos, se asignan las copias libres a las solicitudes vigentes por orden de llegada. Desde la asignación hay 48 horas para recogerlas. El chat muestra **Ya puedes recoger**, y Mis reservas distingue **Lista para recoger** de **En cola**. La aplicación comprueba los avisos al entrar, al volver a la ventana y cada 30 segundos mientras está abierta; no envía correos ni notificaciones fuera de ella.

Prueba: `python evaluacion/probar_recogida_avisos.py`. No se agregó historial de conversaciones.

Las reservas apartan **ejemplares**, no el título completo. Dos cuentas pueden reservar el mismo libro si quedan copias distintas. Antes de confirmar se informa cuántas quedan; si no hay ninguna libre, se aclara que la solicitud quedará en espera. El agente muestra el vencimiento del próximo apartado y la próxima devolución prevista cuando existen. Son fechas orientativas: retirar un apartado o devolver tarde puede cambiar la disponibilidad. No se muestran datos de la otra cuenta.

Prueba de estos casos: `python evaluacion/probar_reservas_ejemplares.py` (revierte todos los datos que prepara).

Herramienta del agente `cancelar_reserva(usuario_id, reserva_id)`:
- Solo para el **usuario identificado** y **sobre sus propias reservas activas**. Si la reserva no es suya, el agente responde que no la encuentra a su nombre, sin revelar nada más.
- Ejemplos: "cancela mi reserva de Ecología", "ya no necesito la reserva de Hacking ético".
- El LLM nunca recibe el `usuario_id` ni el `reserva_id`. El agente busca la reserva entre las activas del usuario por el título. Si tiene una sola, usa esa; si hay varias y el título no aclara cuál, pregunta.
- **Pide confirmación** ("¿Confirmo la cancelación de su reserva de «X»?"). Con el "sí", en una sola **transacción**:
  1. Bloquea la reserva (`FOR UPDATE`).
  2. Cambia su estado a `cancelada`.
  3. Si tenía un ejemplar apartado, lo devuelve a `disponible`.
- Disponible por *tool calling* y también con el **respaldo por palabras clave** (cancela, anula, quita o elimina + reserva). Estas palabras se revisan antes de la regla de "reservar".

## Avisos al identificarse

Cuando el usuario da su código, además del saludo, el agente resume en **una frase** lo importante de su cuenta:
- préstamos **vencidos** (con los días de retraso);
- **multas** pendientes (con el total);
- préstamos que **vencen en los próximos 2 días** ("vence hoy", "vence mañana");
- **reservas** que expiran en menos de 24 horas.

Ejemplo con el usuario de demostración `102`:
> Gracias, Mariana Rosero Burbano. Ya puede hacer sus trámites. Tenga en cuenta: «Fundamentos de seguridad en redes» está vencido hace 5 días y tiene una multa pendiente de $5.000.

Si no tiene nada pendiente, solo saluda. La misma frase llega por voz, sin símbolos ("cinco mil pesos").

---

## Evaluación

```
python evaluacion/evaluar.py              # todos los casos (texto, audio, bibliografía y mapa)
python evaluacion/evaluar.py --sin-audio  # sin los .wav
python evaluacion/evaluar.py --solo TXT   # solo una familia de casos
```

- Ejecuta los casos de `evaluacion/casos_prueba.json` y los audios de `evaluacion/audios/`. Cubre búsqueda semántica y exacta, reglamento, citación, reservas, renovaciones con y sin multa, cancelación de reservas, avisos, fuera de dominio, privacidad, bibliografía y mapa.
- Genera `evaluacion/reporte.md` y `evaluacion/resultados.json` con:
  - aciertos de **intención** y de **herramienta**;
  - **precisión de recuperación top-3**;
  - **tiempos promedio por etapa** (STT, embeddings, búsqueda, LLM, TTS, total);
  - la **lista de fallos** con lo esperado y lo obtenido.
- **No ensucia la base:** antes de empezar guarda préstamos, reservas, ejemplares, multas y devoluciones, y al terminar los restaura, aunque la evaluación falle a mitad. Algunos casos preparan su situación (por ejemplo, un préstamo que vence mañana), y también se deshace.

---

## Casos de prueba de estas funciones

Están en `evaluacion/casos_prueba.json`:
- `BIB-01` a `BIB-06`: APA e IEEE, solo datos de la tabla, orden alfabético, tema sin material, salida por voz, y el caso de control de "cómo cito".
- `MAPA-01` a `MAPA-04`: 55 puntos, proyección de consultas, vecinos relevantes, y que no se recalcule si nada cambió.

## Inicio de sesión por texto y voz

El código de usuario acepta entre 3 y 10 dígitos. Los usuarios de demostración usan el PIN `1234`:

| Código | Nombre | Escenario |
|---|---|---|
| 101 | Carlos Eduardo Córdoba Díaz | Sin problemas |
| 102 | Mariana Rosero Burbano | Préstamo vencido y multa de $5.000 |
| 103 | Valentina Cárdenas Rojas | Tres renovaciones |
| 104 | Juan Sebastián Muñoz Pantoja | Préstamo con reserva ajena |
| 105 | Andrés Felipe Jojoa Gómez | Puede renovar Ingeniería de software |
| 106 | Laura Camila Insuasty Díaz | Cuenta de demostración |
| 107 | Diego Alejandro Chicunque Muñoz | Cuenta de demostración |
| 108 | Paola Andrea Zambrano Erazo | Reserva activa de Redes de computadoras |

Como invitado, escribe o di «mi código es ciento uno» y después «uno dos tres cuatro». También acepta `mi código es 101` y el PIN en cifras, «mil doscientos treinta y cuatro» o «doce treinta y cuatro». Si pediste una reserva antes de identificarte, el agente la retoma y pide confirmación.

El PIN queda como `[PIN oculto]` en historial, bitácora y transcripción de voz. El campo del chat lo enmascara. La sesión usa una cookie HttpOnly con SameSite=Lax y dura dos horas. Tras cinco intentos fallidos, la cuenta se bloquea durante cinco minutos.

Para actualizar una instalación anterior, aplica `sql/migracion_03.sql`: conserva usuarios, PIN, préstamos, multas y reservas. `python -m app.numeros` comprueba los números dictados; `python generar_audios_login.py --voz voces/es_MX-claude-high.onnx` prepara los cuatro audios de login sin sobrescribir los existentes.

El menú principal contiene Chat, Catálogo, Mi cuenta y Mis reservas. Mapa, SQL vs pgvector y Bitácora están en **Panel técnico**.

El **Catálogo** se puede consultar como invitado. Muestra todos los libros y tesis, sus ejemplares disponibles, reservados y prestados, y los totales globales de títulos, libros, tesis y ejemplares. Permite buscar por título, autor o tema, combinar filtros por tipo, programa y disponibilidad, y recorrer páginas de 12 materiales. Cada ficha incluye resumen, datos bibliográficos y ubicación, con acciones para consultar al agente, abrir el mapa o iniciar una reserva en el chat; reservar requiere identificarse.

Para verificar solo el catálogo: `venv/Scripts/python.exe evaluacion/verificar_catalogo.py`. La prueba usa TestClient sin lifespan para comprobar la API actual y Edge para la interfaz; no crea ni cancela reservas. Por defecto consulta el servidor en 8000; para un servidor aislado iniciado con `venv/Scripts/python.exe -m uvicorn app.main:app --port 8001 --lifespan off`, establece `$env:CATALOGO_URL='http://127.0.0.1:8001'` en PowerShell. Guarda capturas de escritorio y móvil en ambos temas, y `evaluacion/catalogo_resultados.json`.

Para repetir la revisión de interfaz con Edge instalado: `python -m pip install playwright` y `python evaluacion/verificar_interfaz.py`, con la API iniciada. Guarda capturas y `evaluacion/interfaz_resultados.json`; restaura las reservas y sesiones que utiliza.
