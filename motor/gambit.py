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
]
CAMPOS_ID = [c[0] for c in CAMPOS]
NIVELES = ("estudiante", "intermedio", "avanzado")
COSTOS = ("gratis", "pago", "depende")
TIPOS = ("escalera", "color", "par", "libre")
MIN_CARTAS, MAX_CARTAS = 3, 7
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
    if err:
        return None, err
    limpios.sort(key=lambda x: (-x["peso"], CAMPOS_ID.index(x["campo"])))
    limpia = {"campos": limpios, "nivel": nivel, "costo": costo,
              "combina_con": relaciones["combina_con"],
              "choca_con": relaciones["choca_con"]}
    nota = " ".join(str(entrada.get("nota") or "").split())
    if nota:
        limpia["nota"] = nota
    return limpia, []


def cmd_clasificar(ctx, args, entrada=None):
    datos = leer_entrada(entrada)
    if isinstance(datos, dict):
        datos = datos.get("cartas", [datos] if "id" in datos else [])
    if not isinstance(datos, list) or not datos:
        raise ErrorGambit("Se espera una lista de clasificaciones.")
    por_id = {c["id"]: c for c in ctx.cartas()}
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
        clas["cartas"][cid] = limpia
    clas["cartas"] = dict(sorted(clas["cartas"].items()))
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
        for cid, nombre in CAMPOS:
            lista = filas[cid]
            prin = sum(1 for x in lista if x["peso"] == 3)
            print(f"{cid:<18} {len(lista):>3} cartas ({prin} principales) · {nombre}")
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
    salida = []
    for c in cartas:
        k = clas.get(c["id"], {})
        salida.append({
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
    return {"generado": hoy(), "cartas": salida, "manos": manos,
            "campos": [{"id": a, "nombre": b} for a, b in CAMPOS],
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
    x = s.add_parser("mano", help="crear (stdin), ver, brief o borrar una mano")
    x.add_argument("accion", choices=("crear", "ver", "brief", "borrar"))
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
