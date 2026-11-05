-- Habilita tesis completas y cargas asíncronas del repositorio.
-- Ejecutar conectado a biblioteca_agente como agente_biblio.

DO $$
DECLARE
    restriccion record;
BEGIN
    FOR restriccion IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'conocimiento.documentos'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) ILIKE '%tipo%'
    LOOP
        EXECUTE format(
            'ALTER TABLE conocimiento.documentos DROP CONSTRAINT %I',
            restriccion.conname
        );
    END LOOP;
END;
$$;

ALTER TABLE conocimiento.documentos
    ADD CONSTRAINT documentos_tipo_check
    CHECK (tipo IN (
        'reglamento', 'apa', 'ieee', 'faq', 'guia_bd',
        'resumen_tesis', 'resena_libro', 'tesis_completa'
    ));

ALTER TABLE public.material
    ADD COLUMN IF NOT EXISTS archivo_pdf text,
    ADD COLUMN IF NOT EXISTS subido_por int REFERENCES public.usuarios(id),
    ADD COLUMN IF NOT EXISTS subido_en timestamptz;

CREATE TABLE IF NOT EXISTS public.cargas_tesis (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id int REFERENCES public.usuarios(id),
    material_id int REFERENCES public.material(id),
    etapa text NOT NULL,
    avance int NOT NULL DEFAULT 0,
    total int NOT NULL DEFAULT 0,
    mensaje text,
    error text,
    creada timestamptz DEFAULT now(),
    actualizada timestamptz DEFAULT now()
);
