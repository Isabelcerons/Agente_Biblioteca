-- Migración idempotente para PIN y sesiones autenticadas.
-- Se almacena solo el SHA-256 del token, nunca el token ni el PIN.

ALTER TABLE public.usuarios
    ADD COLUMN IF NOT EXISTS pin_hash text,
    ADD COLUMN IF NOT EXISTS intentos_fallidos int NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS bloqueado_hasta timestamptz;

CREATE TABLE IF NOT EXISTS public.sesiones (
    token_hash char(64) PRIMARY KEY,
    usuario_id int NOT NULL REFERENCES public.usuarios(id) ON DELETE CASCADE,
    creada timestamptz NOT NULL DEFAULT now(),
    expira timestamptz NOT NULL,
    cerrada timestamptz,
    user_agent text
);

CREATE INDEX IF NOT EXISTS idx_sesiones_usuario_id
    ON public.sesiones (usuario_id);
CREATE INDEX IF NOT EXISTS idx_sesiones_expira
    ON public.sesiones (expira);
