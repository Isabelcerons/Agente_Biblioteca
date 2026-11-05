# Guía de preguntas para probar el agente (datos de demostración)

## 1. Usuarios de prueba (dile "mi código es ...")
| Código | Nombre | Situación |
|---|---|---|
| 101 | Carlos Córdoba (docente) | Sin problemas: ideal para reservar |
| 102 | Mariana Rosero | Multa pendiente de $5.000 y préstamo vencido: NO puede renovar |
| 103 | Valentina Cárdenas | Préstamo de "Cálculo de una variable" con 3 renovaciones: NO puede renovar más |
| 104 | Juan Sebastián Muñoz | Tiene "Redes de computadoras", pero otra persona lo reservó: NO puede renovar |
| 105 | Andrés Jojoa | Préstamo activo de "Ingeniería de software": SÍ puede renovar |
| 106 | Laura Insuasty | Préstamo activo de "Fundamentos de bases de datos" |
| 107 | Diego Chicunque | Ya devolvió su libro; tuvo una multa que ya pagó |
| 108 | Paola Zambrano (docente) | Tiene una reserva activa de "Redes de computadoras" |

## 2. Búsqueda por tema (pgvector)
- "¿Tienen libros sobre cómo proteger una red?"  -> Stallings, Firewalls y VPN, Hacking ético...
- "Necesito algo del medio ambiente"  -> Ecología (Odum), Ciencias ambientales...
- "Quiero aprender a programar desde cero"  -> Fundamentos de programación (Joyanes), Java (Deitel)
- "Libros para hacer mi tesis"  -> Metodología de la investigación (Hernández Sampieri)
- "¿Qué hay sobre cultivos de cacao en el Putumayo?"  -> tesis de cacao (piedemonte, IoT, comercialización)
- "Algo sobre suelos"  -> El suelo (Brady), Edafología, Conservación de suelos
- "Libros de marketing y ventas"  -> Kotler
- "¿Hay tesis sobre turismo?"  -> Sibundoy, corredor Mocoa-Sibundoy

## 3. Búsqueda exacta (título o autor)
- "¿Tienen Redes de computadoras de Tanenbaum?"
- "Busca libros de Kotler"
- "¿Está disponible Inteligencia artificial de Russell y Norvig?"

## 4. De qué trata un material
- "¿De qué trata la tesis del sacha inchi?"
- "Resúmeme la tesis de calidad del agua en Orito"
- "¿De qué trata Ingeniería de software de Sommerville?"

## 5. Reglamento (documentos)
- "¿Cuántos días me prestan un libro?"  -> 8 días
- "¿Cuántas veces puedo renovar?"  -> máximo 3
- "¿Cuánto es la multa por día de retraso?"  -> $1.000
- "¿Cuánto tiempo me guardan una reserva?"  -> 48 horas
- "¿Puedo prestar mi carné a otra persona?"

## 6. Citación
- "¿Cómo cito un libro en APA?"
- "¿Cómo cito una tesis en APA 7?"
- "¿Cuál es la diferencia entre APA e IEEE?"
- "¿Qué bases de datos académicas puedo usar?"

## 7. Trámites (necesitan código)
- "¿Tengo multas?"  (con 102 -> $5.000 pendiente)
- "¿Qué libros tengo prestados?"
- "Renueva mi préstamo"  (con 105 -> lo renueva; con 102, 103 o 104 -> explica por qué no)
- "Resérvame Ecología de Odum"  (con 101 -> pide confirmación, luego "sí")

## 8. Fuera de dominio (debe decir que no es su tema)
- "¿Cómo va a estar el clima mañana?"
- "Recomiéndame una película"

## Demo recomendada para la sustentación (en orden)
1. Por voz: "¿Tienen libros sobre cómo proteger una red?"
2. Pestaña SQL vs pgvector con: "cómo proteger una red de una empresa"
3. "Mi código es 102" -> "Renueva mi préstamo" (lo niega por la multa)
4. "Mi código es 101" -> "Resérvame Ecología de Odum" -> "sí"
5. "¿Cómo cito una tesis en APA?"
6. "¿Cómo va a estar el clima mañana?" (muestra sus límites)
7. Pestaña Bitácora con los tiempos

## Identificarse por voz

Como invitado: «mi código es ciento uno» → «uno dos tres cuatro».
Para ver avisos de multa: «mi código es ciento dos» → «uno dos tres cuatro».
También puedes pedir «quiero reservar Hacking ético» y seguir las instrucciones de código y PIN; al final confirma o cancela la reserva.
