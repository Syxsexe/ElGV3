"""
modules/cocina_datos.py — El G POS
Datos canónicos de la cocina extraídos del APU ("Fichas tecnicas cocina").
Fuente ÚNICA para poblar la base (seed) y para generar el Excel importable,
así nunca divergen.

Modelo de 3 niveles (la BD lo aplana con la tabla receta_preparacion):
  • CRUDOS       → ingredientes que se compran (insumos "hoja").
  • PREPARACIONES→ se FABRICAN a partir de crudos y/o otras preparaciones
                   (rellenos, salsas, masa, adobo…). Cada una tiene rendimiento
                   por lote y su propia receta. Se guardan como insumos.
  • PLATOS       → productos de cocina que se venden; consumen porciones de
                   preparaciones + algunos crudos directos.

Producción "por niveles": el adobo y la salsa búfalo son preparaciones que se
usan DENTRO de otras (filete apanado, alitas, relleno picante). Se preparan
aparte y su stock se descuenta al preparar la que las usa.
"""
from __future__ import annotations

# ── Categorías de cocina para los platos ──────────────────────────────────────
CATEGORIAS = ["Crepes salados", "Crepes dulces", "Sándwiches", "Hamburguesas", "Alitas"]

# ── Crudos: nombre → unidad (g | ml | unidad) ─────────────────────────────────
CRUDOS = {
    # condimentos / secos
    "Sal": "g", "Paprika": "g", "Ajo en polvo": "g", "Cebolla en polvo": "g",
    "Pimienta": "g", "Orégano en polvo": "g", "Comino": "g", "Cúrcuma": "g",
    "Sazonatodo": "g", "Lemmon pepper": "g",
    # harinas / secos base
    "Harina de trigo": "g", "Maicena": "g", "Arroz comino": "g", "Azúcar": "g",
    # lácteos / grasas
    "Leche": "ml", "Mantequilla": "g", "Crema de leche": "ml",
    "Queso tajado": "g", "Queso crema": "g", "Queso campesino": "g",
    # salsas / untables comprados
    "Miel": "g", "Mostaza": "g", "Mayonesa": "g", "Salsa picante": "g",
    "Salsa de tomate": "g", "Salsa bbq": "g", "Salsa inglesa": "g",
    "Salsa tipo cheddar": "g", "Nutella": "g", "Leche condensada": "g",
    "Chilacuán en almíbar": "g", "Almíbar de chilacuán": "ml",
    # líquidos varios
    "Aceite": "ml", "Vinagre": "g", "Vino blanco": "ml", "Jugo de limón": "ml",
    "Agua": "ml",
    # proteínas
    "Pechuga de pollo": "g", "Pecho de res": "g", "Carne de res molida": "g",
    "Atún en lata": "g", "Alitas de pollo": "g", "Tocineta": "g",
    "Champiñones": "g",
    # frutas / verduras
    "Tomate": "g", "Cebolla morada": "g", "Cebolla cabezona": "g",
    "Cilantro fresco": "g", "Aguacate hass": "g", "Lechuga": "g",
    "Repollo verde": "g", "Repollo morado": "g", "Zanahoria": "g",
    "Manzana verde": "g", "Maíz dulce": "g", "Banano": "g", "Fresas": "g",
    "Ralladura de naranja": "g",
    # huevos / panes
    "Huevos": "unidad", "Ajo (dientes)": "g",
    "Pan tipo cubano": "g", "Pan artesanal": "g",
}

# ── Preparaciones: nombre → (rendimiento_g, [(componente, cantidad)]) ──────────
# El componente puede ser un crudo o OTRA preparación (anidado).
PREPARACIONES = {
    "Adobo base seco": (1000, [
        ("Sal", 200), ("Paprika", 150), ("Ajo en polvo", 150),
        ("Cebolla en polvo", 150), ("Pimienta", 80), ("Orégano en polvo", 60),
        ("Comino", 60), ("Cúrcuma", 50), ("Sazonatodo", 100)]),
    "Masa crepes": (1220, [
        ("Harina de trigo", 400), ("Leche", 600), ("Huevos", 3),
        ("Azúcar", 10), ("Sal", 10), ("Mantequilla", 50)]),
    "Salsa lemmon pepper": (190, [
        ("Mantequilla", 125), ("Miel", 50), ("Lemmon pepper", 15)]),
    "Salsa miel mostaza": (275, [
        ("Mostaza", 125), ("Miel", 60), ("Mayonesa", 90)]),
    "Salsa búfalo": (361, [
        ("Mantequilla", 125), ("Salsa picante", 80), ("Vinagre", 40),
        ("Ajo en polvo", 8), ("Paprika", 8), ("Pimienta", 8),
        ("Salsa de tomate", 100)]),
    # La "mayonesa de ajo" (paso previo) se aplana aquí porque no se usa en
    # ningún otro lado; el rendimiento final de la salsa es 650 g.
    "Salsa hobbycenter": (650, [
        ("Huevos", 2), ("Ajo (dientes)", 15), ("Sal", 5), ("Pimienta", 5),
        ("Orégano en polvo", 5), ("Sazonatodo", 10), ("Aceite", 300),
        ("Salsa bbq", 30), ("Mostaza", 45), ("Vinagre", 75), ("Miel", 90),
        ("Salsa inglesa", 30)]),
    "Pico de gallo": (448, [
        ("Tomate", 300), ("Cebolla morada", 80), ("Cilantro fresco", 20),
        ("Jugo de limón", 40), ("Sal", 5), ("Pimienta", 3)]),
    "Guacamole": (548, [
        ("Aguacate hass", 400), ("Cebolla cabezona", 80), ("Cilantro fresco", 20),
        ("Jugo de limón", 40), ("Sal", 5), ("Pimienta", 3)]),
    "Relleno pollo con champiñones": (651, [
        ("Pechuga de pollo", 200), ("Champiñones", 100), ("Cebolla cabezona", 80),
        ("Crema de leche", 150), ("Vino blanco", 100), ("Aceite", 15),
        ("Sal", 3), ("Pimienta", 3)]),
    "Relleno stroganoff de res": (651, [
        ("Pecho de res", 200), ("Champiñones", 100), ("Cebolla cabezona", 80),
        ("Crema de leche", 150), ("Vino blanco", 100), ("Aceite", 15),
        ("Sal", 3), ("Pimienta", 3)]),
    "Relleno carne picante": (610, [
        ("Carne de res molida", 400), ("Maíz dulce", 150), ("Salsa búfalo", 50),
        ("Aceite", 10)]),
    "Relleno atún cremoso": (629, [
        ("Atún en lata", 320), ("Cebolla morada", 85), ("Maíz dulce", 85),
        ("Cilantro fresco", 12), ("Mayonesa", 42), ("Mostaza", 25),
        ("Queso crema", 55), ("Sazonatodo", 5)]),
    "Ensalada coleslaw": (435, [
        ("Repollo verde", 110), ("Repollo morado", 80), ("Zanahoria", 60),
        ("Manzana verde", 80), ("Mayonesa", 40), ("Vinagre", 10),
        ("Crema de leche", 30), ("Mostaza", 10), ("Miel", 15)]),
    "Filete de pollo apanado": (660, [
        ("Pechuga de pollo", 600), ("Adobo base seco", 40),
        ("Harina de trigo", 100), ("Maicena", 100)]),
    "Arroz blanco": (600, [
        ("Arroz comino", 200), ("Aceite", 30), ("Sal", 5),
        ("Sazonatodo", 10), ("Agua", 400)]),
}

# ── Platos: nombre → (categoría, precio_costo, [(componente, cantidad)]) ───────
PLATOS = {
    "Crepe pollo con champiñones": ("Crepes salados", 4883, [
        ("Masa crepes", 80), ("Relleno pollo con champiñones", 130),
        ("Queso tajado", 30), ("Salsa hobbycenter", 30)]),
    "Crepe stroganoff de res": ("Crepes salados", 5094, [
        ("Masa crepes", 80), ("Relleno stroganoff de res", 130),
        ("Queso tajado", 30), ("Salsa hobbycenter", 30)]),
    "Crepe mexicano": ("Crepes salados", 5287, [
        ("Masa crepes", 80), ("Relleno carne picante", 150),
        ("Queso tajado", 30), ("Salsa hobbycenter", 30)]),
    "Crepe de nutella": ("Crepes dulces", 3927, [
        ("Masa crepes", 80), ("Nutella", 60), ("Banano", 50),
        ("Fresas", 50), ("Leche condensada", 15)]),
    "Crepe de chilacuán": ("Crepes dulces", 4730, [
        ("Masa crepes", 80), ("Chilacuán en almíbar", 60), ("Queso campesino", 60),
        ("Leche condensada", 15), ("Crema de leche", 40),
        ("Ralladura de naranja", 3), ("Almíbar de chilacuán", 10)]),
    "Sándwich de pollo con champiñones": ("Sándwiches", 5454, [
        ("Pan tipo cubano", 30), ("Relleno pollo con champiñones", 130),
        ("Queso tajado", 30), ("Salsa hobbycenter", 30), ("Mantequilla", 10)]),
    "Sándwich stroganoff de res": ("Sándwiches", 5665, [
        ("Pan tipo cubano", 30), ("Relleno stroganoff de res", 130),
        ("Queso tajado", 30), ("Salsa hobbycenter", 30), ("Mantequilla", 10)]),
    "Sándwich de atún": ("Sándwiches", 6050, [
        ("Pan tipo cubano", 30), ("Relleno atún cremoso", 125),
        ("Queso tajado", 30), ("Salsa hobbycenter", 30), ("Mantequilla", 10)]),
    "Hamburguesa de res": ("Hamburguesas", 10108, [
        ("Carne de res molida", 150), ("Pan artesanal", 50), ("Queso tajado", 15),
        ("Tocineta", 40), ("Cebolla cabezona", 45), ("Azúcar", 5),
        ("Tomate", 20), ("Lechuga", 5), ("Salsa hobbycenter", 30),
        ("Salsa tipo cheddar", 20), ("Mantequilla", 10), ("Aceite", 5)]),
    "Hamburguesa de pollo": ("Hamburguesas", 6919, [
        ("Pan artesanal", 50), ("Filete de pollo apanado", 132),
        ("Queso tajado", 15), ("Ensalada coleslaw", 72),
        ("Salsa hobbycenter", 30), ("Mantequilla", 10)]),
    "Alitas (porción)": ("Alitas", 10004, [
        ("Alitas de pollo", 250), ("Adobo base seco", 5), ("Agua", 10),
        ("Harina de trigo", 50), ("Maicena", 50), ("Aceite", 25)]),
}

# ── Stock real actual (de "Inventario - Import.xlsx", hoja INSUMOS) ────────────
# Solo los insumos cuyo nombre corresponde SIN ambigüedad a un crudo del APU.
# Los que no aparecen aquí reciben stock por defecto (ver STOCK_DEFAULT).
# Se omiten a propósito los que tienen unidad distinta o son semi-preparados en
# el inventario real (Carne De Hamburguesa en Und, Pechuga De Pollo Crepe,
# Cebollas en Und, Limones en Und): ponles el conteo físico en el POS.
STOCK_REAL = {
    "Champiñones": 1227, "Miel": 3071, "Nutella": 279, "Alitas de pollo": 4400,
    "Vinagre": 2018, "Cúrcuma": 980, "Comino": 952, "Ajo en polvo": 769,
    "Cebolla en polvo": 774, "Pimienta": 1863, "Orégano en polvo": 292,
    "Paprika": 1947, "Sazonatodo": 54, "Salsa inglesa": 772,
    "Salsa de tomate": 2690, "Salsa bbq": 2727, "Salsa tipo cheddar": 66,
    "Leche condensada": 3780, "Harina de trigo": 954, "Azúcar": 4830,
    "Vino blanco": 460, "Leche": 900,
}

# ── Stock por defecto para crudos sin conteo real (por unidad) ────────────────
#   g   → 1000 (1 kg)   ml → 1000 (1 L)   unidad → 100
STOCK_DEFAULT = {"g": (1000, 200), "ml": (1000, 200), "unidad": (100, 12)}


def stock_crudo(nombre: str, unidad: str) -> tuple[float, float]:
    """(stock, stock_minimo) para un crudo: real si existe, si no por defecto."""
    if nombre in STOCK_REAL:
        return (float(STOCK_REAL[nombre]), 0.0)
    return STOCK_DEFAULT.get(unidad, STOCK_DEFAULT["g"])


def es_preparacion(nombre: str) -> bool:
    return nombre in PREPARACIONES


def codigo_plato(indice: int) -> str:
    return f"PLATO-{indice:03d}"
