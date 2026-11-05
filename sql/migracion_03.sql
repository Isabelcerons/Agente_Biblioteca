-- ============================================================
-- Migración 03 — Códigos cortos para los usuarios de demostración
-- Cambia los códigos de 10 dígitos por códigos de 3 dígitos, fáciles de decir por voz
-- ("mi código es ciento uno"). NO borra ni modifica préstamos, multas, reservas,
-- conversaciones ni PIN: todas esas tablas apuntan al id del usuario, no a su código.
-- Idempotente: si un código viejo ya no existe (migración aplicada), no hace nada.
-- Ejecutar como agente_biblio:  psql -d biblioteca_agente -f sql/migracion_03.sql
-- ============================================================
BEGIN;

UPDATE public.usuarios AS u
SET codigo = m.nuevo
FROM (VALUES
    ('2021110008', '101'),  -- Carlos Eduardo Córdoba Díaz: sin problemas
    ('2021110003', '102'),  -- Mariana Rosero Burbano: préstamo vencido y multa pendiente
    ('2021110001', '103'),  -- Valentina Cárdenas Rojas: préstamo con 3 renovaciones
    ('2021110002', '104'),  -- Juan Sebastián Muñoz Pantoja: préstamo con reserva ajena
    ('2021110004', '105'),  -- Andrés Felipe Jojoa Gómez: puede renovar
    ('2021110005', '106'),  -- Laura Camila Insuasty Díaz
    ('2021110006', '107'),  -- Diego Alejandro Chicunque Muñoz
    ('2021110007', '108')   -- Paola Andrea Zambrano Erazo: tiene la reserva ajena
) AS m(viejo, nuevo)
WHERE u.codigo = m.viejo
  AND u.es_demo = true
  -- Seguridad: no pisar un código nuevo que ya pertenezca a otro usuario
  AND NOT EXISTS (SELECT 1 FROM public.usuarios otro WHERE otro.codigo = m.nuevo);

COMMIT;
