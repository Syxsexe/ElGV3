"""Estructura general: tablas, vistas, migraciones y datos iniciales."""
import migrar


def test_59_tablas_y_13_vistas(db):
    tablas = db.execute("""
        SELECT count(*) AS n FROM information_schema.tables
         WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
           AND table_name <> 'schema_migraciones'""").fetchone()["n"]
    vistas = db.execute(
        "SELECT count(*) AS n FROM information_schema.views WHERE table_schema = 'public'").fetchone()["n"]
    assert tablas == 59
    assert vistas == 13


def test_migrar_dos_veces_no_aplica_nada(url_prueba):
    assert migrar.aplicar(url_prueba, verbose=False) == []


def test_admin_tiene_todos_los_permisos_y_vendedor_ninguno(db):
    filas = db.execute("""
        SELECT r.nombre, count(rp.permiso_id) AS n
          FROM roles r LEFT JOIN rol_permisos rp ON rp.rol_id = r.id
         GROUP BY r.nombre""").fetchall()
    assert {r["nombre"]: r["n"] for r in filas} == {"admin": 12, "vendedor": 0}


def test_metodos_de_pago_caen_en_su_caja(db):
    filas = db.execute("""
        SELECT m.codigo, c.nombre FROM metodos_pago m JOIN cajas c ON c.id = m.caja_id""").fetchall()
    sembrados = {"efectivo": "Efectivo", "nequi": "Digital", "daviplata": "Digital",
                 "transferencia": "Digital", "tarjeta": "Digital"}
    assert {r["codigo"]: r["nombre"] for r in filas if r["codigo"] in sembrados} == sembrados


def test_divipola_completo(db):
    assert db.execute("SELECT count(*) AS n FROM municipios").fetchone()["n"] == 1122
    pasto = db.execute("""
        SELECT m.nombre, d.nombre AS depto FROM municipios m
          JOIN departamentos d ON d.id = m.departamento_id WHERE m.codigo = '52001'""").fetchone()
    assert pasto == {"nombre": "PASTO", "depto": "NARIÑO"}


def test_inscripcion_a_torneo_es_servicio_exento(db):
    fila = db.execute("""
        SELECT a.tipo, i.codigo FROM articulos a JOIN impuestos i ON i.id = a.impuesto_id
         WHERE a.nombre = 'Inscripción a torneo'""").fetchone()
    assert fila == {"tipo": "servicio", "codigo": "IVA0-EXENTO"}
    assert db.execute("SELECT count(*) AS n FROM servicios").fetchone()["n"] == 1
