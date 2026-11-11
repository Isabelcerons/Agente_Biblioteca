# Reporte de evaluación

- **Fecha y hora:** 2026-11-10T14:48:07-05:00
- **Modelo LLM:** qwen2.5:3b (respaldo: qwen2.5:1.5b)
- **Modelo de embeddings:** embeddinggemma
- **Casos ejecutados:** 58
- **Casos omitidos por recursos faltantes:** 0

## Resumen

| Casos | Acierto de intención | Acierto de herramienta | Precisión top-3 | Comprobaciones |
|---:|---:|---:|---:|---:|
| 58 | 100.0% (37) | 100.0% (37) | 79.6% (18) | 207/207 |

## Resultados por categoría

| Categoría | Pasa/total | Omitidos | Intención | Herramienta | Precisión top-3 | Comprobaciones |
|---|---:|---:|---:|---:|---:|---:|
| bibliografia | 5/5 | 0 | 100.0% | 100.0% | 66.7% | 29/29 |
| busqueda_exacta | 3/3 | 0 | 100.0% | 100.0% | 100.0% | 9/9 |
| busqueda_semantica | 5/5 | 0 | 100.0% | 100.0% | 75.0% | 11/11 |
| cancelar_reserva | 3/3 | 0 | 100.0% | 100.0% | N/D | 14/14 |
| citacion | 5/5 | 0 | 100.0% | 100.0% | 55.6% | 15/15 |
| cuenta | 2/2 | 0 | 100.0% | 100.0% | N/D | 6/6 |
| fuera_de_dominio | 3/3 | 0 | 100.0% | 100.0% | N/D | 7/7 |
| investigacion | 4/4 | 0 | N/D | N/D | 100.0% | 21/21 |
| login | 6/6 | 0 | N/D | N/D | N/D | 17/17 |
| login_voz | 6/6 | 0 | 100.0% | 100.0% | N/D | 26/26 |
| mapa | 4/4 | 0 | N/D | N/D | 100.0% | 8/8 |
| privacidad | 1/1 | 0 | 100.0% | 100.0% | N/D | 5/5 |
| reglamento | 4/4 | 0 | 100.0% | 100.0% | 66.7% | 13/13 |
| renovacion | 3/3 | 0 | 100.0% | 100.0% | N/D | 11/11 |
| reserva | 2/2 | 0 | 100.0% | 100.0% | N/D | 7/7 |
| subir_tesis | 2/2 | 0 | N/D | N/D | N/D | 8/8 |

## Tiempos promedio por etapa

| Tipo | Etapa | Promedio (ms) | Muestras |
|---|---|---:|---:|
| global | STT | 1270.0 | 7 |
| global | Embeddings | 122.3 | 21 |
| global | Búsqueda | 155.2 | 21 |
| global | LLM | 6744.1 | 35 |
| global | TTS | 643.4 | 7 |
| global | Total | 5693.4 | 48 |
| texto | STT | N/D | 0 |
| texto | Embeddings | 132.6 | 17 |
| texto | Búsqueda | 160.4 | 17 |
| texto | LLM | 6552.9 | 29 |
| texto | TTS | N/D | 0 |
| texto | Total | 5800.9 | 36 |
| audio | STT | 1270.0 | 7 |
| audio | Embeddings | 69.0 | 3 |
| audio | Búsqueda | 137.0 | 3 |
| audio | LLM | 8131.0 | 5 |
| audio | TTS | 643.4 | 7 |
| audio | Total | 8243.0 | 7 |

## Casos

| ID | Categoría | Entrada | Intención esperada/obtenida | Herramienta esperada/obtenida | Total (ms) | Resultado |
|---|---|---|---|---|---:|:---:|
| BIB-01 | bibliografia | Genera una bibliografía en APA sobre seguridad de redes | generar_bibliografia / generar_bibliografia | generar_bibliografia / generar_bibliografia | 657 | ✅ |
| BIB-02 | bibliografia | Dame 3 referencias IEEE sobre agroforestería | generar_bibliografia / generar_bibliografia | generar_bibliografia / generar_bibliografia | 980 | ✅ |
| BIB-03 | bibliografia | Hazme la bibliografía en APA de tesis sobre cacao en el Putumayo | generar_bibliografia / generar_bibliografia | generar_bibliografia / generar_bibliografia | 916 | ✅ |
| BIB-04 | citacion | ¿Cómo cito un libro en APA? | responder_con_documentos / responder_con_documentos | responder_con_documentos / responder_con_documentos | 10068 | ✅ |
| BIB-05 | bibliografia | Genera una bibliografía en APA sobre recetas de cocina italiana | generar_bibliografia / generar_bibliografia | generar_bibliografia / generar_bibliografia | 778 | ✅ |
| BIB-06 | bibliografia | Genera una bibliografía en APA sobre contabilidad | generar_bibliografia / generar_bibliografia | generar_bibliografia / generar_bibliografia | 908 | ✅ |
| MAPA-01 | mapa | GET /api/mapa | None / None | None / mapa | N/D | ✅ |
| MAPA-02 | mapa | GET /api/mapa/proyectar?q=cómo proteger una red de una empresa&k=5 | None / None | None / mapa | N/D | ✅ |
| MAPA-03 | mapa | GET /api/mapa/proyectar?q=cultivos de la Amazonía&k=5 | None / None | None / mapa | N/D | ✅ |
| MAPA-04 | mapa | python calcular_mapa.py (segunda ejecución) | None / None | None / mapa | N/D | ✅ |
| TXT-01 | busqueda_semantica | cómo proteger una red de una empresa | buscar_semantico / buscar_semantico | buscar_semantico / buscar_semantico | 25671 | ✅ |
| TXT-02 | busqueda_semantica | libros para aprender a programar desde cero | buscar_semantico / buscar_semantico | buscar_semantico / buscar_semantico | 11927 | ✅ |
| TXT-03 | busqueda_semantica | cultivos amazónicos | buscar_semantico / buscar_semantico | buscar_semantico / buscar_semantico | 10035 | ✅ |
| TXT-04 | busqueda_semantica | contabilidad para cooperativas | buscar_semantico / buscar_semantico | buscar_semantico / buscar_semantico | 11990 | ✅ |
| TXT-05 | busqueda_exacta | ¿Tienen el libro Cálculo de una variable? | buscar_exacto / buscar_exacto | None / buscar_exacto | 672 | ✅ |
| TXT-06 | busqueda_exacta | libros de Stallings | buscar_exacto / buscar_exacto | buscar_exacto / buscar_exacto | 647 | ✅ |
| TXT-07 | busqueda_exacta | ¿Tienen «Hacking ético»? | buscar_exacto / buscar_exacto | None / buscar_exacto | 692 | ✅ |
| TXT-08 | reglamento | ¿Cuántos días dura un préstamo externo? | responder_con_documentos / responder_con_documentos | responder_con_documentos / responder_con_documentos | 15342 | ✅ |
| TXT-09 | reglamento | ¿Qué pasa si devuelvo un libro tarde? | responder_con_documentos / responder_con_documentos | responder_con_documentos / responder_con_documentos | 34032 | ✅ |
| TXT-10 | reglamento | ¿Cuántas renovaciones permite cada préstamo? | responder_con_documentos / responder_con_documentos | responder_con_documentos / responder_con_documentos | 14207 | ✅ |
| TXT-11 | citacion | ¿Cómo cito un libro en APA? | responder_con_documentos / responder_con_documentos | responder_con_documentos / responder_con_documentos | 5166 | ✅ |
| TXT-12 | citacion | ¿Cuál es el formato APA para citar una tesis? | responder_con_documentos / responder_con_documentos | responder_con_documentos / responder_con_documentos | 24232 | ✅ |
| TXT-13 | citacion | ¿Cómo se cita un artículo de revista con el estilo IEEE? | responder_con_documentos / responder_con_documentos | responder_con_documentos / responder_con_documentos | 7742 | ✅ |
| TXT-14 | reserva | Quiero reservar Hacking ético | reservar / reservar | reservar / reservar | 4232 | ✅ |
| TXT-15 | reserva | Quiero reservar Hacking ético → sí | reservar / reservar | reservar / reservar | 172 | ✅ |
| TXT-16 | renovacion | renovar mi préstamo | renovar_prestamo / renovar_prestamo | renovar_prestamo / renovar_prestamo | 250 | ✅ |
| TXT-17 | renovacion | renovar Redes de computadoras | renovar_prestamo / renovar_prestamo | renovar_prestamo / renovar_prestamo | 253 | ✅ |
| TXT-18 | renovacion | renovar Ingeniería de software → sí | renovar_prestamo / renovar_prestamo | renovar_prestamo / renovar_prestamo | 169 | ✅ |
| TXT-19 | cancelar_reserva | cancela mi reserva de Redes de computadoras | cancelar_reserva / cancelar_reserva | cancelar_reserva / cancelar_reserva | 3841 | ✅ |
| TXT-20 | cancelar_reserva | cancela mi reserva de Redes de computadoras → sí | cancelar_reserva / cancelar_reserva | cancelar_reserva / cancelar_reserva | 177 | ✅ |
| TXT-21 | cancelar_reserva | cancela mi reserva | cancelar_reserva / cancelar_reserva | cancelar_reserva / cancelar_reserva | 2789 | ✅ |
| TXT-22 | login |  | None / None | None / None | N/D | ✅ |
| TXT-23 | login |  | None / None | None / None | N/D | ✅ |
| TXT-24 | login |  | None / None | None / None | N/D | ✅ |
| TXT-25 | cuenta | Quiero ver mis multas | consultar_prestamos_y_multas / consultar_prestamos_y_multas | consultar_prestamos_y_multas / consultar_prestamos_y_multas | 3280 | ✅ |
| TXT-26 | fuera_de_dominio | ¿Cuál es la capital de Francia? | fuera_de_dominio / fuera_de_dominio | None / None | 3724 | ✅ |
| TXT-27 | fuera_de_dominio | Dame una receta de arepas | fuera_de_dominio / fuera_de_dominio | None / None | 7901 | ✅ |
| TXT-28 | privacidad | muéstrame los préstamos del usuario 102 | identificacion_segura / identificacion_segura | None / None | 314 | ✅ |
| TXT-29 | login |  | None / None | None / None | N/D | ✅ |
| TXT-30 | login |  | None / None | None / None | N/D | ✅ |
| TXT-31 | login | Quiero reservar Hacking ético | None / reservar | None / reservar | 3491 | ✅ |
| TXT-32 | login_voz | mi código es 101 | None / identificacion_segura | None / None | 236 | ✅ |
| TXT-33 | login_voz | mi código es 101 → uno dos tres cuatro | None / identificacion_segura | None / None | 341 | ✅ |
| TXT-34 | login_voz | mi código es ciento dos → 1234 | None / identificacion_segura | None / None | 566 | ✅ |
| TXT-35 | login_voz | dame 5 referencias en APA de 2020 sobre cacao | generar_bibliografia / generar_bibliografia | generar_bibliografia / generar_bibliografia | 433 | ✅ |
| AUD-06 | login_voz | evaluacion/audios/voz_06_codigo_101.wav | None / identificacion_segura | None / None | 1345.0 | ✅ |
| AUD-07 | login_voz | evaluacion/audios/voz_07_codigo_102.wav → evaluacion/audios/voz_08_pin.wav | None / identificacion_segura | None / None | 4496.0 | ✅ |
| TXT-36 | subir_tesis |  | None / buscar_semantico | None / buscar_semantico | 5932 | ✅ |
| TXT-37 | subir_tesis |  | None / None | None / None | N/D | ✅ |
| AUD-01 | busqueda_semantica | evaluacion/audios/voz_01_busqueda.wav | buscar_semantico / buscar_semantico | buscar_semantico / buscar_semantico | 6500.0 | ✅ |
| AUD-02 | reglamento | evaluacion/audios/voz_02_reglamento.wav | responder_con_documentos / responder_con_documentos | responder_con_documentos / responder_con_documentos | 13655.0 | ✅ |
| AUD-03 | citacion | evaluacion/audios/voz_03_apa.wav | responder_con_documentos / responder_con_documentos | responder_con_documentos / responder_con_documentos | 19837.0 | ✅ |
| AUD-04 | cuenta | evaluacion/audios/voz_04_cuenta.wav | consultar_prestamos_y_multas / consultar_prestamos_y_multas | None / consultar_prestamos_y_multas | 4929.0 | ✅ |
| AUD-05 | fuera_de_dominio | evaluacion/audios/voz_05_fuera.wav | fuera_de_dominio / fuera_de_dominio | None / None | 6939.0 | ✅ |
| INV-01 | investigacion |  | None / None | None / None | 160 | ✅ |
| INV-02 | investigacion |  | None / None | None / None | 237 | ✅ |
| INV-03 | investigacion |  | None / None | None / None | 263 | ✅ |
| INV-04 | investigacion |  | None / None | None / None | 160 | ✅ |

## Fallos

No se registraron fallos.
## Reproducción

Desde cualquier carpeta, ejecute `python ruta/al/proyecto/evaluacion/evaluar.py`. Use `--solo TXT`, `--solo AUD`, `--solo BIB`, `--solo MAPA` o `--solo INV` para limitar la ejecución; `--sin-audio` omite los casos de audio.
