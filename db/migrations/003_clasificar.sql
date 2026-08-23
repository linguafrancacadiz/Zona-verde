-- Clasificación de un punto GPS. Réplica en SQL de zonaverde.clasificacion.clasificar.
--
-- Cualquier cambio aquí debe replicarse en el módulo Python y viceversa: el
-- criterio de aceptación (etl/zonaverde/validar.py) se ejecuta sobre la
-- implementación Python y es la que define el comportamiento correcto.

CREATE OR REPLACE FUNCTION zv_clasificar(
    p_punto              geography(POINT, 4326),
    p_precision_m        double precision,
    p_version_id         bigint,
    p_tolerancia_m       double precision DEFAULT 15,
    p_margen_ambiguedad  double precision DEFAULT 8,
    p_confianza_minima   smallint         DEFAULT 4,
    p_precision_maxima_m double precision DEFAULT 40
)
RETURNS TABLE (
    reportable  boolean,
    motivo      text,
    tipo        text,
    via         text,
    distancia_m double precision
)
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_radio      double precision;
    v_exclusion  record;
    v_mejor      record;
    v_siguiente  record;
BEGIN
    IF p_precision_m > p_precision_maxima_m THEN
        RETURN QUERY SELECT false, 'precision_insuficiente', NULL::text, NULL::text, NULL::double precision;
        RETURN;
    END IF;

    v_radio := p_tolerancia_m + LEAST(p_precision_m, p_precision_maxima_m);

    -- Las exclusiones (vado, carga y descarga, PMR, obras) se solapan a propósito
    -- con el tramo verde que las contiene: son una capa por encima, no un rival.
    SELECT z.via, ST_Distance(z.geom, p_punto) AS d
      INTO v_exclusion
      FROM zonas z
     WHERE z.version_id = p_version_id
       AND z.tipo = 'excluida'
       AND ST_DWithin(z.geom, p_punto, p_tolerancia_m)
     ORDER BY d
     LIMIT 1;

    IF FOUND THEN
        RETURN QUERY SELECT false, 'tramo_excluido', 'excluida', v_exclusion.via, v_exclusion.d;
        RETURN;
    END IF;

    SELECT z.tipo, z.via, z.confianza, ST_Distance(z.geom, p_punto) AS d
      INTO v_mejor
      FROM zonas z
     WHERE z.version_id = p_version_id
       AND z.tipo <> 'excluida'
       AND ST_DWithin(z.geom, p_punto, v_radio)
     ORDER BY d
     LIMIT 1;

    IF NOT FOUND THEN
        RETURN QUERY SELECT false, 'fuera_de_zona_regulada', NULL::text, NULL::text, NULL::double precision;
        RETURN;
    END IF;

    -- Candidato más cercano de OTRO tipo: si está prácticamente igual de cerca,
    -- no se decide por geometría — lo confirma la persona.
    SELECT z.tipo, ST_Distance(z.geom, p_punto) AS d
      INTO v_siguiente
      FROM zonas z
     WHERE z.version_id = p_version_id
       AND z.tipo <> 'excluida'
       AND z.tipo <> v_mejor.tipo
       AND ST_DWithin(z.geom, p_punto, v_radio)
     ORDER BY d
     LIMIT 1;

    IF FOUND AND v_siguiente.d - v_mejor.d < p_margen_ambiguedad THEN
        RETURN QUERY SELECT false, 'ambiguo', v_mejor.tipo, v_mejor.via, v_mejor.d;
        RETURN;
    END IF;

    IF v_mejor.tipo <> 'verde' THEN
        RETURN QUERY SELECT false, 'no_es_zona_verde', v_mejor.tipo, v_mejor.via, v_mejor.d;
        RETURN;
    END IF;

    IF v_mejor.confianza < p_confianza_minima THEN
        RETURN QUERY SELECT false, 'tramo_sin_verificar', v_mejor.tipo, v_mejor.via, v_mejor.d;
        RETURN;
    END IF;

    RETURN QUERY SELECT true, 'en_zona_verde', v_mejor.tipo, v_mejor.via, v_mejor.d;
END;
$$;
