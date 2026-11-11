-- Recoloca los datos operativos de demo para que siempre reflejen el estado esperado.
-- Se ejecuta en una sola transacción desde refrescar_demo.py.

WITH reservas_101 AS (
    SELECT r.id, r.ejemplar_id
    FROM public.reservas AS r
    JOIN public.usuarios AS u ON u.id = r.usuario_id
    WHERE u.codigo = '101' AND r.estado = 'activa'
)
UPDATE public.reservas AS r
SET estado = 'cancelada'
FROM reservas_101 AS s
WHERE r.id = s.id;

WITH reservas_101 AS (
    SELECT r.id, r.ejemplar_id
    FROM public.reservas AS r
    JOIN public.usuarios AS u ON u.id = r.usuario_id
    WHERE u.codigo = '101' AND r.estado = 'activa'
)
UPDATE public.ejemplares AS e
SET estado = 'disponible'
FROM reservas_101 AS s
WHERE e.id = s.ejemplar_id
  AND e.estado = 'reservado';

DELETE FROM public.multas AS m
USING public.usuarios AS u
WHERE m.usuario_id = u.id
  AND u.codigo = '101';

WITH prestamos_101 AS (
    SELECT p.id, p.ejemplar_id
    FROM public.prestamos AS p
    JOIN public.usuarios AS u ON u.id = p.usuario_id
    WHERE u.codigo = '101' AND p.estado = 'activo'
)
UPDATE public.prestamos AS p
SET estado = 'devuelto',
    fecha_vencimiento = current_date
FROM prestamos_101 AS s
WHERE p.id = s.id;

WITH prestamos_101 AS (
    SELECT p.id, p.ejemplar_id
    FROM public.prestamos AS p
    JOIN public.usuarios AS u ON u.id = p.usuario_id
    WHERE u.codigo = '101' AND p.estado = 'activo'
)
UPDATE public.ejemplares AS e
SET estado = 'disponible'
FROM prestamos_101 AS s
WHERE e.id = s.ejemplar_id
  AND e.estado = 'prestado';

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Fundamentos de seguridad en redes'
    WHERE u.codigo = '102'
),
prestamo AS (
    SELECT p.id
    FROM public.prestamos AS p
    JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
    JOIN meta AS m ON m.usuario_id = p.usuario_id AND e.material_id = m.material_id
    WHERE p.estado IN ('activo', 'vencido')
    ORDER BY p.id DESC
    LIMIT 1
)
UPDATE public.prestamos AS p
SET fecha_prestamo = current_date - 13,
    fecha_vencimiento = current_date - 5,
    renovaciones = 0,
    estado = 'vencido'
FROM meta
WHERE p.usuario_id = meta.usuario_id
  AND p.ejemplar_id IN (
      SELECT e.id
      FROM public.ejemplares AS e
      WHERE e.material_id = meta.material_id
  )
  AND p.id IN (SELECT id FROM prestamo);

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Fundamentos de seguridad en redes'
    WHERE u.codigo = '102'
)
INSERT INTO public.prestamos (ejemplar_id, usuario_id, fecha_prestamo, fecha_vencimiento, renovaciones, estado)
SELECT e.id, meta.usuario_id, current_date - 13, current_date - 5, 0, 'vencido'
FROM meta
CROSS JOIN LATERAL (
    SELECT e.id
    FROM public.ejemplares AS e
    WHERE e.material_id = meta.material_id
    ORDER BY e.codigo_barras
    LIMIT 1
) AS e
WHERE NOT EXISTS (
    SELECT 1
    FROM public.prestamos AS p
    JOIN public.ejemplares AS e2 ON e2.id = p.ejemplar_id
    WHERE p.usuario_id = meta.usuario_id
      AND e2.material_id = meta.material_id
      AND p.estado IN ('activo', 'vencido')
);

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Fundamentos de seguridad en redes'
    WHERE u.codigo = '102'
),
prestamo AS (
    SELECT p.id
    FROM public.prestamos AS p
    JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
    JOIN meta AS m ON m.usuario_id = p.usuario_id AND e.material_id = m.material_id
    WHERE p.estado IN ('activo', 'vencido')
    ORDER BY p.id DESC
    LIMIT 1
)
UPDATE public.multas AS m
SET valor = 5000,
    dias = 5,
    estado = 'pendiente',
    fecha = current_date - 5
FROM prestamo
WHERE m.usuario_id = (SELECT usuario_id FROM public.usuarios WHERE codigo = '102')
  AND m.prestamo_id = prestamo.id;

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Fundamentos de seguridad en redes'
    WHERE u.codigo = '102'
),
prestamo AS (
    SELECT p.id
    FROM public.prestamos AS p
    JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
    JOIN meta AS m ON m.usuario_id = p.usuario_id AND e.material_id = m.material_id
    WHERE p.estado IN ('activo', 'vencido')
    ORDER BY p.id DESC
    LIMIT 1
)
INSERT INTO public.multas (usuario_id, prestamo_id, valor, dias, estado, fecha)
SELECT u.id, prestamo.id, 5000, 5, 'pendiente', current_date - 5
FROM public.usuarios AS u
CROSS JOIN prestamo
WHERE u.codigo = '102'
  AND NOT EXISTS (
      SELECT 1
      FROM public.multas AS m
      WHERE m.usuario_id = u.id
        AND m.prestamo_id = prestamo.id
  );

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Cálculo de una variable'
    WHERE u.codigo = '103'
),
prestamo AS (
    SELECT p.id
    FROM public.prestamos AS p
    JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
    JOIN meta AS m ON m.usuario_id = p.usuario_id AND e.material_id = m.material_id
    WHERE p.estado IN ('activo', 'vencido')
    ORDER BY p.id DESC
    LIMIT 1
)
UPDATE public.prestamos AS p
SET fecha_prestamo = current_date - 2,
    fecha_vencimiento = current_date + 6,
    renovaciones = 3,
    estado = 'activo'
FROM meta
WHERE p.usuario_id = meta.usuario_id
  AND p.ejemplar_id IN (
      SELECT e.id FROM public.ejemplares AS e WHERE e.material_id = meta.material_id
  )
  AND p.id IN (SELECT id FROM prestamo);

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Cálculo de una variable'
    WHERE u.codigo = '103'
)
INSERT INTO public.prestamos (ejemplar_id, usuario_id, fecha_prestamo, fecha_vencimiento, renovaciones, estado)
SELECT e.id, meta.usuario_id, current_date - 2, current_date + 6, 3, 'activo'
FROM meta
CROSS JOIN LATERAL (
    SELECT e.id
    FROM public.ejemplares AS e
    WHERE e.material_id = meta.material_id
    ORDER BY e.codigo_barras
    LIMIT 1
) AS e
WHERE NOT EXISTS (
    SELECT 1
    FROM public.prestamos AS p
    JOIN public.ejemplares AS e2 ON e2.id = p.ejemplar_id
    WHERE p.usuario_id = meta.usuario_id
      AND e2.material_id = meta.material_id
      AND p.estado IN ('activo', 'vencido')
);

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Redes de computadoras'
    WHERE u.codigo = '104'
),
prestamo AS (
    SELECT p.id
    FROM public.prestamos AS p
    JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
    JOIN meta AS m ON m.usuario_id = p.usuario_id AND e.material_id = m.material_id
    WHERE p.estado IN ('activo', 'vencido')
    ORDER BY p.id DESC
    LIMIT 1
)
UPDATE public.prestamos AS p
SET fecha_prestamo = current_date - 1,
    fecha_vencimiento = current_date + 7,
    renovaciones = 1,
    estado = 'activo'
FROM meta
WHERE p.usuario_id = meta.usuario_id
  AND p.ejemplar_id IN (
      SELECT e.id FROM public.ejemplares AS e WHERE e.material_id = meta.material_id
  )
  AND p.id IN (SELECT id FROM prestamo);

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Redes de computadoras'
    WHERE u.codigo = '104'
)
INSERT INTO public.prestamos (ejemplar_id, usuario_id, fecha_prestamo, fecha_vencimiento, renovaciones, estado)
SELECT e.id, meta.usuario_id, current_date - 1, current_date + 7, 1, 'activo'
FROM meta
CROSS JOIN LATERAL (
    SELECT e.id
    FROM public.ejemplares AS e
    WHERE e.material_id = meta.material_id
    ORDER BY e.codigo_barras
    LIMIT 1
) AS e
WHERE NOT EXISTS (
    SELECT 1
    FROM public.prestamos AS p
    JOIN public.ejemplares AS e2 ON e2.id = p.ejemplar_id
    WHERE p.usuario_id = meta.usuario_id
      AND e2.material_id = meta.material_id
      AND p.estado IN ('activo', 'vencido')
);

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Ingeniería de software'
    WHERE u.codigo = '105'
),
prestamo AS (
    SELECT p.id
    FROM public.prestamos AS p
    JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
    JOIN meta AS m ON m.usuario_id = p.usuario_id AND e.material_id = m.material_id
    WHERE p.estado IN ('activo', 'vencido')
    ORDER BY p.id DESC
    LIMIT 1
)
UPDATE public.prestamos AS p
SET fecha_prestamo = current_date - 3,
    fecha_vencimiento = current_date + 5,
    renovaciones = 0,
    estado = 'activo'
FROM meta
WHERE p.usuario_id = meta.usuario_id
  AND p.ejemplar_id IN (
      SELECT e.id FROM public.ejemplares AS e WHERE e.material_id = meta.material_id
  )
  AND p.id IN (SELECT id FROM prestamo);

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Ingeniería de software'
    WHERE u.codigo = '105'
)
INSERT INTO public.prestamos (ejemplar_id, usuario_id, fecha_prestamo, fecha_vencimiento, renovaciones, estado)
SELECT e.id, meta.usuario_id, current_date - 3, current_date + 5, 0, 'activo'
FROM meta
CROSS JOIN LATERAL (
    SELECT e.id
    FROM public.ejemplares AS e
    WHERE e.material_id = meta.material_id
    ORDER BY e.codigo_barras
    LIMIT 1
) AS e
WHERE NOT EXISTS (
    SELECT 1
    FROM public.prestamos AS p
    JOIN public.ejemplares AS e2 ON e2.id = p.ejemplar_id
    WHERE p.usuario_id = meta.usuario_id
      AND e2.material_id = meta.material_id
      AND p.estado IN ('activo', 'vencido')
);

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Fundamentos de bases de datos'
    WHERE u.codigo = '106'
),
prestamo AS (
    SELECT p.id
    FROM public.prestamos AS p
    JOIN public.ejemplares AS e ON e.id = p.ejemplar_id
    JOIN meta AS m ON m.usuario_id = p.usuario_id AND e.material_id = m.material_id
    WHERE p.estado IN ('activo', 'vencido')
    ORDER BY p.id DESC
    LIMIT 1
)
UPDATE public.prestamos AS p
SET fecha_prestamo = current_date - 4,
    fecha_vencimiento = current_date + 8,
    renovaciones = 0,
    estado = 'activo'
FROM meta
WHERE p.usuario_id = meta.usuario_id
  AND p.ejemplar_id IN (
      SELECT e.id FROM public.ejemplares AS e WHERE e.material_id = meta.material_id
  )
  AND p.id IN (SELECT id FROM prestamo);

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Fundamentos de bases de datos'
    WHERE u.codigo = '106'
)
INSERT INTO public.prestamos (ejemplar_id, usuario_id, fecha_prestamo, fecha_vencimiento, renovaciones, estado)
SELECT e.id, meta.usuario_id, current_date - 4, current_date + 8, 0, 'activo'
FROM meta
CROSS JOIN LATERAL (
    SELECT e.id
    FROM public.ejemplares AS e
    WHERE e.material_id = meta.material_id
    ORDER BY e.codigo_barras
    LIMIT 1
) AS e
WHERE NOT EXISTS (
    SELECT 1
    FROM public.prestamos AS p
    JOIN public.ejemplares AS e2 ON e2.id = p.ejemplar_id
    WHERE p.usuario_id = meta.usuario_id
      AND e2.material_id = meta.material_id
      AND p.estado IN ('activo', 'vencido')
);

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Redes de computadoras'
    WHERE u.codigo = '108'
),
reserva AS (
    SELECT r.id, r.ejemplar_id
    FROM public.reservas AS r
    JOIN meta AS m ON m.usuario_id = r.usuario_id AND r.material_id = m.material_id
    WHERE r.estado IN ('activa', 'vencida', 'cancelada')
    ORDER BY r.id DESC
    LIMIT 1
)
UPDATE public.reservas AS r
SET fecha_reserva = now(),
    expira_en = now() + interval '48 hours',
    ejemplar_id = NULL,
    estado = 'activa'
FROM reserva
WHERE r.id = reserva.id;

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Redes de computadoras'
    WHERE u.codigo = '108'
),
reserva AS (
    SELECT r.id, r.ejemplar_id
    FROM public.reservas AS r
    JOIN meta AS m ON m.usuario_id = r.usuario_id AND r.material_id = m.material_id
    WHERE r.estado IN ('activa', 'vencida', 'cancelada')
    ORDER BY r.id DESC
    LIMIT 1
)
UPDATE public.ejemplares AS e
SET estado = 'disponible'
FROM reserva
WHERE reserva.ejemplar_id IS NOT NULL
  AND e.id = reserva.ejemplar_id
  AND e.estado = 'reservado';

WITH meta AS (
    SELECT u.id AS usuario_id, m.id AS material_id
    FROM public.usuarios AS u
    JOIN public.material AS m ON m.titulo = 'Redes de computadoras'
    WHERE u.codigo = '108'
)
INSERT INTO public.reservas (usuario_id, material_id, ejemplar_id, fecha_reserva, expira_en, estado)
SELECT meta.usuario_id, meta.material_id, NULL, now(), now() + interval '48 hours', 'activa'
FROM meta
WHERE NOT EXISTS (
    SELECT 1
    FROM public.reservas AS r
    WHERE r.usuario_id = meta.usuario_id
      AND r.material_id = meta.material_id
      AND r.estado = 'activa'
);

UPDATE public.ejemplares AS e
SET estado = 'prestado'
FROM public.prestamos AS p
WHERE p.ejemplar_id = e.id
  AND p.estado IN ('activo', 'vencido');

-- Reapertura de ejemplares reservados que absurdamente quedaron bloqueados.
UPDATE public.ejemplares AS e
SET estado = 'disponible'
WHERE e.estado = 'reservado'
  AND NOT EXISTS (
      SELECT 1
      FROM public.reservas AS r
      WHERE r.ejemplar_id = e.id
        AND r.estado = 'activa'
  );
