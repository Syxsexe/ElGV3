-- 0002_usuarios.sql — Grupo 1: usuarios, roles, permisos y auditoría.

-- Usada por todas las tablas que solo admiten INSERT (bitácora y movimientos).
CREATE FUNCTION fn_solo_insercion() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% es de solo inserción: no se permite %', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'restrict_violation',
              HINT = 'Los movimientos se corrigen con un reverso, no editando ni borrando.';
END $$;

CREATE TABLE roles (
    id           uuid PRIMARY KEY DEFAULT uuidv7(),
    nombre       text NOT NULL UNIQUE,
    descripcion  text
);

CREATE TABLE permisos (
    id           uuid PRIMARY KEY DEFAULT uuidv7(),
    codigo       text NOT NULL UNIQUE CHECK (codigo ~ '^[a-z_]+\.[a-z_]+$'),
    descripcion  text NOT NULL
);
COMMENT ON TABLE permisos IS
    'Permisos como datos, no como código: se asignan a roles sin tocar el programa. '
    'El código consulta por codigo (ej. creditos.condonar).';

CREATE TABLE rol_permisos (
    rol_id      uuid NOT NULL REFERENCES roles    ON DELETE CASCADE,
    permiso_id  uuid NOT NULL REFERENCES permisos ON DELETE CASCADE,
    PRIMARY KEY (rol_id, permiso_id)
);

CREATE TABLE usuarios (
    id               uuid        PRIMARY KEY DEFAULT uuidv7(),
    usuario          text        NOT NULL UNIQUE CHECK (btrim(usuario) <> ''),
    contrasena_hash  text        NOT NULL,
    rol_id           uuid        NOT NULL REFERENCES roles,
    tercero_id       uuid        UNIQUE REFERENCES terceros,
    activo           boolean     NOT NULL DEFAULT true,
    creado_en        timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE usuarios IS 'Nunca se borran (los referencia el historial): se desactivan con activo.';
COMMENT ON COLUMN usuarios.tercero_id IS
    'La persona detrás del usuario (si es también cliente de fiado o recibe nómina). Una persona, a lo sumo un usuario.';

CREATE TABLE auditoria (
    id          uuid        PRIMARY KEY DEFAULT uuidv7(),
    creado_en   timestamptz NOT NULL DEFAULT now(),
    usuario_id  uuid        REFERENCES usuarios,
    accion      text        NOT NULL CHECK (accion IN (
                    'login', 'caja', 'venta', 'cuenta', 'credito', 'gasto', 'compra',
                    'inventario', 'cliente', 'torneo', 'documento', 'usuario', 'sistema')),
    detalle     text,
    entidad     text,
    entidad_id  uuid,
    CONSTRAINT auditoria_referencia_completa CHECK ((entidad IS NULL) = (entidad_id IS NULL))
);
COMMENT ON TABLE auditoria IS 'Bitácora de solo inserción: un trigger bloquea UPDATE, DELETE y TRUNCATE.';
COMMENT ON COLUMN auditoria.usuario_id IS 'NULL = evento del sistema (sin sesión, ej. una migración).';
COMMENT ON COLUMN auditoria.entidad IS
    'Tabla del registro auditado; junto con entidad_id. Sin FK: apunta a cualquier tabla.';

CREATE TRIGGER auditoria_solo_insercion
    BEFORE UPDATE OR DELETE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION fn_solo_insercion();
CREATE TRIGGER auditoria_sin_truncate
    BEFORE TRUNCATE ON auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION fn_solo_insercion();
