BEGIN;

CREATE TABLE IF NOT EXISTS public.salas (
    id serial PRIMARY KEY,
    slug varchar(50) NOT NULL UNIQUE,
    nombre varchar(200) NOT NULL,
    descripcion text,
    icono varchar(10),
    bibliotecario_nombre varchar(80) NOT NULL,
    bibliotecario_saludo text NOT NULL,
    orden integer NOT NULL DEFAULT 100
);

CREATE TABLE IF NOT EXISTS public.salas_programas (
    sala_id integer NOT NULL REFERENCES public.salas(id) ON DELETE CASCADE,
    programa varchar(160) NOT NULL,
    PRIMARY KEY (sala_id, programa)
);

ALTER TABLE public.material ADD COLUMN IF NOT EXISTS sala_id integer REFERENCES public.salas(id);

INSERT INTO public.salas (slug, nombre, descripcion, icono, bibliotecario_nombre, bibliotecario_saludo, orden)
VALUES
    ('ingenieria', 'Sala de Ingeniería y Tecnología', 'Ingeniería de Sistemas', '💻', 'Andrés', 'Bienvenido a la Sala de Ingeniería. Aquí están los libros de programación, redes, bases de datos e inteligencia artificial. ¿Qué buscas?', 1),
    ('agro-ambiental', 'Sala de Ciencias Agrarias y Ambientales', 'Ingeniería Agroforestal, Ingeniería Ambiental', '🌱', 'Rosa', 'Bienvenida a la Sala Agroambiental. Aquí están los materiales sobre suelo, cultivos, ecología y sostenibilidad. ¿Qué buscas?', 2),
    ('administracion', 'Sala de Administración y Negocios', 'Administración de Empresas', '📈', 'Camilo', 'Bienvenido a la Sala de Administración. Aquí están los libros de gestión, marketing y negocios. ¿Qué buscas?', 3),
    ('contaduria', 'Sala de Contaduría y Finanzas', 'Contaduría Pública', '🧾', 'Lucía', 'Bienvenida a la Sala de Contaduría. Aquí están los materiales de costos, finanzas y contabilidad. ¿Qué buscas?', 4),
    ('investigacion', 'Sala de Investigación y Escritura', 'Transversal (metodología, redacción)', '✍️', 'Elena', 'Bienvenida a la Sala de Investigación. Aquí están los materiales de metodología, redacción y tesis. ¿Qué buscas?', 5)
ON CONFLICT (slug) DO UPDATE
SET nombre = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion,
    icono = EXCLUDED.icono,
    bibliotecario_nombre = EXCLUDED.bibliotecario_nombre,
    bibliotecario_saludo = EXCLUDED.bibliotecario_saludo,
    orden = EXCLUDED.orden;

INSERT INTO public.salas_programas (sala_id, programa)
VALUES
    ((SELECT id FROM public.salas WHERE slug = 'ingenieria'), 'Ingeniería de Sistemas'),
    ((SELECT id FROM public.salas WHERE slug = 'agro-ambiental'), 'Ingeniería Agroforestal'),
    ((SELECT id FROM public.salas WHERE slug = 'agro-ambiental'), 'Ingeniería Ambiental'),
    ((SELECT id FROM public.salas WHERE slug = 'administracion'), 'Administración de Empresas'),
    ((SELECT id FROM public.salas WHERE slug = 'contaduria'), 'Contaduría Pública'),
    ((SELECT id FROM public.salas WHERE slug = 'investigacion'), 'Transversal')
ON CONFLICT (sala_id, programa) DO NOTHING;

UPDATE public.material AS m
SET sala_id = s.id
FROM public.salas AS s
JOIN public.salas_programas AS sp ON sp.sala_id = s.id
WHERE m.sala_id IS NULL
  AND lower(btrim(m.programa)) = lower(btrim(sp.programa));

UPDATE public.material AS m
SET sala_id = (SELECT s.id FROM public.salas AS s WHERE s.slug = 'investigacion')
WHERE m.sala_id IS NULL
  AND lower(btrim(COALESCE(m.programa, ''))) = 'transversal';

CREATE INDEX IF NOT EXISTS idx_material_sala_id ON public.material (sala_id);

COMMIT;
