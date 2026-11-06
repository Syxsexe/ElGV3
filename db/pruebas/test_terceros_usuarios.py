"""Grupos 1 y 3: terceros, empresa, usuarios y auditoría."""
from ayudas import falla


def test_identificacion_va_completa_o_no_va(db, f):
    tipo = f.id_de("tipos_identificacion", "codigo", "13")
    with falla(db, "terceros_identificacion_completa"):
        db.execute("INSERT INTO terceros (nombre, tipo_identificacion_id) VALUES ('Ana', %s)", (tipo,))
    with falla(db, "terceros_identificacion_completa"):
        db.execute("INSERT INTO terceros (nombre, numero_identificacion) VALUES ('Ana', '123')")
    f.tercero("Sin cédula")  # sin ninguno de los dos: válido


def test_identificacion_unica_pero_varios_sin_documento(db, f):
    f.tercero("Ana", documento="1001")
    with falla(db, "terceros_identificacion_unica"):
        f.tercero("Otra Ana", documento="1001")
    f.tercero("Pedro")
    f.tercero("Pedro")  # mismo nombre, sin documento: válido


def test_empresa_es_una_sola_fila(db, f):
    db.execute("INSERT INTO empresa (tercero_id) VALUES (%s)", (f.tercero("El G"),))
    with falla(db, "empresa_pkey"):
        db.execute("INSERT INTO empresa (tercero_id) VALUES (%s)", (f.tercero("Otra"),))
    with falla(db, "empresa_id_check"):
        db.execute("INSERT INTO empresa (id, tercero_id) VALUES (false, %s)", (f.tercero("Otra"),))


def test_un_tercero_tiene_a_lo_sumo_un_usuario(db, f):
    persona = f.tercero("Saavedra")
    f.usuario(tercero_id=persona)
    with falla(db, "usuarios_tercero_id_key"):
        f.usuario(tercero_id=persona)


def test_auditoria_solo_admite_insercion(db, f):
    fila = db.execute(
        "INSERT INTO auditoria (usuario_id, accion, detalle) VALUES (%s, 'venta', 'x') RETURNING id",
        (f.usuario(),)).fetchone()
    with falla(db, "solo inserción"):
        db.execute("UPDATE auditoria SET detalle = 'y' WHERE id = %s", (fila["id"],))
    with falla(db, "solo inserción"):
        db.execute("DELETE FROM auditoria WHERE id = %s", (fila["id"],))
    with falla(db, "solo inserción"):
        db.execute("TRUNCATE auditoria")


def test_auditoria_referencia_completa_y_accion_valida(db):
    db.execute("INSERT INTO auditoria (accion) VALUES ('sistema')")  # evento sin usuario
    with falla(db, "auditoria_referencia_completa"):
        db.execute("INSERT INTO auditoria (accion, entidad) VALUES ('venta', 'ventas')")
    with falla(db, "auditoria_accion_check"):
        db.execute("INSERT INTO auditoria (accion) VALUES ('produccion')")


def test_consumidor_final_marcado_y_unico(db, f):
    fila = db.execute("SELECT nombre, numero_identificacion FROM terceros WHERE es_consumidor_final").fetchone()
    assert fila == {"nombre": "CONSUMIDOR FINAL", "numero_identificacion": "222222222222"}
    with falla(db, "terceros_un_consumidor_final"):
        db.execute("UPDATE terceros SET es_consumidor_final = true WHERE id = %s", (f.tercero("Otro"),))
