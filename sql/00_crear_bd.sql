-- Crea el rol, la base de datos y los esquemas iniciales.
-- Ejecución: psql -U postgres -v app_password='contraseña' -f sql/00_crear_bd.sql

SELECT format('CREATE ROLE agente_biblio LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = 'agente_biblio'
)
\gexec

SELECT format(
    'CREATE DATABASE biblioteca_agente OWNER agente_biblio ENCODING %L',
    'UTF8'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_database WHERE datname = 'biblioteca_agente'
)
\gexec

\connect biblioteca_agente

CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS conocimiento AUTHORIZATION agente_biblio;
GRANT ALL ON SCHEMA public TO agente_biblio;
ALTER SCHEMA public OWNER TO agente_biblio;
