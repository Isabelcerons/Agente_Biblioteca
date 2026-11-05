-- Esquema transaccional y vectorial de la biblioteca.
-- Ejecutar conectado a biblioteca_agente como agente_biblio.

CREATE TABLE IF NOT EXISTS public.usuarios (
    id serial PRIMARY KEY,
    codigo varchar(20) UNIQUE NOT NULL,
    nombre varchar(160) NOT NULL,
    tipo varchar(20) NOT NULL CHECK (tipo IN ('estudiante', 'docente')),
    programa varchar(160),
    email varchar(255),
    activo boolean NOT NULL DEFAULT true,
    es_demo boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS public.material (
    id serial PRIMARY KEY,
    titulo text NOT NULL,
    autor text NOT NULL,
    anio integer,
    tipo varchar(30) NOT NULL CHECK (tipo IN ('libro', 'tesis', 'articulo', 'recurso_digital')),
    tema text,
    programa varchar(160),
    editorial text,
    isbn varchar(32),
    descripcion_corta text,
    es_demo boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS public.ejemplares (
    id serial PRIMARY KEY,
    material_id integer NOT NULL REFERENCES public.material(id),
    codigo_barras varchar(32) UNIQUE NOT NULL,
    estante varchar(32),
    estado varchar(20) NOT NULL DEFAULT 'disponible'
        CHECK (estado IN ('disponible', 'prestado', 'reservado', 'mantenimiento'))
);

CREATE TABLE IF NOT EXISTS public.prestamos (
    id serial PRIMARY KEY,
    ejemplar_id integer NOT NULL REFERENCES public.ejemplares(id),
    usuario_id integer NOT NULL REFERENCES public.usuarios(id),
    fecha_prestamo date NOT NULL DEFAULT current_date,
    fecha_vencimiento date NOT NULL,
    renovaciones integer NOT NULL DEFAULT 0 CHECK (renovaciones BETWEEN 0 AND 3),
    estado varchar(20) NOT NULL DEFAULT 'activo'
        CHECK (estado IN ('activo', 'devuelto', 'vencido'))
);

CREATE TABLE IF NOT EXISTS public.devoluciones (
    id serial PRIMARY KEY,
    prestamo_id integer UNIQUE NOT NULL REFERENCES public.prestamos(id),
    fecha_devolucion date,
    dias_retraso integer DEFAULT 0
);

CREATE TABLE IF NOT EXISTS public.multas (
    id serial PRIMARY KEY,
    usuario_id integer NOT NULL REFERENCES public.usuarios(id),
    prestamo_id integer NOT NULL REFERENCES public.prestamos(id),
    valor numeric(10, 2) CHECK (valor >= 0),
    dias integer,
    estado varchar(20) NOT NULL DEFAULT 'pendiente'
        CHECK (estado IN ('pendiente', 'pagada')),
    fecha date DEFAULT current_date
);

CREATE TABLE IF NOT EXISTS public.reservas (
    id serial PRIMARY KEY,
    usuario_id integer NOT NULL REFERENCES public.usuarios(id),
    material_id integer NOT NULL REFERENCES public.material(id),
    ejemplar_id integer REFERENCES public.ejemplares(id),
    fecha_reserva timestamptz DEFAULT now(),
    expira_en timestamptz NOT NULL DEFAULT now() + interval '48 hours',
    estado varchar(20) NOT NULL DEFAULT 'activa'
        CHECK (estado IN ('activa', 'cumplida', 'vencida', 'cancelada'))
);

CREATE TABLE IF NOT EXISTS public.conversaciones (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id integer REFERENCES public.usuarios(id) ON DELETE SET NULL,
    canal varchar(20) NOT NULL DEFAULT 'texto' CHECK (canal IN ('texto', 'voz')),
    estado jsonb NOT NULL DEFAULT '{}'::jsonb,
    creada timestamptz NOT NULL DEFAULT now(),
    actualizada timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.mensajes (
    id bigserial PRIMARY KEY,
    conversacion_id uuid NOT NULL REFERENCES public.conversaciones(id) ON DELETE CASCADE,
    rol varchar(20) NOT NULL CHECK (rol IN ('user', 'assistant', 'tool')),
    contenido text,
    creado timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.bitacora_agente (
    id bigserial PRIMARY KEY,
    conversacion_id uuid REFERENCES public.conversaciones(id) ON DELETE SET NULL,
    entrada text,
    es_voz boolean DEFAULT false,
    intencion text,
    herramienta text,
    fragmentos jsonb DEFAULT '[]'::jsonb,
    respuesta text,
    error text,
    t_stt_ms integer,
    t_embedding_ms integer,
    t_busqueda_ms integer,
    t_llm_ms integer,
    t_tts_ms integer,
    t_total_ms integer,
    creado timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.parametros (
    clave text PRIMARY KEY,
    valor text,
    descripcion text
);

INSERT INTO public.parametros (clave, valor, descripcion)
VALUES
    ('dias_prestamo', '8', 'Duración de un préstamo en días.'),
    ('max_renovaciones', '3', 'Número máximo de renovaciones por préstamo.'),
    ('multa_por_dia', '1000', 'Valor de la multa por cada día de retraso.'),
    ('horas_reserva', '48', 'Duración de una reserva en horas.')
ON CONFLICT (clave) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_material_titulo ON public.material (titulo);
CREATE INDEX IF NOT EXISTS idx_material_autor ON public.material (autor);
CREATE INDEX IF NOT EXISTS idx_material_tema ON public.material (tema);
CREATE INDEX IF NOT EXISTS idx_ejemplares_material_id ON public.ejemplares (material_id);
CREATE INDEX IF NOT EXISTS idx_prestamos_usuario_id ON public.prestamos (usuario_id);
CREATE INDEX IF NOT EXISTS idx_multas_usuario_estado ON public.multas (usuario_id, estado);
CREATE INDEX IF NOT EXISTS idx_reservas_material_estado ON public.reservas (material_id, estado);
CREATE INDEX IF NOT EXISTS idx_mensajes_conversacion_id ON public.mensajes (conversacion_id);
CREATE INDEX IF NOT EXISTS idx_bitacora_agente_creado ON public.bitacora_agente (creado DESC);

CREATE OR REPLACE VIEW public.v_disponibilidad AS
SELECT
    m.id AS material_id,
    m.titulo,
    m.autor,
    m.tipo,
    count(e.id) AS total,
    count(e.id) FILTER (WHERE e.estado = 'disponible') AS disponibles,
    count(e.id) FILTER (WHERE e.estado = 'prestado') AS prestados,
    count(e.id) FILTER (WHERE e.estado = 'reservado') AS reservados
FROM public.material AS m
LEFT JOIN public.ejemplares AS e ON e.material_id = m.id
GROUP BY m.id, m.titulo, m.autor, m.tipo;

CREATE TABLE IF NOT EXISTS conocimiento.documentos (
    id serial PRIMARY KEY,
    titulo text NOT NULL,
    tipo varchar(20) NOT NULL
        CHECK (tipo IN ('reglamento', 'apa', 'ieee', 'faq', 'guia_bd', 'resumen_tesis', 'resena_libro')),
    fuente text NOT NULL UNIQUE,
    material_id integer REFERENCES public.material(id),
    hash_contenido varchar(64) NOT NULL,
    creado timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conocimiento.fragmentos (
    id bigserial PRIMARY KEY,
    documento_id integer NOT NULL REFERENCES conocimiento.documentos(id) ON DELETE CASCADE,
    orden integer NOT NULL,
    seccion text,
    texto text NOT NULL,
    embedding vector(768) NOT NULL,
    UNIQUE (documento_id, orden)
);

CREATE INDEX IF NOT EXISTS idx_fragmentos_embedding
    ON conocimiento.fragmentos USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS conocimiento.mapa_pca (
    id smallint PRIMARY KEY CHECK (id = 1),
    media vector(768) NOT NULL,
    comp1 vector(768) NOT NULL,
    comp2 vector(768) NOT NULL,
    varianza_explicada real[],
    n_materiales int,
    firma text,
    calculado timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conocimiento.mapa_materiales (
    material_id int PRIMARY KEY
        REFERENCES public.material(id) ON DELETE CASCADE,
    x real NOT NULL,
    y real NOT NULL,
    embedding_medio vector(768) NOT NULL,
    calculado timestamptz DEFAULT now()
);
