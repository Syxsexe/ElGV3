-- 0001_terceros.sql — Grupo 3: clientes, proveedores y el propio negocio.
--
-- Va primero porque usuarios (grupo 1) apunta a terceros: un usuario del
-- sistema puede ser también cliente de fiado y quien recibe nómina.

CREATE TABLE tipos_identificacion (
    id      uuid PRIMARY KEY DEFAULT uuidv7(),
    codigo  text NOT NULL UNIQUE,
    nombre  text NOT NULL
);
COMMENT ON TABLE tipos_identificacion IS
    'Tipos de documento de identidad con su código DIAN (13 CC, 31 NIT…). '
    'CONSUMIDOR_FINAL ya no es un tipo: quien no da documento queda sin identificación.';

CREATE TABLE departamentos (
    id      uuid PRIMARY KEY DEFAULT uuidv7(),
    codigo  text NOT NULL UNIQUE CHECK (codigo ~ '^[0-9]{2}$'),
    nombre  text NOT NULL
);
COMMENT ON TABLE departamentos IS 'Departamentos de Colombia, código DIVIPOLA (DANE) de 2 dígitos.';

CREATE TABLE municipios (
    id               uuid PRIMARY KEY DEFAULT uuidv7(),
    codigo           text NOT NULL UNIQUE CHECK (codigo ~ '^[0-9]{5}$'),
    nombre           text NOT NULL,
    departamento_id  uuid NOT NULL REFERENCES departamentos
);
COMMENT ON TABLE municipios IS 'Municipios de Colombia, código DIVIPOLA (DANE) de 5 dígitos; la DIAN lo exige en la factura electrónica.';

CREATE TABLE terceros (
    id                      uuid        PRIMARY KEY DEFAULT uuidv7(),
    tipo_persona            text        NOT NULL DEFAULT 'natural'
                                        CHECK (tipo_persona IN ('natural', 'juridica')),
    nombre                  text        NOT NULL CHECK (btrim(nombre) <> ''),
    tipo_identificacion_id  uuid        REFERENCES tipos_identificacion,
    numero_identificacion   text        CHECK (btrim(numero_identificacion) <> ''),
    direccion               text,
    municipio_id            uuid        REFERENCES municipios,
    telefono                text,
    email                   text,
    responsable_iva         boolean,
    creado_en               timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT terceros_identificacion_completa
        CHECK ((tipo_identificacion_id IS NULL) = (numero_identificacion IS NULL)),
    CONSTRAINT terceros_identificacion_unica
        UNIQUE (tipo_identificacion_id, numero_identificacion)
);
COMMENT ON TABLE terceros IS
    'Toda persona o empresa con la que trata el negocio. Cliente y proveedor son roles '
    '(tablas clientes/proveedores) y un mismo tercero puede tener ambos.';
COMMENT ON COLUMN terceros.nombre IS 'Nombre completo o razón social. No es único: dos clientes pueden llamarse igual.';
COMMENT ON COLUMN terceros.numero_identificacion IS
    'Sin dígito de verificación: el DV del NIT se calcula. Va junto con tipo_identificacion_id o ninguno.';
COMMENT ON COLUMN terceros.responsable_iva IS 'NULL = sin dato (solo se exige al emitir factura electrónica).';

CREATE TABLE clientes (
    tercero_id      uuid          PRIMARY KEY REFERENCES terceros,
    limite_credito  numeric(14,2) NOT NULL DEFAULT 0 CHECK (limite_credito >= 0),
    dias_credito    integer       NOT NULL DEFAULT 30 CHECK (dias_credito > 0),
    activo          boolean       NOT NULL DEFAULT true
);
COMMENT ON TABLE clientes IS 'Rol de cliente de un tercero (subtipo 1:1). limite_credito = 0 significa sin fiado.';

CREATE TABLE proveedores (
    tercero_id  uuid    PRIMARY KEY REFERENCES terceros,
    contacto    text,
    activo      boolean NOT NULL DEFAULT true
);
COMMENT ON TABLE proveedores IS 'Rol de proveedor de un tercero (subtipo 1:1).';
COMMENT ON COLUMN proveedores.contacto IS 'Nombre de la persona de contacto (el teléfono va en terceros).';

CREATE TABLE responsabilidades_fiscales (
    id           uuid PRIMARY KEY DEFAULT uuidv7(),
    codigo       text NOT NULL UNIQUE,
    descripcion  text NOT NULL
);
COMMENT ON TABLE responsabilidades_fiscales IS 'Responsabilidades del RUT (O-13, O-15, O-23, O-47, R-99-PN).';

CREATE TABLE tercero_responsabilidades (
    tercero_id          uuid NOT NULL REFERENCES terceros,
    responsabilidad_id  uuid NOT NULL REFERENCES responsabilidades_fiscales,
    PRIMARY KEY (tercero_id, responsabilidad_id)
);
COMMENT ON TABLE tercero_responsabilidades IS 'Puente N:M: en el RUT una persona puede tener varias responsabilidades.';

CREATE TABLE empresa (
    id                          boolean PRIMARY KEY DEFAULT true CHECK (id),
    tercero_id                  uuid    NOT NULL UNIQUE REFERENCES terceros,
    regimen_tributario          text    NOT NULL DEFAULT 'ordinario'
                                        CHECK (regimen_tributario IN ('ordinario', 'simple')),
    responsable_inc             boolean NOT NULL DEFAULT false,
    precios_incluyen_impuestos  boolean NOT NULL DEFAULT true
);
COMMENT ON TABLE empresa IS
    'El propio negocio (una sola fila). Sus datos de NIT, nombre y municipio están en su tercero; '
    'terceros.responsable_iva de ese tercero decide si se discrimina IVA en ventas y documentos.';
