-- Tramos de estacionamiento regulado.
--
-- El dataset se versiona: los tramos nunca se modifican en sitio. Cuando Emasa
-- repinta una calle se publica una versión nueva y la anterior se conserva, de
-- modo que un reporte antiguo siga siendo defendible frente a la cartografía
-- que estaba en vigor cuando se levantó.

CREATE TABLE IF NOT EXISTS zonas_version (
    id           bigserial PRIMARY KEY,
    etiqueta     text        NOT NULL UNIQUE,      -- p. ej. '0.1.0'
    notas        text,
    publicada_en timestamptz NOT NULL DEFAULT now(),
    vigente      boolean     NOT NULL DEFAULT false
);

-- Una sola versión vigente a la vez.
CREATE UNIQUE INDEX IF NOT EXISTS zonas_version_una_vigente
    ON zonas_version ((true)) WHERE vigente;

CREATE TABLE IF NOT EXISTS zonas (
    id                 bigserial PRIMARY KEY,
    version_id         bigint      NOT NULL REFERENCES zonas_version(id) ON DELETE CASCADE,
    tramo_id           text        NOT NULL,       -- estable entre versiones
    tipo               text        NOT NULL CHECK (tipo IN ('verde','naranja','azul','excluida')),
    ambito             text        NOT NULL DEFAULT '',
    via                text        NOT NULL,
    via_clave          text        NOT NULL,       -- forma canónica para emparejar
    lado               text        NOT NULL DEFAULT 'ambos'
                                   CHECK (lado IN ('ambos','pares','impares')),
    geom               geography(LINESTRING, 4326) NOT NULL,
    -- 1 sin emparejar · 2 calle completa · 3 recorte automático
    -- 4 contrastado o revisado · 5 verificado en campo con foto
    confianza          smallint    NOT NULL CHECK (confianza BETWEEN 1 AND 5),
    metodo             text        NOT NULL DEFAULT '',
    fuente             text        NOT NULL DEFAULT '',
    fecha_verificacion date,
    foto_senal         text,
    observaciones      text,
    UNIQUE (version_id, tramo_id)
);

CREATE INDEX IF NOT EXISTS zonas_geom_idx    ON zonas USING GIST (geom);
CREATE INDEX IF NOT EXISTS zonas_version_idx ON zonas (version_id);
CREATE INDEX IF NOT EXISTS zonas_tipo_idx    ON zonas (tipo);

-- Un tramo verificado en campo debe llevar fecha; sin fecha no llega a confianza 5.
ALTER TABLE zonas DROP CONSTRAINT IF EXISTS zonas_verificacion_coherente;
ALTER TABLE zonas ADD CONSTRAINT zonas_verificacion_coherente
    CHECK (confianza < 5 OR fecha_verificacion IS NOT NULL);

COMMENT ON TABLE  zonas IS 'Tramos de estacionamiento regulado, versionados.';
COMMENT ON COLUMN zonas.confianza IS 'La app sólo denuncia a partir de 4.';
