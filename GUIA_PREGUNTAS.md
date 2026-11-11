# Guía de preguntas y casos para la sustentación (Datos de demostración)

Esta guía reúne todas las preguntas y pruebas organizadas por subsistema, listas para copiar y pegar durante la sustentación del proyecto **Agente de biblioteca y repositorio académico — UniPutumayo** (Institución Universitaria del Putumayo).

> [!TIP]
> **Preparación inicial para la sustentación**:
> Antes de comenzar la presentación o demostración ante jurados, ejecuta en la terminal:
> ```powershell
> python refrescar_demo.py
> ```
> Esto sincronizará todos los escenarios operativos de los usuarios demo (101 a 108) con la fecha actual del sistema (`now()`), asegurando que las fechas de vencimiento, multas acumuladas y reservas vigentes coincidan exactamente con lo planeado. Para revisar el estado sin alterar la base de datos, usa `python refrescar_demo.py --solo-mostrar`.

---

## 1. Usuarios de prueba (PIN general: `1234`)

Para identificarte por chat de texto o por voz, di o escribe: `mi código es ...` y luego ingresa o di el PIN `1234`.

| Código | Nombre completo | Rol / Programa | Situación particular para pruebas |
|:---:|---|---|---|
| **101** | Carlos Eduardo Córdoba Díaz | Docente · Administración de Empresas | Sin problemas: cuenta limpia, ideal para reservar títulos o demostrar préstamos exitosos. |
| **102** | Mariana Rosero Burbano | Estudiante · Ingeniería Agroforestal | Multa pendiente de $5.000 y préstamo vencido: **NO** puede renovar. |
| **103** | Valentina Cárdenas Rojas | Estudiante · Ingeniería de Sistemas | Préstamo de «Cálculo de una variable» con 3 renovaciones alcanzadas: **NO** puede renovar más. |
| **104** | Juan Sebastián Muñoz Pantoja | Estudiante · Ingeniería de Sistemas | Tiene «Redes de computadoras», pero otra persona (108) lo reservó: **NO** puede renovar. |
| **105** | Andrés Felipe Jojoa Gómez | Estudiante · Administración de Empresas | Préstamo activo de «Ingeniería de software» (0 renovaciones): **SÍ** puede renovar (+8 días). |
| **106** | Laura Camila Insuasty Díaz | Estudiante · Contaduría Pública | Préstamo activo regular de «Fundamentos de bases de datos». Cuenta limpia. |
| **107** | Diego Alejandro Chicunque Muñoz | Estudiante · Ingeniería Ambiental | Ya devolvió su material y pagó multa previa. Cuenta al día. |
| **108** | Paola Andrea Zambrano Erazo | Docente · Ingeniería de Sistemas | Tiene una reserva activa de «Redes de computadoras» lista para recoger en mostrador. |

---

## 2. Búsqueda por tema (pgvector y embeddinggemma)

Preguntas temáticas en lenguaje natural que evalúan la recuperación semántica conceptual (768 dimensiones):

- `¿Tienen libros sobre cómo proteger una red?` *(recupera: Stallings, Firewalls y VPN, Hacking ético)*
- `Necesito algo del medio ambiente` *(recupera: Ecología de Odum, Ciencias ambientales, Begon)*
- `Quiero aprender a programar desde cero` *(recupera: Fundamentos de programación de Joyanes, Java de Deitel)*
- `Libros para hacer mi tesis` *(recupera: Metodología de la investigación de Hernández Sampieri)*
- `¿Qué hay sobre cultivos de cacao en el Putumayo?` *(recupera: tesis de cacao en piedemonte, monitoreo IoT, comercialización)*
- `Algo sobre suelos` *(recupera: El suelo de Brady, Edafología de Porta, Conservación de suelos)*
- `Libros de marketing y ventas` *(recupera: Dirección de marketing y Fundamentos de marketing de Kotler)*
- `¿Hay tesis sobre turismo?` *(recupera: tesis sobre ecoturismo en Sibundoy y corredor Mocoa-Sibundoy)*

---

## 3. Búsqueda exacta (título o autor con SQL)

Consultas para verificar el despachador de búsqueda literal (`ILIKE`):

- `¿Tienen Redes de computadoras de Tanenbaum?`
- `Busca libros de Kotler`
- `¿Está disponible Inteligencia artificial de Russell y Norvig?`
- `¿Tienen el libro de Joyanes Aguilar?`
- `¿Hay ejemplares de Cálculo de Stewart?`

---

## 4. De qué trata un material (resumen y contenido)

Consultas para evaluar la síntesis extractiva de libros y tesis:

- `¿De qué trata la tesis del sacha inchi?`
- `Resúmeme la tesis de calidad del agua en Orito`
- `¿De qué trata Ingeniería de software de Sommerville?`
- `¿De qué trata la tesis de monitoreo de cacao con IoT?`
- `Explícame de qué habla el libro de Hacking ético`

---

## 5. Reglamento y políticas de biblioteca (RAG normativo)

Preguntas institucionales sobre préstamos, horarios, deberes y sanciones:

- `¿Cuántos días me prestan un libro?` *(Respuesta esperada: 8 días)*
- `¿Cuántas veces puedo renovar?` *(Respuesta esperada: máximo 3 veces)*
- `¿Cuánto es la multa por día de retraso?` *(Respuesta esperada: $1.000 por día)*
- `¿Cuánto tiempo me guardan una reserva?` *(Respuesta esperada: 48 horas tras asignarse)*
- `¿Puedo prestar mi carné a otra persona?` *(Respuesta esperada: No, es personal e intransferible)*
- `¿Cuál es el horario de atención de la biblioteca?`
- `¿Qué sanciones tengo si pierdo un libro?`

---

## 6. Citación y bibliografía (normas APA 7 e IEEE)

Consultas normativas y herramientas generadoras de referencias:

- `¿Cómo cito un libro en APA?` *(Explica la estructura de citación según la guía indexada)*
- `¿Cómo cito una tesis en APA 7?`
- `¿Cuál es la diferencia entre APA e IEEE?`
- `¿Qué bases de datos académicas puedo usar en la universidad?`
- `Genera una bibliografía en APA sobre seguridad de redes` *(Invoca `generar_bibliografia` y entrega referencias ordenadas alfabéticamente)*
- `Dame 3 referencias IEEE sobre agroforestería` *(Invoca `generar_bibliografia` con norma IEEE)*

---

## 7. Trámites y autoservicio (requieren sesión activa)

Pruebas de la máquina de estados, control de identidad y transacciones:

- `¿Tengo multas?`  
  *(Con usuario 102 informa: $5.000 pendiente por entrega tardía).*
- `¿Qué libros tengo prestados?`  
  *(Con usuario 103, 104, 105 o 106 detalla fechas de vencimiento formateadas).*
- `Renueva mi préstamo`  
  - Con **105**: Procede a la renovación (+8 días adicionales).
  - Con **102**: Lo rechaza por multa pendiente de $5.000.
  - Con **103**: Lo rechaza por superar el límite de 3 renovaciones.
  - Con **104**: Lo rechaza porque otra persona (108) reservó ese material.
- `Resérvame Ecología de Odum`  
  *(Con usuario 101 pide confirmación explícita; responder `sí` para ejecutar).*
- `Cancela mi reserva de Ecología`  
  *(Con usuario 101 pide confirmación y luego cancela la reserva en transacción atómica `SELECT FOR UPDATE`).*
- `¿Cuándo puedo recoger mi reserva de Redes de computadoras?`  
  *(Con usuario 108 informa que el ejemplar ya está apartado en mostrador y tiene 48 horas).*

---

## 8. Casos fuera de dominio (límites éticos y alcance)

Preguntas para verificar que el agente reconozca sus fronteras y no alucine:

- `¿Cómo va a estar el clima mañana en Mocoa?`
- `Recomiéndame una película para el fin de semana`
- `¿Quién ganó el último partido de fútbol?`
- `Escribe una receta para hacer pan`

---

## 9. Pruebas del Asistente de investigación (`#investigacion`)

El Asistente de investigación (`POST /api/investigacion`) realiza búsquedas semánticas profundas sobre libros, reseñas y tesis completas, organizando la evidencia en extractos literales, citas normalizadas `[material ID]`, subtemas del acervo y bibliografía APA 7 copiable.

Para probarlo en la interfaz:
1. Haz clic en **Investigar** en la barra superior o navega a `#investigacion`.
2. Copia y pega cualquiera de los siguientes temas:

### Ejemplos listos para copiar y pegar:

#### Caso 1: Seguridad informática (con filtro de programa)
- **Tema:** `Sistemas de detección de intrusos y protección perimetral en redes empresariales`
- **Programa (selector):** `Ingeniería de Sistemas`
- **Resultado observable:** Recupera fragmentos de libros de Stallings, Forouzan o Cheswick; genera citas `[material X]`, detecta subtemas como *Seguridad informática* o *Redes* y lista las referencias APA exactas.

#### Caso 2: Agroforestería y suelos amazónicos (con filtro de programa)
- **Tema:** `Recuperación de suelos degradados y sistemas agroforestales en la Amazonía`
- **Programa (selector):** `Ingeniería Agroforestal`
- **Resultado observable:** Localiza libros de edafología (Brady) y tesis de agroforestería de la región del Putumayo con sus citas y fragmentos literales de texto.

#### Caso 3: Cadenas de valor y negocios locales (con filtro de programa)
- **Tema:** `Planes de negocio y comercialización de productos agrícolas amazónicos`
- **Programa (selector):** `Administración de Empresas`
- **Resultado observable:** Conecta tesis de comercialización de cacao o sacha inchi con libros de administración y marketing de Kotler.

#### Caso 4: Metodología de investigación (sin filtro de programa)
- **Tema:** `Metodología de la investigación cuantitativa, recolección de datos y diseño muestral`
- **Programa:** *(Dejar en blanco / Todos)*
- **Resultado observable:** Evidencia transversal de libros de Hernández Sampieri y textos de investigación aplicada.

#### Caso 5: Tecnologías emergentes y monitoreo ambiental
- **Tema:** `Aplicación de internet de las cosas y sensores para el monitoreo agrícola`
- **Programa:** `Ingeniería de Sistemas`
- **Resultado observable:** Recupera tesis de prototipos IoT aplicados al cultivo de cacao en Putumayo.

---

## 10. Selector de voces y audio multimodal

En la barra lateral izquierda, el agente permite configurar y probar el motor de voz en tiempo real:

1. **Voces locales Piper**:
   - `Claude · México` (`es_MX-claude-high`): Voz neuronal clara y fluida (predeterminada).
   - `Ald · México` (`es_MX-ald-medium`): Voz masculina rápida y ligera para CPU.
   - `Sharvard · Femenina` (`es_ES-sharvard-medium`, voz 1): Locución en español de España femenina.
   - `Sharvard · Masculina` (`es_ES-sharvard-medium`, voz 0): Locución en español de España masculina.
2. **Voz personalizada XTTS-v2**:
   - Opción para clonación local a partir de muestra autorizada en la carpeta `voz que quiero/` (requiere aceptar explícitamente su licencia comunitaria CPML para fines no comerciales).
3. **Prueba de voz en un clic**:
   - Selecciona cualquier voz y haz clic en **Escuchar prueba**.
   - El sistema genera un audio de demostración sin necesidad de enviar mensajes en el chat.
4. **Lectura automática y verificación de voz**:
   - Activa el interruptor **Leer respuestas en voz alta** para que todas las respuestas de texto del chat se sinteticen automáticamente en audio.
   - En cada respuesta, el backend confirma la voz efectiva en `voz_usada`; si la voz solicitada no estuviese disponible, genera un `aviso` y recurre de manera segura a la voz estándar.

---

## 11. Salas de la biblioteca (Navegación temática y bibliotecarios)

El agente permite recorrer las 5 salas especializadas de la biblioteca, cada una atendida por su propio bibliotecario/a con su saludo y acervo delimitado por programa:

### Preguntas para elegir y cambiar de sala:
- `¿Qué salas hay?`  
  *(El agente despliega las 5 salas como opciones interactivas dentro de la burbuja).*
- `Quiero la sala de ingeniería`  
  *(Activa la sala de Ingeniería de Sistemas; saluda Andrés: «Bienvenido a la Sala de Ingeniería. Aquí están los libros de programación, redes, bases de datos e inteligencia artificial. ¿Qué buscas?»).*
- `Llévame a la de contabilidad`  
  *(Activa la sala de Contaduría Pública; saluda Lucía: «Bienvenida a la Sala de Contaduría. Aquí están los materiales de costos, finanzas y contabilidad. ¿Qué buscas?»).*
- `Quiero ir a la sala de agrarias`  
  *(Activa la sala de Ciencias Agrarias y Ambientales; saluda Rosa: «Bienvenida a la Sala Agroambiental. Aquí están los materiales sobre suelo, cultivos, ecología y sostenibilidad. ¿Qué buscas?»).*
- `Cámbiame a administración`  
  *(Activa la sala de Administración y Negocios; saluda Camilo: «Bienvenido a la Sala de Administración. Aquí están los libros de gestión, marketing y negocios. ¿Qué buscas?»).*
- `Toda la biblioteca`  
  *(Quita el filtro de sala y regresa al comportamiento del catálogo general unificado).*

### Búsqueda con delimitación por sala:
- Estando en la Sala de Ingeniería:  
  `¿Tienen libros de redes?`  
  *(Solo recupera libros y tesis de Ingeniería de Sistemas: Tanenbaum, Stallings, Firewalls, Hacking ético).*
- Estando en la Sala de Ciencias Agrarias y Ambientales:  
  `¿Qué hay sobre cultivos de cacao?`  
  *(Solo recupera tesis y libros de Ingeniería Agroforestal y Ambiental).*

### Sugerencia inteligente de otra sala:
- Estando en la Sala de Contaduría (`contaduria`), escribe o di:  
  `Libros sobre redes de computadoras`  
  *(Como en contaduría no hay redes pero sí en ingeniería, el agente responde: «En esta sala no tengo material sobre eso, pero en la Sala de Ingeniería y Tecnología hay 4 resultados. ¿Quieres que te lleve?» y ofrece la opción interactiva).*

### Consulta transversal (no se limita por sala):
- Estando en cualquier sala (ej. `ingenieria` o `agro-ambiental`):  
  `¿Cuántos días me prestan un libro?`  
  *(El agente responde normalmente 8 días con el reglamento, demostrando que las políticas normativas no se limitan por sala).*

---

## 12. Identificación por voz y avisos proactivos

El sistema cuenta con una pantalla de inicio de sesión con escena animada de estantería de biblioteca y orbe interactivo (la cual también acompaña la bienvenida del chat). Admite tanto el formulario gráfico como el dictado oral de credenciales en cifras o en palabras mediante `app/numeros.py` dentro del chat:

- **Inicio de sesión limpio (Usuario 101):**
  - Turno 1: `mi código es ciento uno` *(o `soy el 101`)*
  - Turno 2: `uno dos tres cuatro` *(o `doce treinta y cuatro`, `1234`)*
  - Observación: Saludo de bienvenida confirmando cuenta sin novedades:  
    > *"Bienvenido Carlos Eduardo Córdoba Díaz. Su cuenta está al día."*
- **Avisos automáticos de multa y préstamo vencido (Usuario 102):**
  - Turno 1: `mi código es ciento dos`
  - Turno 2: `uno dos tres cuatro`
  - Observación: El agente emite la advertencia proactiva:
    > *"Gracias, Mariana Rosero Burbano. Ya puede hacer sus trámites. Tenga en cuenta: «Fundamentos de seguridad en redes» está vencido hace 5 días y tiene una multa pendiente de $5.000."*
- **Aviso de reserva lista para recoger (Usuario 108):**
  - Turno 1: `mi código es ciento ocho`
  - Turno 2: `uno dos tres cuatro`
  - Observación: El agente notifica proactivamente el aviso de recogida inmediata en mostrador:
    > *"¡Ya puedes recoger «Redes de computadoras»! Tienes 48 horas para reclamarlo en el mostrador presentando tu carné."*

---

## 13. Pruebas del Modo llamada manos libres (Audio continuo)

El modo llamada permite interactuar con el agente por voz continua mediante el transductor del navegador, utilizando detección automática de silencios (VAD) para enviar los turnos sin tocar la pantalla.

### Flujo recomendado para la sustentación:
1. Ve a la vista de **Chat**.
2. Haz clic en el botón verde **Iniciar llamada** (o el ícono del auricular).
3. Concede permisos de micrófono en el navegador si este los solicita.
4. Habla claramente hacia el micrófono y haz una pausa natural al terminar de formular tu consulta:

```
[Turno 1 - Consulta temática general]
Usuario: "¿Tienen libros sobre cómo proteger una red empresarial?"
Agente: Transcribe la voz, consulta pgvector y responde con audio de Piper
        citando los libros de Stallings, Firewalls y Hacking ético.

[Turno 2 - Consulta de reglamento de préstamo]
Usuario: "¿Cuántos días dura el préstamo de un libro y cuántas renovaciones tengo?"
Agente: Responde por voz explicando que el préstamo dura 8 días y se permiten
        máximo 3 renovaciones consecutivas.

[Turno 3 - Identificación por voz con números en palabras]
Usuario: "Mi código es ciento uno"
Agente: Solicita el PIN de seguridad.
Usuario: "Uno dos tres cuatro"
Agente: Valida las credenciales, enmascara el PIN como [PIN oculto] y saluda:
        "Bienvenido Carlos Eduardo Córdoba Díaz. Su cuenta está al día".

[Turno 4 - Trámite transaccional de reserva]
Usuario: "Quiero reservar el libro de Ecología de Odum"
Agente: Verifica la disponibilidad del título y solicita confirmación:
        "¿Confirma la reserva de Ecología de Eugene P. Odum?".
Usuario: "Sí, confirmo"
Agente: Ejecuta la transacción en PostgreSQL y confirma:
        "Reserva confirmada. Su ejemplar ha sido apartado por 48 horas".

[Turno 5 - Finalizar llamada]
Usuario: Haz clic en "Terminar llamada" o di "Adiós".
```

---

## 14. Pruebas del Catálogo público (`#catalogo`)

El Catálogo (`/api/catalogo`) permite explorar los 55 materiales y 103 copias sin necesidad de iniciar sesión:

1. **Búsqueda por texto**: Escribe `Tanenbaum`, `cacao` o `inteligencia artificial`.
2. **Filtro por tipo de material**: Selecciona `Solo libros` o `Solo tesis`.
3. **Filtro por programa**: Selecciona `Ingeniería Agroforestal` o `Administración de Empresas`.
4. **Filtro de disponibilidad**: Activa `Solo disponibles` para ocultar materiales sin copias libres.
5. **Ficha modal**:
   - Haz clic en *Criptografía y seguridad de redes*.
   - Revisa el resumen unificado, la ubicación en estante (Estante 2, nivel B) y los códigos de barras.
   - Pulsa **Ver en Mapa del conocimiento** para proyectar el material en la vista 2D.
   - Pulsa **Preguntar al agente** para abrir el chat con el contexto precargado.

---

## 15. Secuencia recomendada ("Demo de 5 minutos") para la sustentación

Si dispones de poco tiempo durante la presentación ante el jurado, sigue este guion paso a paso:

1. **Voz y multimodalidad (Chat/Llamada):**  
   Por voz: `¿Tienen libros sobre cómo proteger una red?`  
   *(Demuestra captura de micrófono, STT Whisper int8 y TTS Piper en local con orbe animado).*
2. **Semántica vs SQL literal (Panel técnico):**  
   Pestaña **SQL vs pgvector** con la consulta: `cómo proteger una red de una empresa`  
   *(Demuestra empíricamente por qué SQL tradicional da 0 resultados mientras pgvector recupera los materiales pertinentes).*
3. **Asistente de investigación (Vista Investigar):**  
   Ingresa en `#investigacion` el tema: `Sistemas de detección de intrusos en redes` con filtro `Ingeniería de Sistemas`.  
   *(Demuestra respuestas extractivas con citas [material ID], subtemas del acervo y referencias APA copiables).*
4. **Salas de la biblioteca y navegación temática (Chat):**  
   Escribe o di: `quiero la sala de ingeniería` → Andrés saluda delimitando el catálogo a Ingeniería de Sistemas. Luego di: `toda la biblioteca` para regresar al catálogo general.
5. **Catálogo y Ficha modal (Vista Catálogo):**  
   Filtra por `Ingeniería Agroforestal` + `Solo tesis`. Abre la ficha modal de una tesis para ver el resumen y los estantes.
6. **Reglas de negocio y seguridad (Chat):**  
   Identifícate como `102` con PIN `1234` y pide `Renueva mi préstamo`.  
   *(El agente rechaza la renovación por la multa de $5.000).*
7. **Transacción exitosa (Chat):**  
   Identifícate como `101` con PIN `1234` y pide `Resérvame Ecología de Odum` → responde `sí`.  
   *(Se ejecuta la reserva transaccional con SELECT FOR UPDATE).*
8. **Cancelación transaccional (Chat):**  
   Pide `Cancela mi reserva de Ecología` → responde `sí`.  
   *(Se libera el ejemplar a disponible en tiempo real).*
9. **Límites y ética (Chat):**  
   `¿Cómo va a estar el clima mañana?`  
   *(Demuestra que el agente reconoce sus límites y rechaza preguntas fuera de dominio).*
10. **Auditoría y tiempos (Panel técnico):**  
    Pestaña **Bitácora** para visualizar la latencia milimétrica por etapa (STT, embeddings, búsqueda, LLM, TTS).

---

## 16. Preguntas típicas y tiempos objetivo

El sistema cuenta con una batería permanente de **30 preguntas típicas** de alta frecuencia orientadas a verificar la rapidez y precisión del agente frente a consultas cotidianas de estudiantes, docentes e investigadores.

La prueba completa se ejecuta mediante el script:
```powershell
# Ejecución estándar (in-process con TestClient)
python probar_preguntas_tipicas.py

# Ejecución contra servidor activo
python probar_preguntas_tipicas.py --servidor

# Medición con historial acumulado en una misma conversación
python probar_preguntas_tipicas.py --misma-conversacion
```

### Metas oficiales de latencia por tipo de pregunta

| Categoría | Meta máxima | Criterio técnico de optimización |
|---|:---:|---|
| **Deterministas** (saludos, presentación, cortesía, fuera de dominio, trámites directos) | **≤ 3,0 s** | Enrutador rápido sin invocación de LLM pesado. |
| **Reglamento con FAQ clara** (días de préstamo, sanciones, horarios, cupos) | **≤ 3,0 s** | Extracción directa y estructurada de normativas indexadas. |
| **Búsquedas de catálogo** (semántica densa pgvector, búsqueda exacta SQL, disponibilidad) | **≤ 4,0 s** | Representación vectorial con `embeddinggemma` y consultas optimizadas. |
| **Síntesis con LLM o resúmenes extensos** | **≤ 10,0 s** | Redacción contextualizada en CPU mediante modelos compactos. |
| **Promedio global del sistema** | **< 4,0 s** | Umbral institucional para una respuesta ágil y fluida. |

### Batería completa de las 30 preguntas típicas

| # | Pregunta | Intención / Herramienta | Respuesta y comportamiento esperado | Meta |
|:---:|---|---|---|:---:|
| 1 | `Hola` | `saludo` / `None` | Saludo de bienvenida y disposición para orientar al usuario. | ≤ 3,0 s |
| 2 | `¿Quién eres?` | `presentacion` / `None` | Presentación como asistente de biblioteca UniPutumayo (no fuera de dominio). | ≤ 3,0 s |
| 3 | `¿Qué puedes hacer?` | `presentacion` / `None` | Describe funciones clave: catálogo, préstamos, citas APA/IEEE y reservas. | ≤ 3,0 s |
| 4 | `¿Qué libros tienes?` | `panorama_catalogo` | Panorama general indicando cantidad numérica de libros y tesis disponibles. | ≤ 3,0 s |
| 5 | `¿Qué libros hay en la biblioteca?` | `panorama_catalogo` | Muestra el panorama temático y los títulos más representativos del acervo. | ≤ 3,0 s |
| 6 | `¿Qué libro me sugieres?` | `recomendar` | Indaga el área de interés del usuario o sugiere títulos destacados con criterio. | ≤ 4,0 s |
| 7 | `¿Cuál es el mejor libro de programación?` | `recomendar` | Recomienda obras fundamentales: *Fundamentos de programación* o *Cómo programar en Java*. | ≤ 4,0 s |
| 8 | `Recomiéndame un libro para aprender a programar` | `recomendar` | Sugiere textos introductorios de programación entregando fichas de material. | ≤ 4,0 s |
| 9 | `¿Qué me recomiendas para mi tesis de agroforestería?` | `recomendar` | Recomienda trabajos sobre sistemas agroforestales, cultivos amazónicos o cacao. | ≤ 4,0 s |
| 10 | `¿Tienen libros de inteligencia artificial?` | `buscar_semantico` | Recupera el texto de referencia de Stuart Russell y Peter Norvig. | ≤ 4,0 s |
| 11 | `Quiero un libro de contabilidad` | `buscar_semantico` | Despliega resultados pertinentes de contabilidad financiera, de costos y gerencial. | ≤ 4,0 s |
| 12 | `¿Qué tesis hay?` | `panorama_catalogo` | Desglosa los proyectos de grado disponibles en el repositorio institucional. | ≤ 4,0 s |
| 13 | `¿Qué tesis hay sobre cacao?` | `buscar_semantico` | Recupera tesis sobre sistemas agroforestales de cacao y monitoreo IoT en Putumayo. | ≤ 4,0 s |
| 14 | `¿De qué trata la tesis plan de negocios?` | `resumir_material` | Síntesis extractiva del documento referenciando explícitamente la Fuente. | ≤ 4,0 s |
| 15 | `¿Cuál es el libro más prestado?` | `mas_prestados` | Identifica el ejemplar con mayor volumen histórico de préstamos en el sistema. | ≤ 3,0 s |
| 16 | `¿Está disponible Cálculo de una variable?` | `consultar_disponibilidad` | Consulta inmediata del estado de copias disponibles y prestadas. | ≤ 4,0 s |
| 17 | `¿Dónde encuentro el libro Redes de computadoras?` | `ubicacion_material` | Indica la signatura topográfica y estantería física (Estante C-06 o D-01). | ≤ 3,0 s |
| 18 | `¿Cuántos días me prestan un libro?` | `responder_con_documentos` | Cita la política reglamentaria: 8 días para préstamo externo. | ≤ 3,0 s |
| 19 | `¿Cuánto es la multa por día?` | `responder_con_documentos` | Cita el reglamento: $1.000 COP por día calendario de retraso. | ≤ 3,0 s |
| 20 | `¿Cuál es el horario de la biblioteca?` | `responder_con_documentos` | Informa los horarios de atención al público de lunes a viernes. | ≤ 3,0 s |
| 21 | `¿Cuántos libros puedo sacar a la vez?` | `responder_con_documentos` | Informa el cupo máximo de 3 libros (sin desviar a búsqueda semántica). | ≤ 3,0 s |
| 22 | `¿Cómo cito un libro en APA?` | `responder_con_documentos` | Explica la estructura de citación según la guía indexada de APA 7ma edición. | ≤ 3,0 s |
| 23 | `Dame 3 referencias en APA sobre marketing` | `generar_bibliografia` | Genera las 3 referencias formateadas en APA a partir de obras como Kotler. | ≤ 4,0 s |
| 24 | `¿Qué salas hay?` | `elegir_sala` | Enumera las salas temáticas: Ingeniería, Agrarias, Administración, Contaduría e Investigación. | ≤ 3,0 s |
| 25 | `¿Tengo multas?` | `consultar_prestamos_y_multas` | Consulta la cuenta de la sesión activa (reporta $5.000 para el usuario 102). | ≤ 3,0 s |
| 26 | `¿Qué libros tengo prestados?` | `consultar_prestamos_y_multas` | Reporta *Fundamentos de seguridad en redes* en la cuenta del usuario 102. | ≤ 3,0 s |
| 27 | `Renueva mi préstamo` | `renovar_prestamo` | Deniega la renovación e informa sobre el préstamo vencido o multa pendiente. | ≤ 3,0 s |
| 28 | `Gracias` | `cortesia` / `None` | Respuesta de cortesía cerrando cordialmente la interacción. | ≤ 3,0 s |
| 29 | `Adiós` | `cortesia` / `None` | Despedida formal invitando a volver a la biblioteca. | ≤ 3,0 s |
| 30 | `¿Cuál es la capital de Francia?` | `fuera_de_dominio` | Reconoce los límites del agente e informa que solo atiende asuntos bibliotecarios. | ≤ 3,0 s |
