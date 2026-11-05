# Auditoría de consultas comunes del agente de biblioteca

Fecha: 4 de noviembre de 2026. Alcance: lectura del código actual y pruebas aisladas de clasificación y preparación conversacional, sin modificar la aplicación. Las 40 consultas siguientes describen el comportamiento esperado; no constituyen 40 pruebas integrales aprobadas.

No se importó ni ejecutó `procesar_mensaje`, no se llamó a la API ni al LLM y no se abrió una conexión a PostgreSQL. No se crearon, renovaron ni cancelaron reservas o préstamos, ni se cambiaron datos de la usuaria. Esto importa porque incluso `historial_reservas` llama a `sincronizar_espera`, que puede vencer reservas y asignar ejemplares: una consulta aparente no garantiza ausencia de escrituras.

## Criterios para contestar

- Buscar material, consultar disponibilidad y leer reglamento o citación son consultas públicas. La cuenta, las reservas propias, la recogida y los trámites requieren sesión válida, no solamente conocer un código.
- Si falta materia, título o selección entre coincidencias, pedir el dato específico antes de actuar. No elegir silenciosamente un título por similitud.
- Reservar, renovar y cancelar requieren identificar el material propio cuando corresponda y una confirmación explícita. Un «sí» solo vale para la propuesta vigente, que en el chat expira a los dos minutos.
- Distinguir un ejemplar apartado de una solicitud en espera. No prometer recogida, fecha de devolución efectiva o renovación sin verificar el estado pertinente.
- Las respuestas sobre normas deben apoyarse en documentos. Las referencias bibliográficas se construyen con metadatos del catálogo; no se inventan fuentes, DOI, páginas ni editoriales.

En las tablas, «Sí» significa pedir inicio de sesión si aún es invitado; «No» significa que no se necesita sesión para esa consulta. Las acciones son el siguiente paso recomendado, no operaciones ejecutadas durante esta auditoría.

## 1. Recomendaciones y exámenes

| ID | Consulta realista | Intención esperada | Datos faltantes / sesión | Siguiente pregunta o acción adecuada |
|---|---|---|---|---|
| C01 | Recomiéndame algo para estudiar. | Aclarar necesidad y después buscar por tema. | Materia o tema; sesión: No. | «¿Qué materia o tema necesitas estudiar?»; evitar una lista arbitraria. |
| C02 | Tengo un parcial mañana, ¿qué libro me sirve? | Aclarar tema del examen. | Materia; sesión: No. | Pedir materia o tema, conservando que quiere una recomendación para estudiar. |
| C03 | Redes. —después de C02— | Continuar la recomendación con el tema aportado. | Puede faltar nivel o subtema; sesión: No. | Buscar material de redes y ofrecer afinar por protocolos, arquitectura o ejercicios. |
| C04 | Recomiéndame libros básicos de contabilidad con ejercicios. | Búsqueda semántica con nivel y propósito. | Ningún dato indispensable; sesión: No. | Buscar en el acervo; indicar qué contenido respalda la recomendación y no afirmar que tiene ejercicios sin evidencia. |

C02–C03, la normalización oral de APA/IEEE y la recuperación documental separada por norma están siendo atendidas por el coordinador. Se incluyen como aceptación esperada, sin duplicar implementación ni declararlas fallos pendientes aquí.

## 2. Búsqueda por título, autor y tema

| ID | Consulta realista | Intención esperada | Datos faltantes / sesión | Siguiente pregunta o acción adecuada |
|---|---|---|---|---|
| C05 | ¿Tienen el libro «Redes de computadoras»? | Búsqueda exacta de título. | Posible edición o autor si hay coincidencias; sesión: No. | Mostrar coincidencias reales, autor, año y existencias; pedir elección si hay varias. |
| C06 | Busco libros del autor Tanenbaum. | Búsqueda por autor. | Ninguno inicialmente; sesión: No. | Separar el apellido de la frase de petición y buscarlo; no usar toda la frase como nombre. |
| C07 | Necesito material sobre seguridad en redes. | Búsqueda por tema. | Ninguno inicialmente; sesión: No. | Buscar semánticamente y mostrar material pertinente con disponibilidad. |
| C08 | Busco «Ecología», de Odum. | Resolver título y autor. | Ninguno si identifica una obra; sesión: No. | Distinguirla de otros títulos de ecología, usando el autor antes de recomendar o reservar. |
| C09 | ¿De qué trata el libro «Redes de computadoras»? | Resumen o ficha del libro. | Identificar título si es ambiguo; sesión: No. | Usar la ficha/reseña disponible del libro; no responder que no existe una tesis. Véase F03. |

## 3. Disponibilidad

| ID | Consulta realista | Intención esperada | Datos faltantes / sesión | Siguiente pregunta o acción adecuada |
|---|---|---|---|---|
| C10 | ¿Está disponible «Ingeniería de software»? | Consultar disponibilidad del material. | Autor o edición si hay varias; sesión: No. | Resolver material y dar cantidades disponibles, prestadas y reservadas, sin datos de otros usuarios. |
| C11 | ¿Hay algún ejemplar disponible? | Aclarar material para consultar existencias. | Título o tema; sesión: No. | «¿De qué libro o tesis quieres consultar la disponibilidad?» |
| C12 | Si no hay ejemplares de «Redes de computadoras», ¿cuándo habrá? | Consultar disponibilidad y fechas conocidas. | Identificar material; sesión: No. | Distinguir vencimiento previsto de préstamo de disponibilidad garantizada; explicar si no hay fecha confirmada. |

## 4. Reservas

| ID | Consulta realista | Intención esperada | Datos faltantes / sesión | Siguiente pregunta o acción adecuada |
|---|---|---|---|---|
| C13 | Quiero reservar «Redes de computadoras». | Preparar reserva. | Sesión: Sí; selección si hay varias obras. | Identificar título, consultar existencias, explicar apartado o espera y pedir confirmación antes de guardar. |
| C14 | Quiero reservar un libro. | Aclarar material y preparar reserva. | Título; sesión: Sí para tramitar. | Pedir título o invitar a buscar primero; no reservar el candidato semántico de una frase genérica. |
| C15 | Resérvame «Ecología», pero si no hay ejemplar no quiero quedar en espera. | Reserva condicionada por disponibilidad. | Obra exacta si es ambigua; sesión: Sí. | Respetar la condición; si no hay ejemplar, informar y no proponer la espera como si estuviera aceptada. |
| C16 | No quiero reservar «Redes de computadoras», solo saber si está disponible. | Consulta pública de disponibilidad con negación de trámite. | Ninguno si título resuelto; sesión: No. | Consultar existencias sin pedir login para reservar ni preparar esa acción. Véase F06. |

## 5. Recogida

| ID | Consulta realista | Intención esperada | Datos faltantes / sesión | Siguiente pregunta o acción adecuada |
|---|---|---|---|---|
| C17 | ¿Cuándo puedo recoger «Redes de computadoras»? | Consultar recogida de reserva propia. | Sesión: Sí. | Consultar su reserva: si tiene ejemplar apartado, indicar límite y recogida con carné; si está en espera, aclararlo. |
| C18 | ¿Puedo recoger mis reservas hoy? | Consultar reservas propias listas para recoger. | Sesión: Sí. | Separar las listas de las que siguen en espera y apoyarse en el horario documentado; no interpretar «hoy» como garantía de apertura. |
| C19 | Mi reserva sigue en espera, ¿puedo retirar el libro? | Aclarar recogida y estado de espera. | Sesión: Sí; título si tiene varias reservas. | Explicar que una solicitud en espera no aparta un ejemplar; comprobar si el estado cambió y señalar el aviso disponible en la aplicación. |

## 6. Cuenta y multas

| ID | Consulta realista | Intención esperada | Datos faltantes / sesión | Siguiente pregunta o acción adecuada |
|---|---|---|---|---|
| C20 | Muéstrame mi cuenta y mis préstamos. | Consultar cuenta propia. | Sesión: Sí. | Mostrar préstamos, vencimientos, multas y reservas del usuario autenticado; no pedir el código de otra cuenta. |
| C21 | ¿Cuánto debo de multas? | Consultar multas propias. | Sesión: Sí. | Leer importes registrados y distinguirlos de una multa estimada por retraso; no inventar un importe pagado. |
| C22 | ¿Cómo pago una multa? | Consultar procedimiento documentado. | Sesión: No para conocer el procedimiento. | Buscar reglamento/FAQ; si el procedimiento no aparece, decirlo y orientar a biblioteca sin inventar pasarelas. Véase F02. |
| C23 | Mis reservas. | Consultar reservas propias. | Sesión: Sí. | Abrir Mis reservas o consultar la cuenta; no preparar una reserva nueva. Véase F01. |

## 7. Renovación

| ID | Consulta realista | Intención esperada | Datos faltantes / sesión | Siguiente pregunta o acción adecuada |
|---|---|---|---|---|
| C24 | Quiero renovar mi préstamo. | Preparar renovación. | Sesión: Sí; título si tiene varios préstamos. | Listar préstamos propios cuando haga falta; validar vencimiento, máximo, multas y reserva ajena, y pedir confirmación. |
| C25 | ¿Puedo renovar mi préstamo? | Comprobar elegibilidad y, si procede, preparar renovación. | Sesión: Sí; título si hay varios. | Interpretar «puedo» como parte de la petición, no como título; comprobar préstamos propios. Véase F04. |
| C26 | Renueva mi préstamo. | Preparar renovación, equivalente a «quiero renovar». | Sesión: Sí; selección si hay varios. | Reconocer el imperativo; no responder solamente con la cuenta. Véase F04. |
| C27 | «Redes de computadoras». —después de que pregunte cuál préstamo renovar— | Completar selección de la renovación. | Contexto del turno anterior; sesión: Sí. | Resolver el título únicamente entre los préstamos ofrecidos, validar y pedir confirmación; no empezar una búsqueda general. Véase F05. |

## 8. Cancelación

| ID | Consulta realista | Intención esperada | Datos faltantes / sesión | Siguiente pregunta o acción adecuada |
|---|---|---|---|---|
| C28 | Cancela mi reserva de «Redes de computadoras». | Preparar cancelación de reserva propia. | Sesión: Sí. | Identificar la reserva activa del usuario y pedir confirmación; no tocar préstamos ni reservas ajenas. |
| C29 | Cancela mi reserva. | Aclarar cuál reserva cancelar. | Sesión: Sí; título si hay varias. | Si solo hay una, proponerla; si hay varias, enumerarlas y conservar la intención para la respuesta siguiente. Véase F05. |
| C30 | No, mejor no. —ante una confirmación de cancelación— | Rechazar la acción pendiente. | Propuesta vigente; sesión: la de la operación. | Descartar la propuesta sin cancelar la reserva; la frase no debe interpretarse como confirmar. |

## 9. Reglamento

| ID | Consulta realista | Intención esperada | Datos faltantes / sesión | Siguiente pregunta o acción adecuada |
|---|---|---|---|---|
| C31 | ¿Cuántas veces puedo renovar un libro? | Consulta de norma general. | Ninguno; sesión: No. | Recuperar la regla documentada y citar la sección; no iniciar una renovación. |
| C32 | ¿Cuál es el horario de la biblioteca? | Consultar horario documentado. | Fecha especial solo si pregunta por festivo; sesión: No. | Informar horario de la fuente y reconocer si no constan excepciones para ese día. |
| C33 | ¿Qué hago si perdí o dañé un libro prestado? | Consultar procedimiento por pérdida o daño. | Ninguno para la regla general; sesión: No. | Responder con el reglamento y el canal documentado; no fijar cobros o sanciones no respaldados. |

## 10. APA e IEEE

| ID | Consulta realista | Intención esperada | Datos faltantes / sesión | Siguiente pregunta o acción adecuada |
|---|---|---|---|---|
| C34 | ¿Cómo cito un libro en APA? | Explicar formato de citación de libro. | Datos de la obra solo si pide construir su cita; sesión: No. | Recuperar guía APA y distinguir cita dentro del texto de referencia final. |
| C35 | Explícame la diferencia entre APA e IEEE. | Comparar normas documentadas. | Ninguno; sesión: No. | Recuperar ambas normas por separado y explicar autor-fecha frente a numeración, con las fuentes correspondientes. |
| C36 | Dame cinco referencias IEEE sobre seguridad en redes. | Generar bibliografía del acervo. | Tema, norma y cantidad presentes; sesión: No. | Construir hasta cinco referencias con metadatos reales; si hay menos, explicarlo; mantener el orden de la norma. |
| C37 | Hazme una bibliografía en APA. | Aclarar tema de bibliografía. | Tema; sesión: No. | «¿Sobre qué tema necesitas las referencias?»; no asumir que «APA» es el tema ni inventar obras. |

## 11. Tesis y repositorio

| ID | Consulta realista | Intención esperada | Datos faltantes / sesión | Siguiente pregunta o acción adecuada |
|---|---|---|---|---|
| C38 | Busco tesis sobre cacao en el Putumayo. | Búsqueda temática de tesis. | Ninguno inicialmente; sesión: No. | Recuperar material pertinente y distinguir tesis de libros; ofrecer catálogo filtrado si necesita listar solo tesis. |
| C39 | ¿De qué trata la tesis sobre cacao en el Putumayo? | Resolver tesis y resumir sus fuentes. | Título si hay varias coincidencias; sesión: No. | Identificar la tesis, usar resumen/PDF indexado y citar sección o página; no mezclar resultados de distintas obras. |
| C40 | Quiero subir mi tesis, ¿qué necesito? | Orientar hacia el flujo existente de subida. | Sesión: Sí para subir; PDF y metadatos. | Explicar el botón Subir tesis: PDF de hasta 25 MB, título, autor, año y programa; iniciar sesión antes del envío y mostrar el progreso existente. No prometer carga por una herramienta de chat que no existe. |

## Seis fallos concretos a priorizar

Los resultados de clasificación son deterministas. En `procesar_mensaje`, si las palabras clave producen una intención distinta de la del LLM y no es `fuera_de_dominio`, el código sustituye la elección del LLM por la regla; por eso los errores siguientes no se pueden descartar suponiendo que el modelo siempre los corregirá. El mensaje final de extremo a extremo no se ejecutó en esta auditoría.

### F01. Consultar «Mis reservas» dispara la intención de crear una reserva

**Evidencia ejecutada:** `intencion_por_palabras("Mis reservas") == "reservar"`; también ocurre con «Quiero ver mis reservas». La condición amplia `if "reserv" in normalizado` aparece antes de distinguir una consulta de reservas propias. `_ejecutar_herramienta` trata `reservar` como trámite que requiere login y resolución de material.

**Consecuencia:** el nombre de una vista existente se interpreta como otro trámite; autenticado puede acabar buscando «mis reservas» como material, sin listar su cuenta. No se observó creación involuntaria: la operación real aún tiene confirmación.

**Corrección recomendada:** reconocer solicitudes explícitas de listar/ver reservas propias antes del verbo reservar, dirigiéndolas a la consulta ya disponible o a Mis reservas. Conservar «quiero reservar [título]» para crear una propuesta. Aceptación: C13 y C23 terminan en intenciones distintas.

### F02. «¿Cómo pago una multa?» se interpreta como consulta privada de cuenta

**Evidencia ejecutada:** `intencion_por_palabras("¿Cómo pago una multa?") == "consultar_prestamos_y_multas"`. La coincidencia por «multa» no distingue procedimiento de pago de saldo personal. Además, `accionesSiguientes` del chat ofrece precisamente «¿Cómo pago una multa?» como acción de seguimiento.

**Consecuencia:** un invitado recibe una petición de identificación para una pregunta general, y un usuario autenticado puede recibir el saldo sin el procedimiento que pidió. No se probó ni se propone implementar un sistema de pagos.

**Corrección recomendada:** separar «cómo/dónde pagar una multa» de «cuánto debo/mis multas», enviando lo primero a documentos/FAQ. Si no existe información de pago en las fuentes, reconocer la ausencia. Aceptación: C21 requiere cuenta; C22 permite respuesta pública documentada.

### F03. Resuelto: libros admitidos por el resumidor sin perder tesis ni procedencia

**Actualización del 4 de noviembre de 2026:** se corrigió únicamente `herramientas.resumir_material` para recuperar reseñas de libros o resumen/páginas de tesis. Respeta el tipo explícito de la pregunta, pide selección antes de recuperar fragmentos cuando hay varias obras y filtra los fragmentos por identificador y tipo documental del material elegido. Si no hay texto indexado, lo informa sin inventar un resumen; las fuentes conservan sección, tipo y procedencia reales. El coordinador y otro constructor atienden los textos/prompt de `agente.py`; esta corrección no modifica ese archivo.

**Verificación:** `venv/Scripts/python.exe evaluacion/resumen_libros_regresion.py --real` pasó 13/13 regresiones con dobles de libro, tesis con PDF, filtro de tipo explícito, ambigüedad, ausencia de texto, errores y aislamiento de obras. La lectura real del catálogo recuperó el libro 33, «Sistemas agroforestales: principios y aplicaciones en los trópicos», con dos fragmentos de reseña y dos fuentes de esa misma obra. No se modificaron datos ni servidores; no se ejecutó la redacción final por LLM ni una prueba de interfaz. La evidencia siguiente se conserva como registro del fallo anterior, ya corregido en la herramienta.

**Evidencia ejecutada y de lectura:** «¿De qué trata el libro Redes de computadoras?» se clasifica como `resumir_material`; esa herramienta en `herramientas.py` filtra candidatos con `tipo == "tesis"`. Al ejecutarla aislada con un resolver ficticio que devolvía únicamente un libro, respondió `ok=False`, «No encontré esa tesis en el repositorio». La ficha del catálogo usa el mismo botón «Preguntar al agente» para todos los tipos y emite «¿De qué trata «[título]»?».

**Consecuencia:** una ruta visible de la interfaz puede negar la existencia de una tesis cuando la usuaria está preguntando por un libro que sí está en pantalla.

**Corrección recomendada:** resolver primero el material y elegir la ficha/reseña ya disponible para libros, manteniendo resumen/PDF para tesis; alternativamente, que el botón ofrezca explícitamente la ficha cuando no haya resumidor aplicable. No inventar una explicación si la reseña no contiene suficiente información. Aceptación: C09 y C39 distinguen tipo y fuente.

### F04. Variantes comunes de renovación se pierden en la intención o en el título

**Evidencia ejecutada:** «Renueva mi préstamo» produce `consultar_prestamos_y_multas`, porque «renueva» no contiene la raíz literal `renov`. «¿Puedo renovar mi préstamo?» sí produce `renovar_prestamo`, pero `_titulo_renovacion` devuelve `"puedo"`. `procesar_mensaje` fuerza esa extracción cuando coincide la regla de renovación; luego `_ejecutar_herramienta` busca ese supuesto título entre los préstamos propios.

**Consecuencia:** dos formas habituales de la misma petición pueden devolver la cuenta o «No encontré ese préstamo entre los suyos», aunque un préstamo válido esté disponible para seleccionar. La elegibilidad real no se comprobó contra ninguna cuenta.

**Corrección recomendada:** reconocer formas habituales de renovar y retirar auxiliares interrogativos/cortesías antes de decidir si hay un título. Cuando no quede título, usar la selección de préstamos propia ya existente, sin asumir elegibilidad. Aceptación: C24–C26 siguen el mismo flujo y conservan las restricciones de renovación.

### F05. La pregunta «¿cuál préstamo/reserva?» no conserva un estado explícito de selección

**Evidencia ejecutada:** `_ejecutar_herramienta("renovar_prestamo", {"titulo": ""}, usuario_ficticio, estado={})`, con dos préstamos ficticios, devolvió «¿Cuál préstamo desea renovar?» y dejó `estado == {}`. La rama de varias reservas devuelve una pregunta equivalente sin guardar selección. Una respuesta aislada «Redes de computadoras» se clasifica como `buscar_semantico`; «Ingeniería de software» como `fuera_de_dominio`.

**Consecuencia:** aunque el historial enviado al LLM puede ayudar en algunos casos, no hay continuación determinista garantizada. Para «Redes de computadoras» la regla no vacía puede incluso sustituir una elección contextual correcta del LLM por una búsqueda. Una usuaria puede contestar bien la pregunta que el propio agente hizo y perder el trámite.

**Corrección recomendada:** guardar temporalmente la intención y los identificadores de las opciones ofrecidas, aceptar la siguiente selección únicamente entre esas opciones y volver a validar antes de confirmar. Permitir cancelar esa selección; no interpretar cualquier título posterior como autorización de ejecutar. Aceptación: C27 y la continuación de C29 preparan el trámite correcto sin escribir todavía.

### F06. Negaciones y condiciones de reserva no se preservan en la ruta determinista

**Evidencia ejecutada:** `intencion_por_palabras("No quiero reservar Redes de computadoras") == "reservar"`. Por lectura, la regla `"reserv" in normalizado` también precede a la consulta de disponibilidad en C16. `_seleccion_directa_segura` evita el atajo ante «no» o «si», pero la selección posterior por palabras puede volver a imponer `reservar`; sus argumentos no contienen un campo para la condición de no quedar en espera. `_ejecutar_herramienta` ofrece esperar cuando no hay disponibilidad, sin comprobar esa condición de la frase.

**Consecuencia:** el agente puede pedir login o proponer una reserva que fue negada, o perder una condición expresa. La confirmación de la operación reduce el riesgo; no se observó ni se afirma que haya reservado automáticamente por una negación.

**Corrección recomendada:** reconocer primero negación de trámite y preguntas informativas, y confirmar por separado cualquier cambio de condición —por ejemplo, entrar en espera—. Si la frase mezcla acciones y no se puede interpretar con seguridad, preguntar antes de preparar. Aceptación: C16 solo consulta y C15 no introduce una espera implícita.

## Evidencia, fuentes y límites

Se leyeron las funciones de [agente.py](../app/agente.py), en particular `intencion_por_palabras`, `_titulo_renovacion`, `_ejecutar_herramienta`, `_confirmar_pendiente`, `_estudio_sin_tema` y `procesar_mensaje`; y [herramientas.py](../app/herramientas.py), en particular `resolver_material`, `resumir_material`, `consultar_recogida`, `historial_reservas`, `validar_renovacion` y `responder_con_documentos`.

Para contrastar los flujos visibles se revisaron [chat.js](../static/js/chat.js) —tarjetas, sugerencias, login y confirmaciones—, [catalogo.js](../static/js/vistas/catalogo.js) —ficha y traslado al chat—, [mis_reservas.js](../static/js/vistas/mis_reservas.js) y [cuenta.js](../static/js/cuenta.js) —consulta propia y confirmación de cancelación—, [tesis.js](../static/js/tesis.js) —validación, sesión y progreso—, y la continuación del login en [app.js](../static/js/app.js) y [sesion.js](../static/js/sesion.js). Las referencias por función son deliberadas: otros constructores trabajan simultáneamente y los números de línea pueden cambiar.

**Método reproducible sin escrituras:** con `venv/Scripts/python.exe`, leer los archivos con `Path.read_text(encoding="utf-8")`, extraer mediante `ast.parse` únicamente las definiciones indicadas y compilar esas funciones en un espacio con `re`, `unicodedata` y `typing.Any`; no ejecutar las importaciones del módulo. Para F05 se sustituyó `herramientas.prestamos_activos_usuario` por una función que devuelve dos registros ficticios; para F03 se aisló el resumidor y se sustituyó `resolver_material` por un resultado de libro ficticio. Ninguna de esas pruebas necesita credenciales, base de datos, Ollama ni llamadas HTTP.

| Comprobación aislada | Resultado observado |
|---|---|
| `intencion_por_palabras("Mis reservas")` | `reservar` |
| `intencion_por_palabras("¿Cómo pago una multa?")` | `consultar_prestamos_y_multas` |
| `intencion_por_palabras("¿De qué trata el libro Redes de computadoras?")` | `resumir_material` |
| Resumidor con único candidato ficticio de tipo libro | `ok=False`; «No encontré esa tesis en el repositorio» |
| `intencion_por_palabras("Renueva mi préstamo")` | `consultar_prestamos_y_multas` |
| `_titulo_renovacion("¿Puedo renovar mi préstamo?")` | `"puedo"` |
| Preparar renovación con dos préstamos ficticios | Pregunta cuál renovar; no añade contexto de selección al estado |
| `intencion_por_palabras("Redes de computadoras")` | `buscar_semantico` |
| `intencion_por_palabras("Ingeniería de software")` | `fuera_de_dominio` |
| `intencion_por_palabras("No quiero reservar Redes de computadoras")` | `reservar` |

Esta auditoría no valida disponibilidad actual, saldos, permisos efectivos, contenido documental recuperado, calidad de recomendaciones, audio o latencia; tampoco certifica respuestas finales generadas por el modelo. Queda al coordinador priorizar estos seis ajustes y, si los aplica, verificar regresiones con dobles de prueba o una base aislada antes de cualquier prueba que escriba trámites. No se requieren nuevas funciones para atender la mayoría de los casos: las recomendaciones proponen encaminar correctamente las herramientas y vistas existentes.
