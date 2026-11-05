# Fase 1 — Diseño del Agente de Biblioteca (UniPutumayo)

> Documento de diseño. No contiene código ejecutable; es la base que se valida antes de la Fase 2.

## 1. Arquitectura general

```
 Navegador (HTML/CSS/JS)
   │  texto ──────────────► POST /api/chat
   │  audio WAV 16k mono ─► POST /api/voz
   ▼
 FastAPI (app/main.py)
   ├─ stt.py      faster-whisper base, int8, CPU (cargado 1 vez)
   ├─ agente.py   gestor conversacional: estado + LLM qwen2.5:3b (tool calling)
   │     ├─ respaldo por palabras clave si el LLM no llama herramienta
   │     └─ herramientas.py ──► db.py (PostgreSQL transaccional)
   │                        └─► rag.py (embeddinggemma + pgvector)
   ├─ tts.py      Piper es_MX-claude-high (cargado 1 vez)
   └─ bitácora    tiempos por etapa → tabla bitacora_agente
   ▼
 Respuesta JSON { texto, audio_wav_base64, fuentes, tiempos }
```

Flujo de voz: audio → STT → agente/LLM → PostgreSQL + pgvector → respuesta → TTS → voz + texto.

## 2. Intenciones

| Intención | Herramienta | ¿Requiere identificación? | ¿Modifica datos? |
|---|---|---|---|
| `saludo` / `despedida` | — | No | No |
| `identificarse` ("mi código es 2021...") | (interna) validar usuario | — | No |
| `buscar_tema` ("libros sobre redes") | `buscar_semantico` | No | No |
| `buscar_titulo_autor` ("¿tienen Cálculo de Stewart?") | `buscar_exacto` | No | No |
| `disponibilidad` | `consultar_disponibilidad` | No | No |
| `recomendar` ("bibliografía para mi tesis de cacao") | `buscar_semantico` (top-5, agrupado) | No | No |
| `reservar` | `reservar` | **Sí** | **Sí** (confirmación) |
| `renovar` | `renovar_prestamo` | **Sí** | **Sí** (confirmación) |
| `mi_cuenta` (préstamos/multas) | `consultar_prestamos_y_multas` | **Sí** | No |
| `reglamento` / `citacion` / `faq` | `responder_con_documentos` | No | No |
| `fuera_de_dominio` | — (respuesta fija cordial) | No | No |

**Respaldo por palabras clave** (si qwen2.5 no llama herramienta): reglas ordenadas — `reserv` → reservar; `renov` → renovar; `multa|préstamo|debo` → mi_cuenta; `APA|IEEE|cit` → citación (RAG); `reglamento|horario|cuántos días|sanción` → RAG; comillas o "autor/de <Nombre>" → exacto; resto de "libro/tesis/sobre/tema" → semántico; nada → fuera de dominio.

## 3. Estados de la conversación (máquina de estados)

```
              ┌────────────┐  identificarse OK   ┌────────────────┐
  inicio ───► │  ANONIMO   │ ──────────────────► │ IDENTIFICADO   │
              └────────────┘                      └────────────────┘
               │ búsquedas, RAG                    │ búsquedas, RAG, mi_cuenta
               │ reservar/renovar ─► pide código   │ reservar/renovar
               ▼                                   ▼
        ESPERANDO_CODIGO ── código válido ──► ESPERANDO_CONFIRMACION
                                               { accion, params, expira 2 min }
                                                 │ "sí"  → ejecutar en TRANSACCIÓN → IDENTIFICADO
                                                 │ "no"  → cancelar          → IDENTIFICADO
                                                 │ otro  → se descarta la acción pendiente
```

- El estado se guarda en `conversaciones.estado` (JSONB: `usuario_id`, `accion_pendiente`).
- La acción pendiente la arma el **código**, no el LLM: el LLM solo propone la herramienta; la ejecución real exige el "sí" explícito del usuario.
- El `usuario_id` de las herramientas **siempre** sale del estado de la sesión, nunca del texto del LLM → nadie puede consultar datos de otro usuario.

## 4. Modelo de datos — PostgreSQL transaccional (esquema `public`)

```
usuarios(id PK, codigo UNIQUE, nombre, tipo['estudiante','docente'], programa, email, activo)
material(id PK, titulo, autor, anio, tipo['libro','tesis','articulo','recurso_digital'],
         tema, programa, editorial, isbn NULL, descripcion_corta, es_demo BOOL)
ejemplares(id PK, material_id FK, codigo_barras UNIQUE, estante,
           estado['disponible','prestado','reservado','mantenimiento'])
prestamos(id PK, ejemplar_id FK, usuario_id FK, fecha_prestamo, fecha_vencimiento,
          renovaciones INT CHECK (renovaciones <= 3), estado['activo','devuelto','vencido'])
devoluciones(id PK, prestamo_id FK UNIQUE, fecha_devolucion, dias_retraso)
multas(id PK, usuario_id FK, prestamo_id FK, valor NUMERIC, dias, estado['pendiente','pagada'], fecha)
reservas(id PK, usuario_id FK, material_id FK, ejemplar_id FK NULL, fecha_reserva,
         expira_en (= +48 h), estado['activa','cumplida','vencida','cancelada'])
conversaciones(id UUID PK, usuario_id FK NULL, canal['texto','voz'], estado JSONB, creada, actualizada)
mensajes(id PK, conversacion_id FK, rol['user','assistant','tool'], contenido, creado)
bitacora_agente(id PK, conversacion_id FK, entrada, es_voz, intencion, herramienta,
                fragmentos JSONB [{fragmento_id, fuente, seccion, similitud}],
                respuesta, error, t_stt_ms, t_embedding_ms, t_busqueda_ms,
                t_llm_ms, t_tts_ms, t_total_ms, creado)
```

**Reglas de negocio en código y BD** (constantes en `config.py`):
- Préstamo 8 días · máx. 3 renovaciones (`CHECK`) · multa $1.000/día · sin préstamo ni renovación con multas pendientes · reserva 48 h.
- `renovar_prestamo`: en una transacción con `SELECT ... FOR UPDATE` sobre el préstamo; valida dueño, renovaciones < 3, sin multas pendientes, sin reserva activa de **otro** usuario sobre ese material.
- `reservar`: transacción; si hay ejemplar disponible lo marca `reservado`, si no, reserva en cola sobre el material.

## 5. Conocimiento vectorial — esquema `conocimiento` (pgvector)

Separación física: esquema propio `conocimiento`, distinto de `public`.

```
conocimiento.documentos(id PK, titulo, tipo['reglamento','apa','ieee','faq','guia_bd',
                        'resumen_tesis','resena_libro'], fuente (archivo), material_id FK NULL,
                        hash_contenido UNIQUE, creado)
conocimiento.fragmentos(id PK, documento_id FK ON DELETE CASCADE, orden, seccion,
                        texto, embedding vector(768))
INDEX HNSW ON fragmentos USING hnsw (embedding vector_cosine_ops)
```

- `material_id` enlaza resúmenes/reseñas con el acervo → `buscar_semantico` devuelve el libro/tesis **y** su disponibilidad real desde `ejemplares`.
- Prefijos embeddinggemma: consulta `task: search result | query: {texto}`; documento `title: {titulo|none} | text: {texto}`.
- Ingesta idempotente: `hash_contenido` (SHA-256 del archivo); si cambió, se borran sus fragmentos y se reinsertan; si no, se omite.
- Fragmentación: ~500 caracteres, solapamiento ~80, respetando títulos de sección (`##`) para guardar `seccion`.

## 6. Demostración SQL vs pgvector

Misma consulta, p. ej. *"cómo proteger una red de una empresa"*:
- **SQL:** `WHERE titulo ILIKE '%cómo proteger una red de una empresa%' OR autor ILIKE ...` → 0 resultados (el texto literal no aparece). Variante por palabras sueltas para mostrar ruido.
- **pgvector:** `ORDER BY embedding <=> :q LIMIT 5` → encuentra "Seguridad en redes", "Firewalls y VPN", tesis de ciberseguridad, aunque no contengan esas palabras.
Se muestra en la pestaña de la interfaz y en `demo_sql_vs_vector.py`.

## 7. Prompt del sistema (resumen)

Cordial, breve, español; solo datos de herramientas; si no hay datos, decirlo; citar `documento › sección`; en voz máx. 3–4 frases sin símbolos ni URLs; pedir confirmación antes de reservar/renovar; nunca revelar datos de otros usuarios.

## 8. Rendimiento (12 GB RAM, sin GPU)

Whisper y Piper como singletons al arrancar · Ollama `num_ctx=4096`, `keep_alive="2m"` · top-5 fragmentos · historial al LLM limitado a los últimos 6 mensajes · modelo configurable por `.env` (`LLM_MODEL=qwen2.5:3b`, respaldo `qwen2.5:1.5b`) · cada etapa en `try/except` con mensaje claro y registro en bitácora.

## 9. Seguridad

- Rol de BD `agente_biblio` (no `postgres`) con permisos solo sobre `biblioteca_agente`.
- `.env` (no versionado) y `.env.example` sin contraseñas.
- Consultas siempre parametrizadas (psycopg), sin SQL concatenado.

## 10. Plan de construcción (orquestación)

| Fase | Constructor sugerido | Criterio de aceptación observable |
|---|---|---|
| 2 BD | Copilot CLI | `psql -f schema.sql/seed.sql` sin errores; 55 materiales, 8 usuarios, 1 multa pendiente, 1 reserva |
| 3 Conocimiento | Antigravity | `python ingestar.py` 2 veces → mismo número de fragmentos; consulta de prueba devuelve reglamento |
| 4 Backend | Copilot CLI | `POST /api/chat` resuelve 7 herramientas; bitácora con tiempos |
| 5 Voz | Antigravity | `/api/voz` con un WAV devuelve texto + audio |
| 6 Interfaz | Antigravity | chat, micrófono, Mi cuenta, SQL vs pgvector, Bitácora |
| 7 Evaluación | Copilot CLI | `evaluar.py` genera `reporte.md` con ≥20 texto + 5 audio |
| 8 Docs | Orquestador | README + guía de sustentación |

Cada entrega se verifica (ejecución real) y se califica 1–10; se aprueba con ≥ 9.5.
