#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gambit: crupier de la baraja de ideas de Uatu.

Lee la baraja (solo lectura), guarda la clasificacion por campo del desarrollo
y las manos en datos/, y genera la demostracion visual en demo/index.html.
Python estandar, sin dependencias.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BARAJA_DEF = Path(r"C:\Users\andre\OneDrive\Documentos\Uatu\baraja\baraja.json")
MARCADOR = "__GAMBIT_DATOS__"
ESQUELETO_LOCAL = (
    '<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    "<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);"
    "padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px system-ui,sans-serif}"
    "img{max-width:100%}[hidden]{display:none!important}</style>\n</head>\n<body>\n"
)

CAMPOS = [
    ("frontend", "Frontend web: maquetación, componentes, CSS"),
    ("ux-ui", "Diseño UX/UI y sistemas de diseño"),
    ("movimiento", "Animación e interacción web"),
    ("grafico", "Gráficos 3D, canvas, shaders y generativo"),
    ("movil", "Apps móviles (Android, iOS, híbridas)"),
    ("backend", "Backend y APIs"),
    ("datos", "Bases de datos, analítica y visualización de datos"),
    ("ia", "Agentes de IA y automatización"),
    ("devops", "Despliegue, rendimiento y operación"),
    ("accesibilidad-seo", "Accesibilidad, SEO y calidad web"),
    ("producto", "Producto, marketing, portafolio y presentación"),
    ("escuela", "Entregables académicos: reportes, SRS, diagramas, exposiciones"),
    # Familia "Conocimiento general" (2026-11-15): cartas de temas generales que llegan por EGO.
    ("ia-general", "IA para la vida diaria: asistentes, modelos y su uso fuera del código"),
    ("tecnologia", "Tecnología: dispositivos, apps, hogar conectado y trucos del día a día"),
    ("ciencia-salud", "Ciencia y salud: cuerpo, mente, bienestar y descubrimientos"),
    ("finanzas", "Finanzas personales: dinero, ahorro, inversión y negocios"),
    ("productividad", "Productividad: hábitos, estudio, organización y aprendizaje"),
    ("actualidad", "Actualidad: noticias, tendencias y lo que pasa en el mundo"),
    ("cultura", "Cultura: arte, música, cine, libros e historia"),
]
CAMPOS_ID = [c[0] for c in CAMPOS]
# Familias del catálogo. Una carta puede tener campos de las dos; su familia principal es la
# del campo de mayor peso (empate: la de mayor suma de pesos; si sigue, desarrollo).
FAMILIAS = (("desarrollo", "Desarrollo"), ("general", "Conocimiento general"))
CAMPOS_GENERALES = ("ia-general", "tecnologia", "ciencia-salud", "finanzas", "productividad", "actualidad", "cultura")
FAMILIA_DE = {c: ("general" if c in CAMPOS_GENERALES else "desarrollo") for c in CAMPOS_ID}
# Sin clasificar, la familia se adivina por el mazo: estas palabras indican desarrollo.
MAZOS_DESARROLLO = ("diseno", "web", "agente", "backend", "frontend", "movil", "base-de-datos",
                    "devops", "program", "codigo", "api", "software")
NIVELES = ("estudiante", "intermedio", "avanzado")
COSTOS = ("gratis", "pago", "depende")
TIPOS = ("escalera", "color", "par", "libre")
MIN_CARTAS, MAX_CARTAS = 3, 7
# --- Naipes -------------------------------------------------------------------
# Regla de palos (encargo 2): cada carta de Uatu se juega con un palo frances.
#   corazones  lo que se siente: color, tipografia, imagen y material
#   diamantes  lo que vende: composicion y presentacion
#   treboles   lo que se mueve: movimiento, interaccion, 3D y canvas
#   picas      lo que da poder: proceso, herramientas y agentes de IA
# Orden de decision: 1) "naipe" puesto a mano en la clasificacion, 2) palo de Uatu
# en PALO_A_NAIPE, 3) mazo en MAZO_A_NAIPE, 4) pistas por palabra en el palo y el
# mazo, 5) picas (un mazo nuevo de backend o productividad es "lo que da poder").
# Mazos de conocimiento general (EGO, 2026-11-15), por nombre exacto o por pista:
#   corazones  ciencia y salud, bienestar, cultura, arte, música, cine, libros
#   diamantes  finanzas, dinero, negocios, emprendimiento, marketing
#   treboles   actualidad, noticias, tendencias, deporte, viajes
#   picas      IA, tecnología, productividad, estudio y todo mazo sin pista
# Comodines: cartas de regla general que valen en cualquier mano; van sin rango.
RANGOS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
NAIPES = {
    "corazones": ("♥", "Lo que se siente: color, tipografía, imagen y material; en general, ciencia, salud y cultura"),
    "diamantes": ("♦", "Lo que vende: composición y presentación; en general, finanzas y negocios"),
    "treboles": ("♣", "Lo que se mueve: movimiento, interacción, 3D y canvas; en general, actualidad y tendencias"),
    "picas": ("♠", "Lo que da poder: proceso, herramientas y agentes de IA; en general, IA, tecnología y productividad"),
}
PALO_A_NAIPE = {
    "color": "corazones", "tipografia": "corazones", "imagen-y-material": "corazones",
    "composicion": "diamantes", "presentacion": "diamantes",
    "movimiento": "treboles", "interaccion": "treboles", "3d-y-canvas": "treboles",
    "proceso": "picas", "herramientas": "picas", "arquitectura": "picas", "casos-de-uso": "picas",
}
MAZO_A_NAIPE = {
    "agentes-ia": "picas", "ia": "picas", "ia-general": "picas", "inteligencia-artificial": "picas",
    "tecnologia": "picas", "tecnologia-cotidiana": "picas", "productividad": "picas",
    "ciencia": "corazones", "salud": "corazones", "ciencia-y-salud": "corazones", "cultura": "corazones",
    "finanzas": "diamantes", "finanzas-personales": "diamantes", "negocios": "diamantes",
    "actualidad": "treboles", "noticias": "treboles",
}
PISTAS_NAIPE = (
    ("corazones", ("color", "tipo", "imagen", "material", "visual", "ilustr", "foto", "marca",
                   "salud", "cienc", "bienestar", "cultur", "arte", "music", "cine", "libro", "histor")),
    ("diamantes", ("compos", "present", "layout", "maquet", "venta", "market", "conver", "copy",
                   "finanz", "dinero", "negocio", "emprend", "invers", "ahorro", "econom")),
    ("treboles", ("movim", "anim", "interac", "3d", "canvas", "shader", "juego", "scroll",
                  "actualidad", "noticia", "tendencia", "deport", "viaje")),
)
# Potencia de 0 a 100: utilidad 35, impacto 30, evidencia 15, facilidad 10, costo y peso 10.
# Impacto (1 a 5, juicio de Gambit): en Desarrollo, cuánto mejora un producto real; en
# Conocimiento general, cuánto le sirve a André en su vida, sus estudios o su trabajo.
PESOS_POTENCIA = (("utilidad", 35), ("impacto", 30), ("evidencia", 15), ("facilidad", 10), ("costo", 10))
CARGAS = ("ligera", "media", "pesada")
TAM_ESCALERA = 7
CAMPOS_HUELLA = ("mazo", "palo", "nombre", "idea", "como", "cuando", "evitar",
                 "dificultad", "stack", "etiquetas")


class ErrorGambit(Exception):
    """Error de validacion o de datos; se muestra sin traza."""


# ---------------------------------------------------------------- utilidades

def hoy():
    return datetime.date.today().isoformat()


def una_linea(texto, largo=110):
    t = " ".join(str(texto or "").split())
    return t if len(t) <= largo else t[: largo - 1].rstrip() + "…"


def huella(carta):
    base = {k: carta.get(k) for k in CAMPOS_HUELLA}
    crudo = json.dumps(base, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:12]


def leer_json(ruta, defecto):
    ruta = Path(ruta)
    if not ruta.exists():
        return defecto
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar_json(ruta, datos):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, ruta)


def leer_entrada(texto):
    if texto is None:
        texto = sys.stdin.buffer.read().decode("utf-8-sig")
    texto = texto.strip()
    if not texto:
        raise ErrorGambit("No llegó JSON por la entrada estándar.")
    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        raise ErrorGambit(f"JSON inválido: {e}")


# ------------------------------------------------------------------ contexto

class Ctx:
    def __init__(self, baraja=None, datos=None, demo=None, plantilla=None):
        self.baraja = Path(baraja or os.environ.get("GAMBIT_BARAJA") or BARAJA_DEF)
        self.datos = Path(datos or os.environ.get("GAMBIT_DATOS") or RAIZ / "datos")
        self.demo = Path(demo or os.environ.get("GAMBIT_DEMO") or RAIZ / "demo" / "index.html")
        self.pages = Path(os.environ.get("GAMBIT_PAGES") or self.demo.parent.parent / "docs" / "index.html")
        self.plantilla = Path(plantilla or Path(__file__).resolve().parent / "plantilla.html")
        self.ruta_clas = self.datos / "clasificacion.json"
        self.ruta_manos = self.datos / "manos.json"

    def cartas(self):
        if not self.baraja.exists():
            raise ErrorGambit(f"No encuentro la baraja: {self.baraja}")
        with open(self.baraja, encoding="utf-8") as f:
            return json.load(f).get("cartas", [])

    def clasificacion(self):
        d = leer_json(self.ruta_clas, {"version": 1, "cartas": {}})
        d.setdefault("cartas", {})
        return d

    def manos(self):
        d = leer_json(self.ruta_manos, {"version": 1, "manos": []})
        d.setdefault("manos", [])
        return d


# ---------------------------------------------------------------------- sync

def estado_sync(ctx):
    cartas = ctx.cartas()
    clas = ctx.clasificacion()["cartas"]
    por_id = {c["id"]: c for c in cartas}
    nuevas = [c for c in cartas if c["id"] not in clas]
    cambiadas = [c for c in cartas
                 if c["id"] in clas and clas[c["id"]].get("huella") != huella(c)]
    huerfanas = sorted(i for i in clas if i not in por_id)
    return {"cartas": cartas, "clas": clas, "nuevas": nuevas,
            "cambiadas": cambiadas, "huerfanas": huerfanas}


def linea_carta(c, detalle=False):
    base = f"{c['id']} | {c.get('palo', '?')} | {c.get('nombre', '')} | {una_linea(c.get('idea'))}"
    if not detalle:
        return base
    extra = [f"   idea: {una_linea(c.get('idea'), 260)}",
             f"   como: {una_linea(c.get('como'), 220)}",
             f"   cuando: {una_linea(c.get('cuando'), 140)}",
             f"   evitar: {una_linea(c.get('evitar'), 140)}",
             f"   dif {c.get('dificultad', '?')} · {c.get('stack', '')} · {', '.join(c.get('etiquetas', []))}"]
    return f"{c['id']} | {c.get('mazo', '?')} / {c.get('palo', '?')} | {c.get('nombre', '')}\n" + "\n".join(extra)


def cmd_sync(ctx, args):
    e = estado_sync(ctx)
    mazos = sorted({c.get("mazo", "?") for c in e["cartas"]})
    print(f"Baraja: {len(e['cartas'])} cartas, {len(mazos)} mazos. "
          f"Clasificadas: {len(e['cartas']) - len(e['nuevas'])}. "
          f"Sin clasificar: {len(e['nuevas'])}. Cambiadas: {len(e['cambiadas'])}. "
          f"Sin carta: {len(e['huerfanas'])}.")
    if e["nuevas"]:
        print("\nSIN CLASIFICAR")
        for c in e["nuevas"]:
            print(linea_carta(c, args.detalle))
    if e["cambiadas"]:
        print("\nCAMBIARON DESDE SU CLASIFICACIÓN")
        for c in e["cambiadas"]:
            print(linea_carta(c, args.detalle))
    if e["huerfanas"]:
        print("\nCLASIFICADAS SIN CARTA EN LA BARAJA")
        for i in e["huerfanas"]:
            print(i)
    if not (e["nuevas"] or e["cambiadas"] or e["huerfanas"]):
        print("Sin pendientes.")
    return 0


def cmd_ver(ctx, args):
    por_id = {c["id"]: c for c in ctx.cartas()}
    faltan = [i for i in args.ids if i not in por_id]
    if faltan:
        raise ErrorGambit("No existen en la baraja: " + ", ".join(faltan))
    clas = ctx.clasificacion()["cartas"]
    for i in args.ids:
        print(linea_carta(por_id[i], True))
        k = clas.get(i)
        if k:
            for cp in k["campos"]:
                print(f"   campo {cp['campo']} (peso {cp['peso']}): {cp['aplicacion']}")
            if k.get("combina_con"):
                print("   combina: " + ", ".join(k["combina_con"]))
            if k.get("choca_con"):
                print("   choca: " + ", ".join(k["choca_con"]))
    return 0


# ---------------------------------------------------------------- clasificar

def validar_clasificacion(entrada, ids_baraja):
    """Devuelve (limpia, errores) para una entrada de clasificacion."""
    err = []
    if not isinstance(entrada, dict):
        return None, ["cada entrada debe ser un objeto"]
    cid = entrada.get("id")
    pref = f"{cid}: "
    if cid not in ids_baraja:
        return None, [f"{cid!r}: no existe en la baraja"]
    campos = entrada.get("campos")
    limpios = []
    if not isinstance(campos, list) or not 1 <= len(campos) <= 4:
        err.append(pref + "debe tener de 1 a 4 campos")
        campos = []
    vistos = set()
    for cp in campos:
        if not isinstance(cp, dict):
            err.append(pref + "cada campo debe ser un objeto")
            continue
        nombre, peso = cp.get("campo"), cp.get("peso")
        aplic = " ".join(str(cp.get("aplicacion") or "").split())
        if nombre not in CAMPOS_ID:
            err.append(pref + f"campo fuera del catálogo: {nombre!r}")
        elif nombre in vistos:
            err.append(pref + f"campo repetido: {nombre}")
        vistos.add(nombre)
        if peso not in (1, 2, 3):
            err.append(pref + f"peso inválido en {nombre}: {peso!r} (1 a 3)")
        if not aplic:
            err.append(pref + f"falta la aplicación en {nombre}")
        limpios.append({"campo": nombre, "peso": peso, "aplicacion": aplic})
    nivel = entrada.get("nivel")
    if nivel not in NIVELES:
        err.append(pref + f"nivel inválido: {nivel!r} ({', '.join(NIVELES)})")
    costo = entrada.get("costo")
    if costo not in COSTOS:
        err.append(pref + f"costo inválido: {costo!r} ({', '.join(COSTOS)})")
    relaciones = {}
    for clave in ("combina_con", "choca_con"):
        lista = entrada.get(clave) or []
        if not isinstance(lista, list):
            err.append(pref + f"{clave} debe ser una lista")
            lista = []
        for otro in lista:
            if otro == cid:
                err.append(pref + f"{clave} no puede apuntar a sí misma")
            elif otro not in ids_baraja:
                err.append(pref + f"{clave}: {otro!r} no existe en la baraja")
        relaciones[clave] = sorted(set(lista))
    ambos = set(relaciones["combina_con"]) & set(relaciones["choca_con"])
    if ambos:
        err.append(pref + "combina y choca a la vez con " + ", ".join(sorted(ambos)))
    puntos, err_puntos = validar_puntos(entrada, pref)
    err += err_puntos
    if err:
        return None, err
    limpios.sort(key=lambda x: (-x["peso"], CAMPOS_ID.index(x["campo"])))
    limpia = {"campos": limpios, "nivel": nivel, "costo": costo,
              "combina_con": relaciones["combina_con"],
              "choca_con": relaciones["choca_con"]}
    nota = " ".join(str(entrada.get("nota") or "").split())
    if nota:
        limpia["nota"] = nota
    limpia.update(puntos)
    return limpia, []


def cmd_clasificar(ctx, args, entrada=None):
    datos = leer_entrada(entrada)
    if isinstance(datos, dict):
        datos = datos.get("cartas", [datos] if "id" in datos else [])
    if not isinstance(datos, list) or not datos:
        raise ErrorGambit("Se espera una lista de clasificaciones.")
    cartas = ctx.cartas()
    por_id = {c["id"]: c for c in cartas}
    errores, listas = [], {}
    for e in datos:
        limpia, err = validar_clasificacion(e, por_id)
        errores.extend(err)
        if limpia:
            if e["id"] in listas:
                errores.append(f"{e['id']}: repetida en la entrada")
            listas[e["id"]] = limpia
    if errores:
        raise ErrorGambit("No se guardó nada. Errores:\n- " + "\n- ".join(errores))
    clas = ctx.clasificacion()
    nuevas = 0
    for cid, limpia in listas.items():
        nuevas += cid not in clas["cartas"]
        limpia["huella"] = huella(por_id[cid])
        limpia["clasificada"] = hoy()
        previa = clas["cartas"].get(cid, {})
        for clave in ("impacto", "carga", "usada_en", "comodin", "naipe"):
            if clave in previa and clave not in limpia:
                limpia[clave] = previa[clave]
        clas["cartas"][cid] = limpia
    clas["cartas"] = dict(sorted(clas["cartas"].items()))
    recalcular(clas, cartas)
    clas["actualizado"] = hoy()
    guardar_json(ctx.ruta_clas, clas)
    faltan = len([i for i in por_id if i not in clas["cartas"]])
    print(f"Guardadas {len(listas)} ({nuevas} nuevas, {len(listas) - nuevas} actualizadas). "
          f"Sin clasificar: {faltan}.")
    return 0


# -------------------------------------------------------------------- campos

def cartas_por_campo(cartas, clas):
    filas = {c: [] for c in CAMPOS_ID}
    por_id = {c["id"]: c for c in cartas}
    for cid, k in clas.items():
        if cid not in por_id:
            continue
        for cp in k.get("campos", []):
            filas.setdefault(cp["campo"], []).append(
                {"id": cid, "peso": cp["peso"], "aplicacion": cp["aplicacion"],
                 "nombre": por_id[cid].get("nombre", "")})
    for lista in filas.values():
        lista.sort(key=lambda x: (-x["peso"], x["id"]))
    return filas


def cmd_campos(ctx, args):
    filas = cartas_por_campo(ctx.cartas(), ctx.clasificacion()["cartas"])
    if not args.campo:
        for fam, titulo in FAMILIAS:
            print(titulo)
            for cid, nombre in CAMPOS:
                if FAMILIA_DE[cid] != fam:
                    continue
                lista = filas[cid]
                prin = sum(1 for x in lista if x["peso"] == 3)
                print(f"  {cid:<18} {len(lista):>3} cartas ({prin} principales) · {nombre}")
        return 0
    if args.campo not in CAMPOS_ID:
        raise ErrorGambit(f"Campo fuera del catálogo: {args.campo}. Opciones: {', '.join(CAMPOS_ID)}")
    print(dict(CAMPOS)[args.campo])
    for x in filas[args.campo]:
        print(f"{x['peso']} {x['id']} {x['nombre']} — {x['aplicacion']}")
    if not filas[args.campo]:
        print("Sin cartas.")
    return 0


# --------------------------------------------------------------------- manos

def choques_declarados(ids, clas):
    pares = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if b in clas.get(a, {}).get("choca_con", []) or a in clas.get(b, {}).get("choca_con", []):
                pares.append((a, b))
    return pares


def validar_mano(mano, por_id):
    err = []
    if not isinstance(mano, dict):
        return None, ["la mano debe ser un objeto"]
    mid = str(mano.get("id") or "")
    if not re.fullmatch(r"mano-[a-z0-9]+(-[a-z0-9]+)*", mid):
        err.append(f"id inválido: {mid!r} (formato mano-nombre-corto)")
    for clave in ("nombre", "objetivo", "por_que"):
        if not str(mano.get(clave) or "").strip():
            err.append(f"falta {clave}")
    tipo = mano.get("tipo")
    if tipo not in TIPOS:
        err.append(f"tipo inválido: {tipo!r} ({', '.join(TIPOS)})")
    cartas = mano.get("cartas")
    limpias = []
    if not isinstance(cartas, list):
        err.append("cartas debe ser una lista")
        cartas = []
    minimo = 2 if tipo == "par" else MIN_CARTAS
    if not minimo <= len(cartas) <= MAX_CARTAS:
        err.append(f"la mano lleva de {minimo} a {MAX_CARTAS} cartas (tiene {len(cartas)})")
    vistos = set()
    for c in cartas:
        cid = c.get("id") if isinstance(c, dict) else None
        if cid not in por_id:
            err.append(f"carta inexistente: {cid!r}")
            continue
        if cid in vistos:
            err.append(f"carta repetida: {cid}")
        vistos.add(cid)
        rol = " ".join(str(c.get("rol") or "").split())
        if not rol:
            err.append(f"{cid}: falta el rol")
        limpias.append({"id": cid, "rol": rol})
    dif = mano.get("dificultad_total")
    if dif is None and limpias:
        dif = max(por_id[c["id"]].get("dificultad", 1) for c in limpias)
    if dif not in (1, 2, 3):
        err.append(f"dificultad_total inválida: {dif!r} (1 a 3)")
    listo = mano.get("listo") or []
    if not isinstance(listo, list):
        err.append("listo debe ser una lista de criterios")
        listo = []
    if err:
        return None, err
    limpia = {"id": mid, "nombre": mano["nombre"].strip(), "objetivo": mano["objetivo"].strip(),
              "tipo": tipo, "cartas": limpias, "por_que": mano["por_que"].strip(),
              "conflictos": str(mano.get("conflictos") or "").strip(),
              "dificultad_total": dif, "stack": str(mano.get("stack") or "").strip(),
              "listo": [" ".join(str(x).split()) for x in listo if str(x).strip()]}
    if str(mano.get("usada_en") or "").strip():
        limpia["usada_en"] = mano["usada_en"].strip()
    return limpia, []


def avisos_mano(mano, por_id, clas):
    avisos = []
    ids = [c["id"] for c in mano["cartas"]]
    for a, b in choques_declarados(ids, clas):
        avisos.append(f"choque declarado: {a} con {b}")
    sin = [i for i in ids if i not in clas]
    if sin:
        avisos.append("sin clasificar: " + ", ".join(sin))
    mov = [i for i in ids if por_id[i].get("palo") == "movimiento"]
    if len(mov) > 1:
        avisos.append("varias cartas de movimiento (" + ", ".join(mov) +
                      "): dejar un solo momento animado por página")
    return avisos


def buscar_mano(ctx, mid):
    for m in ctx.manos()["manos"]:
        if m["id"] == mid:
            return m
    raise ErrorGambit(f"No existe la mano {mid}. Usa 'manos' para listarlas.")


def texto_brief(mano, por_id, clas):
    L = [f"BRIEF · {mano['nombre']} ({mano['id']})",
         f"Tipo: {mano['tipo']} · Dificultad: {mano['dificultad_total']} de 3"
         + (f" · Stack: {mano['stack']}" if mano.get("stack") else ""),
         f"Objetivo: {mano['objetivo']}",
         f"Por qué juntas: {mano['por_que']}"]
    if mano.get("usada_en"):
        L.append(f"Referencia: {mano['usada_en']}")
    L += ["", "CARTAS EN ORDEN DE APLICACIÓN"]
    for n, c in enumerate(mano["cartas"], 1):
        k = por_id.get(c["id"])
        if not k:
            L.append(f"{n}. {c['id']} · (ya no existe en la baraja) · rol: {c['rol']}")
            continue
        L.append(f"{n}. {c['id']} · {k.get('nombre', '')} · rol: {c['rol']}")
        L.append(f"   Idea: {' '.join(str(k.get('idea', '')).split())}")
        L.append(f"   Cómo: {' '.join(str(k.get('como', '')).split())}")
        if k.get("evitar"):
            L.append(f"   Evitar: {' '.join(str(k['evitar']).split())}")
    L += ["", "CONFLICTOS"]
    L.append(mano.get("conflictos") or "Ninguno declarado.")
    for a, b in choques_declarados([c["id"] for c in mano["cartas"]], clas):
        L.append(f"Atención: {a} y {b} están marcadas como cartas que chocan.")
    L += ["", "LISTO CUANDO"]
    criterios = mano.get("listo") or [
        "Cada carta se reconoce en la página en el rol indicado.",
        "Hay un solo momento animado protagonista por página.",
        "Se ve bien a 360 px y respeta prefers-reduced-motion."]
    L += [f"- {x}" for x in criterios]
    return "\n".join(L)


def cmd_mano(ctx, args, entrada=None):
    por_id = {c["id"]: c for c in ctx.cartas()}
    clas = ctx.clasificacion()["cartas"]
    if args.accion == "escalera":
        if not args.id:
            raise ErrorGambit("Falta el campo: mano escalera CAMPO.")
        return cmd_escalera(ctx, args.id)
    if args.accion == "crear":
        datos = leer_entrada(entrada)
        lote = datos if isinstance(datos, list) else [datos]
        limpias, errores = [], []
        for m in lote:
            limpia, err = validar_mano(m, por_id)
            nombre = m.get("id", "?") if isinstance(m, dict) else "?"
            errores += [f"{nombre}: {x}" for x in err]
            if limpia:
                limpias.append(limpia)
        if errores:
            raise ErrorGambit("No se guardó nada. Errores:\n- " + "\n- ".join(errores))
        d = ctx.manos()
        for limpia in limpias:
            previa = next((m for m in d["manos"] if m["id"] == limpia["id"]), None)
            limpia["creada"] = previa.get("creada", hoy()) if previa else hoy()
            if previa:
                limpia["actualizada"] = hoy()
                d["manos"][d["manos"].index(previa)] = limpia
            else:
                d["manos"].append(limpia)
            print(f"{'Actualizada' if previa else 'Creada'} {limpia['id']}: "
                  f"{len(limpia['cartas'])} cartas, tipo {limpia['tipo']}.")
            for a in avisos_mano(limpia, por_id, clas):
                print(f"  Aviso: {a}")
        d["actualizado"] = hoy()
        guardar_json(ctx.ruta_manos, d)
        return 0
    if not args.id:
        raise ErrorGambit("Falta el id de la mano.")
    mano = buscar_mano(ctx, args.id)
    if args.accion == "brief":
        print(texto_brief(mano, por_id, clas))
        return 0
    if args.accion == "borrar":
        d = ctx.manos()
        d["manos"] = [m for m in d["manos"] if m["id"] != args.id]
        d["actualizado"] = hoy()
        guardar_json(ctx.ruta_manos, d)
        print(f"Borrada {args.id}.")
        return 0
    print(f"{mano['id']} · {mano['nombre']} · {mano['tipo']} · dificultad {mano['dificultad_total']}")
    print(f"Objetivo: {mano['objetivo']}")
    for n, c in enumerate(mano["cartas"], 1):
        nombre = por_id.get(c["id"], {}).get("nombre", "(ya no existe)")
        print(f"{n}. {c['id']} {nombre} — {c['rol']}")
    if mano.get("conflictos"):
        print(f"Conflictos: {mano['conflictos']}")
    for a in avisos_mano(mano, {**{c['id']: {} for c in mano['cartas']}, **por_id}, clas):
        print(f"Aviso: {a}")
    return 0


def cmd_manos(ctx, args):
    manos = ctx.manos()["manos"]
    if not manos:
        print("Sin manos.")
    for m in manos:
        ids = " ".join(c["id"] for c in m["cartas"])
        print(f"{m['id']} | {m['tipo']} | dif {m['dificultad_total']} | {m['nombre']} | {ids}")
    return 0


# ------------------------------------------------------------------ potencia

def slug(texto):
    t = unicodedata.normalize("NFD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def familia_de(carta, k=None):
    """Familia principal de una carta (desarrollo o general) y todas las que toca."""
    campos = (k or {}).get("campos") or []
    if not campos:
        mazo = slug(carta.get("mazo"))
        fam = "desarrollo" if any(p in mazo for p in MAZOS_DESARROLLO) else "general"
        return fam, [fam]
    puntaje = {}
    for cp in campos:
        f = FAMILIA_DE.get(cp["campo"], "desarrollo")
        maximo, suma = puntaje.get(f, (0, 0))
        puntaje[f] = (max(maximo, cp["peso"]), suma + cp["peso"])
    orden = [f for f, _ in FAMILIAS if f in puntaje]
    principal = max(orden, key=lambda f: (puntaje[f], f == "desarrollo"))
    return principal, orden


def naipe_de(carta, k=None):
    """Palo frances de una carta, segun la regla documentada arriba."""
    puesto = (k or {}).get("naipe")
    if puesto in NAIPES:
        return puesto
    palo, mazo = slug(carta.get("palo")), slug(carta.get("mazo"))
    if palo in PALO_A_NAIPE:
        return PALO_A_NAIPE[palo]
    if mazo in MAZO_A_NAIPE:
        return MAZO_A_NAIPE[mazo]
    for texto in (palo, mazo):
        for naipe, pistas in PISTAS_NAIPE:
            if any(p in texto for p in pistas):
                return naipe
    return "picas"


def partes_potencia(carta, k=None):
    """Desglose de la potencia. Sin clasificacion usa solo los datos de Uatu (provisional)."""
    k = k or {}
    campos = k.get("campos") or []
    if campos:
        suma = sum(c.get("peso", 0) for c in campos)
        utilidad = 35 * min(1.0, (suma + len(campos) - 1) / 10)
    else:
        utilidad = 35 * 0.4
    impacto = 30 * (k.get("impacto") or 3) / 5
    fuentes = carta.get("fuentes") or []
    creadores = {f.get("creador") for f in fuentes if f.get("creador")}
    evidencia = (0, 5, 7, 8)[min(len(fuentes), 3)]
    evidencia += 2 if len(creadores) >= 2 else 0
    evidencia += 5 if k.get("usada_en") else 0
    facilidad = {1: 10, 2: 6, 3: 2}.get(carta.get("dificultad"), 6)
    costo = {"gratis": 6, "depende": 3, "pago": 0}.get(k.get("costo"), 3)
    costo += {"ligera": 4, "media": 2, "pesada": 0}.get(k.get("carga"), 2)
    partes = {"utilidad": round(utilidad, 1), "impacto": round(impacto, 1),
              "evidencia": float(min(15, evidencia)), "facilidad": float(facilidad), "costo": float(costo)}
    partes["exacto"] = round(sum(partes.values()), 1)
    partes["total"] = int(round(partes["exacto"]))
    partes["provisional"] = not campos or not k.get("impacto")
    return partes


def tabla_potencia(cartas, clas):
    """id -> potencia, rango por percentil, palo de naipe y puesto en el ranking."""
    tabla = {}
    for c in cartas:
        k = clas.get(c["id"]) or {}
        t = partes_potencia(c, k)
        t["naipe"] = naipe_de(c, k)
        t["familia"], t["familias"] = familia_de(c, k)
        t["comodin"] = bool(k.get("comodin"))
        t["rango"], t["puesto"] = "", 0
        tabla[c["id"]] = t
    normales = sorted((i for i, t in tabla.items() if not t["comodin"]),
                      key=lambda i: (-tabla[i]["exacto"], i))
    n = len(normales)
    for puesto, cid in enumerate(normales, 1):
        t = tabla[cid]
        menores = sum(1 for o in normales if tabla[o]["exacto"] < t["exacto"])
        t["rango"] = RANGOS[min(len(RANGOS) - 1, int(menores * len(RANGOS) / n))]
        t["puesto"] = puesto
    return tabla


def escalera_campo(campo, cartas, clas, tabla, todas=False):
    """Las cartas de un campo de menor a mayor potencia; las ultimas 7 son la escalera."""
    pesos = {}
    for c in cartas:
        if tabla[c["id"]]["comodin"]:
            continue
        for cp in (clas.get(c["id"]) or {}).get("campos", []):
            if cp["campo"] == campo:
                pesos[c["id"]] = cp["peso"]
    orden = sorted(pesos, key=lambda i: (pesos[i] >= 2, tabla[i]["exacto"], i))
    resto, mano = orden[:-TAM_ESCALERA], orden[-TAM_ESCALERA:]
    mano.sort(key=lambda i: (tabla[i]["exacto"], i))
    return resto + mano if todas else mano


def etiqueta_naipe(t):
    return "comodín" if t["comodin"] else f"{t['rango']}{NAIPES[t['naipe']][0]}"


def validar_puntos(entrada, pref, ids_baraja=None):
    """Campos opcionales de potencia: impacto, carga, usada_en, comodin y naipe."""
    err, puntos = [], {}
    if "impacto" in entrada:
        if entrada["impacto"] not in (1, 2, 3, 4, 5):
            err.append(pref + f"impacto inválido: {entrada['impacto']!r} (1 a 5)")
        puntos["impacto"] = entrada["impacto"]
    if "carga" in entrada:
        if entrada["carga"] not in CARGAS:
            err.append(pref + f"carga inválida: {entrada['carga']!r} ({', '.join(CARGAS)})")
        puntos["carga"] = entrada["carga"]
    if "usada_en" in entrada:
        usada = entrada["usada_en"] or []
        if not isinstance(usada, list):
            err.append(pref + "usada_en debe ser una lista de proyectos")
            usada = []
        puntos["usada_en"] = [" ".join(str(x).split()) for x in usada if str(x).strip()]
    if "comodin" in entrada:
        puntos["comodin"] = bool(entrada["comodin"])
    if entrada.get("naipe"):
        if entrada["naipe"] not in NAIPES:
            err.append(pref + f"naipe inválido: {entrada['naipe']!r} ({', '.join(NAIPES)})")
        puntos["naipe"] = entrada["naipe"]
    return puntos, err


def recalcular(clas, cartas):
    """Guarda en cada clasificacion su potencia, rango, palo y puesto (los percentiles se mueven)."""
    tabla = tabla_potencia(cartas, clas["cartas"])
    for cid, k in clas["cartas"].items():
        t = tabla.get(cid)
        if not t:
            continue
        k["potencia"] = {"total": t["total"], **{f: t[f] for f, _ in PESOS_POTENCIA}}
        k["rango"], k["palo_naipe"], k["puesto"] = t["rango"], t["naipe"], t["puesto"]
        k["familia"] = t["familia"]
    return tabla


def cmd_puntuar(ctx, args, entrada=None):
    datos = leer_entrada(entrada)
    if isinstance(datos, dict):
        datos = [datos]
    cartas = ctx.cartas()
    por_id = {c["id"]: c for c in cartas}
    clas = ctx.clasificacion()
    errores, listos = [], {}
    for e in datos:
        cid = e.get("id") if isinstance(e, dict) else None
        if cid not in por_id:
            errores.append(f"{cid!r}: no existe en la baraja")
            continue
        if cid not in clas["cartas"]:
            errores.append(f"{cid}: aún no está clasificada; usa clasificar primero")
            continue
        puntos, err = validar_puntos(e, f"{cid}: ")
        errores += err
        listos[cid] = puntos
    if errores:
        raise ErrorGambit("No se guardó nada. Errores:\n- " + "\n- ".join(errores))
    for cid, puntos in listos.items():
        clas["cartas"][cid].update(puntos)
    recalcular(clas, cartas)
    clas["actualizado"] = hoy()
    guardar_json(ctx.ruta_clas, clas)
    sin = sum(1 for k in clas["cartas"].values() if not k.get("impacto"))
    print(f"Puntuadas {len(listos)}. Sin impacto: {sin}. Potencia y rangos recalculados.")
    return 0


def linea_ranking(c, t, clas):
    prin = [cp["campo"] for cp in (clas.get(c["id"]) or {}).get("campos", []) if cp["peso"] == 3]
    marca = " (provisional)" if t["provisional"] else ""
    puesto = f"{t['puesto']:>3}" if t["puesto"] else "  ·"
    return (f"{puesto} {etiqueta_naipe(t):<8} {t['total']:>3} {c['id']} {c.get('nombre', '')}"
            f"{' [' + ', '.join(prin) + ']' if prin else ''}{marca}")


def cmd_potencia(ctx, args):
    cartas = ctx.cartas()
    clas = ctx.clasificacion()
    if not args.id:
        tabla = recalcular(clas, cartas)
        clas["actualizado"] = hoy()
        guardar_json(ctx.ruta_clas, clas)
        print(f"Potencia recalculada para {len(tabla)} cartas.")
        for r in reversed(RANGOS):
            ids = [i for i, t in tabla.items() if t["rango"] == r]
            print(f"  {r:>2}: {len(ids)}")
        comodines = [i for i, t in tabla.items() if t["comodin"]]
        print("  comodines: " + (", ".join(comodines) or "ninguno"))
        prov = [i for i, t in tabla.items() if t["provisional"]]
        if prov:
            print("  provisionales: " + ", ".join(prov))
        return 0
    por_id = {c["id"]: c for c in cartas}
    if args.id not in por_id:
        raise ErrorGambit(f"No existe en la baraja: {args.id}")
    t = tabla_potencia(cartas, clas["cartas"])[args.id]
    c = por_id[args.id]
    print(f"{c['id']} · {c.get('nombre', '')}")
    print(f"{etiqueta_naipe(t)} · potencia {t['total']} de 100"
          + (f" · puesto {t['puesto']}" if t["puesto"] else "")
          + (" · provisional" if t["provisional"] else "")
          + f" · {dict(FAMILIAS)[t['familia']]}")
    for factor, maximo in PESOS_POTENCIA:
        print(f"  {factor:<10} {t[factor]:>5} de {maximo}")
    return 0


def cmd_ranking(ctx, args):
    cartas = ctx.cartas()
    clas = ctx.clasificacion()["cartas"]
    if args.campo and args.campo not in CAMPOS_ID:
        raise ErrorGambit(f"Campo fuera del catálogo: {args.campo}")
    if args.palo and args.palo not in NAIPES:
        raise ErrorGambit(f"Palo inválido: {args.palo}. Opciones: {', '.join(NAIPES)}")
    if args.familia and args.familia not in dict(FAMILIAS):
        raise ErrorGambit(f"Familia inválida: {args.familia}. Opciones: {', '.join(dict(FAMILIAS))}")
    tabla = tabla_potencia(cartas, clas)
    lista = [c for c in cartas if not tabla[c["id"]]["comodin"]]
    if args.familia:
        lista = [c for c in lista if tabla[c["id"]]["familia"] == args.familia]
    if args.campo:
        lista = [c for c in lista
                 if any(cp["campo"] == args.campo for cp in (clas.get(c["id"]) or {}).get("campos", []))]
    if args.palo:
        lista = [c for c in lista if tabla[c["id"]]["naipe"] == args.palo]
    lista.sort(key=lambda c: tabla[c["id"]]["puesto"])
    for c in lista[: args.n]:
        print(linea_ranking(c, tabla[c["id"]], clas))
    if not lista:
        print("Sin cartas.")
    if not args.campo and not args.palo:
        for c in cartas:
            if tabla[c["id"]]["comodin"] and (not args.familia or tabla[c["id"]]["familia"] == args.familia):
                print(linea_ranking(c, tabla[c["id"]], clas))
    return 0


def cmd_escalera(ctx, campo):
    if campo not in CAMPOS_ID:
        raise ErrorGambit(f"Campo fuera del catálogo: {campo}. Opciones: {', '.join(CAMPOS_ID)}")
    cartas = ctx.cartas()
    clas = ctx.clasificacion()["cartas"]
    tabla = tabla_potencia(cartas, clas)
    por_id = {c["id"]: c for c in cartas}
    mano = escalera_campo(campo, cartas, clas, tabla)
    print(f"Escalera de {campo}: de menor a mayor potencia")
    for cid in mano:
        t = tabla[cid]
        print(f"  {etiqueta_naipe(t):<4} {t['total']:>3} {cid} {por_id[cid].get('nombre', '')}")
    if not mano:
        print("  Sin cartas en este campo.")
    return 0


# --------------------------------------------------------------------- stats

def contar(valores):
    c = {}
    for v in valores:
        c[v] = c.get(v, 0) + 1
    return sorted(c.items(), key=lambda x: (-x[1], str(x[0])))


def cmd_stats(ctx, args):
    e = estado_sync(ctx)
    cartas, clas = e["cartas"], e["clas"]
    print(f"Cartas: {len(cartas)} · clasificadas: {len(cartas) - len(e['nuevas'])} · "
          f"manos: {len(ctx.manos()['manos'])}")
    print("\nPor mazo")
    for k, v in contar(c.get("mazo", "?") for c in cartas):
        print(f"  {v:>3} {k}")
    print("\nPor palo")
    for k, v in contar(f"{c.get('mazo', '?')} / {c.get('palo', '?')}" for c in cartas):
        print(f"  {v:>3} {k}")
    print("\nPor campo (total · principales)")
    filas = cartas_por_campo(cartas, clas)
    for cid in CAMPOS_ID:
        prin = sum(1 for x in filas[cid] if x["peso"] == 3)
        print(f"  {len(filas[cid]):>3} · {prin:>2} {cid}")
    print("\nPor dificultad")
    for k, v in sorted(contar(c.get("dificultad", "?") for c in cartas), key=lambda x: str(x[0])):
        print(f"  {v:>3} dificultad {k}")
    if e["nuevas"]:
        print("\nSin clasificar: " + " ".join(c["id"] for c in e["nuevas"]))
    else:
        print("\nSin clasificar: ninguna")
    return 0


# ---------------------------------------------------------------------- demo

def datos_demo(ctx):
    cartas = ctx.cartas()
    clas = ctx.clasificacion()["cartas"]
    por_id = {c["id"]: c for c in cartas}
    tabla = tabla_potencia(cartas, clas)
    salida = []
    for c in cartas:
        k = clas.get(c["id"], {})
        t = tabla[c["id"]]
        salida.append({
            "naipe": t["naipe"], "rango": t["rango"], "comodin": t["comodin"], "puesto": t["puesto"],
            "familia": t["familia"], "familias": t["familias"],
            "pot": {"total": t["total"], "provisional": t["provisional"],
                    **{f: t[f] for f, _ in PESOS_POTENCIA}},
            "carga": k.get("carga", ""), "usada": k.get("usada_en", []),
            "id": c["id"], "mazo": c.get("mazo", ""), "palo": c.get("palo", ""),
            "nombre": c.get("nombre", ""), "idea": c.get("idea", ""), "como": c.get("como", ""),
            "cuando": c.get("cuando", ""), "evitar": c.get("evitar", ""),
            "dificultad": c.get("dificultad", 1), "stack": c.get("stack", ""),
            "etiquetas": c.get("etiquetas", []),
            "fuentes": [{"url": f.get("url", ""), "creador": f.get("creador", ""),
                         "plataforma": f.get("plataforma", ""), "fecha": f.get("fecha", "")}
                        for f in c.get("fuentes", [])],
            "campos": k.get("campos", []), "nivel": k.get("nivel", ""), "costo": k.get("costo", ""),
            "combina": [i for i in k.get("combina_con", []) if i in por_id],
            "choca": [i for i in k.get("choca_con", []) if i in por_id],
            "nota": k.get("nota", ""),
        })
    manos = []
    for m in ctx.manos()["manos"]:
        mm = dict(m)
        mm["brief"] = texto_brief(m, por_id, clas)
        mm["choques"] = [list(p) for p in choques_declarados([c["id"] for c in m["cartas"]], clas)]
        manos.append(mm)
    todas = sorted((i for i, t in tabla.items() if not t["comodin"]),
                   key=lambda i: (tabla[i]["exacto"], i))
    barajas = {c: escalera_campo(c, cartas, clas, tabla, todas=True) for c in CAMPOS_ID}
    return {"generado": hoy(), "cartas": salida, "manos": manos,
            "baraja": todas, "barajas": barajas, "rangos": list(RANGOS),
            "naipes": [{"id": a, "simbolo": b[0], "nombre": b[1]} for a, b in NAIPES.items()],
            "pesos": [{"id": a, "max": b} for a, b in PESOS_POTENCIA],
            "campos": [{"id": a, "nombre": b, "familia": FAMILIA_DE[a]} for a, b in CAMPOS],
            "familias": [{"id": a, "nombre": b} for a, b in FAMILIAS],
            "limites": {"min": MIN_CARTAS, "max": MAX_CARTAS}}


def cmd_demo(ctx, args):
    if not ctx.plantilla.exists():
        raise ErrorGambit(f"Falta la plantilla: {ctx.plantilla}")
    plantilla = ctx.plantilla.read_text(encoding="utf-8")
    if MARCADOR not in plantilla:
        raise ErrorGambit(f"La plantilla no tiene el marcador {MARCADOR}.")
    datos = datos_demo(ctx)
    crudo = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    crudo = crudo.replace("</", "<\\/").replace("<!--", "<\\u0021--")
    html = plantilla.replace(MARCADOR, crudo)
    ctx.demo.parent.mkdir(parents=True, exist_ok=True)
    ctx.demo.write_text(html, encoding="utf-8", newline="\n")
    # demo/index.html es el fragmento que se publica como Artifact (el visor pone el esqueleto);
    # docs/index.html lo envuelve en un documento completo para GitHub Pages y para abrirlo del disco.
    ctx.pages.parent.mkdir(parents=True, exist_ok=True)
    ctx.pages.write_text(ESQUELETO_LOCAL + html + "\n</body>\n</html>\n", encoding="utf-8", newline="\n")
    sin = sum(1 for c in datos["cartas"] if not c["campos"])
    print(f"Demo generada: {ctx.demo} ({len(html) // 1024} KB, {len(datos['cartas'])} cartas, "
          f"{len(datos['manos'])} manos, {sin} sin clasificar).")
    return 0


# ---------------------------------------------------------------------- main

def construir_parser():
    p = argparse.ArgumentParser(prog="gambit", description="Crupier de la baraja de ideas.")
    p.add_argument("--baraja", help="ruta de baraja.json (solo lectura)")
    p.add_argument("--datos", help="carpeta de clasificacion.json y manos.json")
    p.add_argument("--demo", help="ruta de salida de la demo")
    p.add_argument("--plantilla", help="plantilla HTML de la demo")
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("sync", help="cartas sin clasificar, cambiadas o sin carta")
    x.add_argument("--detalle", action="store_true", help="incluye cómo, cuándo y evitar")
    x = s.add_parser("ver", help="vista compacta de cartas por id")
    x.add_argument("ids", nargs="+")
    s.add_parser("clasificar", help="guarda clasificaciones (JSON por stdin)")
    x = s.add_parser("campos", help="catálogo o cartas de un campo")
    x.add_argument("campo", nargs="?")
    s.add_parser("puntuar", help="guarda impacto, carga, usada_en y comodin (JSON por stdin)")
    x = s.add_parser("potencia", help="sin id recalcula y guarda; con id muestra el desglose")
    x.add_argument("id", nargs="?")
    x = s.add_parser("ranking", help="cartas de mayor a menor potencia")
    x.add_argument("--campo")
    x.add_argument("--palo")
    x.add_argument("--familia", help="desarrollo o general")
    x.add_argument("--n", type=int, default=20)
    x = s.add_parser("mano", help="crear (stdin), ver, brief, borrar o escalera CAMPO")
    x.add_argument("accion", choices=("crear", "ver", "brief", "borrar", "escalera"))
    x.add_argument("id", nargs="?")
    s.add_parser("manos", help="lista de manos")
    s.add_parser("demo", help="genera demo/index.html")
    s.add_parser("stats", help="conteos")
    return p


def main(argv=None, entrada=None):
    args = construir_parser().parse_args(argv)
    ctx = Ctx(args.baraja, args.datos, args.demo, args.plantilla)
    try:
        if args.cmd == "sync":
            return cmd_sync(ctx, args)
        if args.cmd == "ver":
            return cmd_ver(ctx, args)
        if args.cmd == "clasificar":
            return cmd_clasificar(ctx, args, entrada)
        if args.cmd == "campos":
            return cmd_campos(ctx, args)
        if args.cmd == "mano":
            return cmd_mano(ctx, args, entrada)
        if args.cmd == "manos":
            return cmd_manos(ctx, args)
        if args.cmd == "demo":
            return cmd_demo(ctx, args)
        if args.cmd == "puntuar":
            return cmd_puntuar(ctx, args, entrada)
        if args.cmd == "potencia":
            return cmd_potencia(ctx, args)
        if args.cmd == "ranking":
            return cmd_ranking(ctx, args)
        if args.cmd == "stats":
            return cmd_stats(ctx, args)
    except ErrorGambit as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    sys.exit(main())
