# -*- coding: utf-8 -*-
"""Pruebas de Gambit: cd motor && python -m unittest test_gambit"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import gambit


def carta(cid, palo="composición", mazo="diseño web", **extra):
    base = {"id": cid, "mazo": mazo, "palo": palo, "nombre": f"Carta {cid}",
            "idea": f"Idea de {cid}", "como": "Con CSS", "cuando": "Siempre",
            "evitar": "Abusar", "dificultad": 1, "stack": "CSS", "etiquetas": ["x"],
            "fuentes": [{"url": "https://example.com/p/1", "creador": "@alguien",
                         "plataforma": "instagram", "fecha": "2026-11-01"}],
            "agregada": "2026-11-12"}
    base.update(extra)
    return base


def clas(cid, campo="frontend", **extra):
    base = {"id": cid, "campos": [{"campo": campo, "peso": 3, "aplicacion": "Se usa así"}],
            "nivel": "estudiante", "costo": "gratis"}
    base.update(extra)
    return base


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.baraja = self.dir / "baraja.json"
        self.datos = self.dir / "datos"
        self.demo = self.dir / "demo" / "index.html"
        self.plantilla = self.dir / "plantilla.html"
        self.plantilla.write_text(
            '<!doctype html><title>t</title><script type="application/json" id="datos">'
            + gambit.MARCADOR + "</script>", encoding="utf-8")
        self.cartas = [carta("dis-001"), carta("dis-002", palo="movimiento"),
                       carta("dis-003", palo="movimiento"), carta("age-001", "arquitectura", "agentes ia")]
        self.escribir_baraja()

    def tearDown(self):
        self.tmp.cleanup()

    def escribir_baraja(self):
        self.baraja.write_text(json.dumps(
            {"cartas": self.cartas, "vistos": [], "prefijos": {}}, ensure_ascii=False), encoding="utf-8")

    def correr(self, *argv, entrada=None):
        out, err = io.StringIO(), io.StringIO()
        base = ["--baraja", str(self.baraja), "--datos", str(self.datos),
                "--demo", str(self.demo), "--plantilla", str(self.plantilla)]
        if entrada is not None and not isinstance(entrada, str):
            entrada = json.dumps(entrada, ensure_ascii=False)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            codigo = gambit.main(base + list(argv), entrada=entrada)
        return codigo, out.getvalue(), err.getvalue()

    def clasificar_todas(self):
        codigo, _, err = self.correr("clasificar", entrada=[
            clas("dis-001"), clas("dis-002", "movimiento", choca_con=["dis-003"]),
            clas("dis-003", "movimiento"), clas("age-001", "ia")])
        self.assertEqual(codigo, 0, err)


class TestSync(Base):
    def test_todas_nuevas(self):
        codigo, out, _ = self.correr("sync")
        self.assertEqual(codigo, 0)
        self.assertIn("Sin clasificar: 4", out)
        self.assertIn("dis-001 | composición | Carta dis-001 | Idea de dis-001", out)

    def test_sin_pendientes(self):
        self.clasificar_todas()
        _, out, _ = self.correr("sync")
        self.assertIn("Sin pendientes.", out)

    def test_carta_nueva(self):
        self.clasificar_todas()
        self.cartas.append(carta("bac-001", "apis", "backend"))
        self.escribir_baraja()
        _, out, _ = self.correr("sync")
        self.assertIn("Sin clasificar: 1", out)
        self.assertIn("bac-001 | apis", out)

    def test_carta_cambiada(self):
        self.clasificar_todas()
        self.cartas[0]["como"] = "Con otra técnica"
        self.escribir_baraja()
        _, out, _ = self.correr("sync")
        self.assertIn("Cambiadas: 1", out)
        self.assertIn("CAMBIARON", out)
        self.assertIn("dis-001", out.split("CAMBIARON")[1])

    def test_fuente_nueva_no_cuenta_como_cambio(self):
        self.clasificar_todas()
        self.cartas[0]["fuentes"].append({"url": "https://example.com/p/2"})
        self.escribir_baraja()
        _, out, _ = self.correr("sync")
        self.assertIn("Sin pendientes.", out)

    def test_clasificada_sin_carta(self):
        self.clasificar_todas()
        self.cartas.pop()
        self.escribir_baraja()
        _, out, _ = self.correr("sync")
        self.assertIn("Sin carta: 1", out)
        self.assertIn("age-001", out)

    def test_baraja_no_se_modifica(self):
        antes = self.baraja.read_bytes()
        self.clasificar_todas()
        self.correr("sync")
        self.correr("stats")
        self.correr("demo")
        self.assertEqual(antes, self.baraja.read_bytes())


class TestClasificar(Base):
    def test_guarda_con_huella(self):
        self.clasificar_todas()
        d = json.loads((self.datos / "clasificacion.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(d["cartas"]), ["age-001", "dis-001", "dis-002", "dis-003"])
        self.assertEqual(d["cartas"]["dis-001"]["huella"], gambit.huella(self.cartas[0]))

    def test_id_inexistente(self):
        codigo, _, err = self.correr("clasificar", entrada=[clas("dis-999")])
        self.assertEqual(codigo, 1)
        self.assertIn("no existe en la baraja", err)
        self.assertFalse((self.datos / "clasificacion.json").exists())

    def test_campo_fuera_del_catalogo(self):
        codigo, _, err = self.correr("clasificar", entrada=[clas("dis-001", "magia")])
        self.assertEqual(codigo, 1)
        self.assertIn("campo fuera del catálogo", err)

    def test_un_error_no_guarda_nada(self):
        codigo, _, _ = self.correr("clasificar", entrada=[clas("dis-001"), clas("dis-002", "magia")])
        self.assertEqual(codigo, 1)
        self.assertFalse((self.datos / "clasificacion.json").exists())

    def test_peso_nivel_costo_y_relaciones(self):
        mala = clas("dis-001", nivel="experto", costo="caro", combina_con=["dis-404"])
        mala["campos"][0]["peso"] = 5
        codigo, _, err = self.correr("clasificar", entrada=[mala])
        self.assertEqual(codigo, 1)
        for texto in ("peso inválido", "nivel inválido", "costo inválido", "'dis-404' no existe"):
            self.assertIn(texto, err)

    def test_maximo_cuatro_campos(self):
        mala = clas("dis-001")
        mala["campos"] = [{"campo": c, "peso": 1, "aplicacion": "a"} for c in gambit.CAMPOS_ID[:5]]
        codigo, _, err = self.correr("clasificar", entrada=[mala])
        self.assertEqual(codigo, 1)
        self.assertIn("de 1 a 4 campos", err)

    def test_campos_ordena_por_peso(self):
        self.correr("clasificar", entrada=[
            clas("dis-001", campos=[{"campo": "frontend", "peso": 1, "aplicacion": "poco"}]),
            clas("dis-002", campos=[{"campo": "frontend", "peso": 3, "aplicacion": "mucho"}])])
        _, out, _ = self.correr("campos", "frontend")
        self.assertLess(out.index("dis-002"), out.index("dis-001"))
        _, out, _ = self.correr("campos")
        self.assertIn("frontend", out)
        self.assertIn("2 cartas (1 principales)", out)

    def test_stats(self):
        self.clasificar_todas()
        codigo, out, _ = self.correr("stats")
        self.assertEqual(codigo, 0)
        self.assertIn("Cartas: 4 · clasificadas: 4", out)
        self.assertIn("Sin clasificar: ninguna", out)


class TestManos(Base):
    def mano(self, **extra):
        base = {"id": "mano-prueba", "nombre": "Mano de prueba", "objetivo": "Probar",
                "tipo": "libre", "por_que": "Porque sí", "conflictos": "Nada",
                "cartas": [{"id": "dis-001", "rol": "base"}, {"id": "dis-002", "rol": "entrada"},
                           {"id": "age-001", "rol": "cierre"}]}
        base.update(extra)
        return base

    def test_crear_ver_listar_brief(self):
        self.clasificar_todas()
        codigo, out, err = self.correr("mano", "crear", entrada=self.mano())
        self.assertEqual(codigo, 0, err)
        self.assertIn("Creada mano-prueba", out)
        _, out, _ = self.correr("manos")
        self.assertIn("mano-prueba | libre", out)
        _, out, _ = self.correr("mano", "ver", "mano-prueba")
        self.assertIn("1. dis-001", out)
        _, out, _ = self.correr("mano", "brief", "mano-prueba")
        for texto in ("BRIEF · Mano de prueba", "Objetivo: Probar", "1. dis-001", "Cómo: Con CSS",
                      "CONFLICTOS", "LISTO CUANDO"):
            self.assertIn(texto, out)
        self.assertLess(out.index("1. dis-001"), out.index("3. age-001"))

    def test_carta_inexistente(self):
        m = self.mano()
        m["cartas"][0]["id"] = "dis-999"
        codigo, _, err = self.correr("mano", "crear", entrada=m)
        self.assertEqual(codigo, 1)
        self.assertIn("carta inexistente", err)
        self.assertFalse((self.datos / "manos.json").exists())

    def test_limite_de_cartas(self):
        m = self.mano(cartas=[{"id": "dis-001", "rol": "a"}, {"id": "dis-002", "rol": "b"}])
        codigo, _, err = self.correr("mano", "crear", entrada=m)
        self.assertEqual(codigo, 1)
        self.assertIn("de 3 a 7 cartas", err)
        m["tipo"] = "par"
        codigo, _, _ = self.correr("mano", "crear", entrada=m)
        self.assertEqual(codigo, 0)

    def test_aviso_de_choque_y_movimiento(self):
        self.clasificar_todas()
        m = self.mano(cartas=[{"id": "dis-001", "rol": "a"}, {"id": "dis-002", "rol": "b"},
                              {"id": "dis-003", "rol": "c"}])
        codigo, out, _ = self.correr("mano", "crear", entrada=m)
        self.assertEqual(codigo, 0)
        self.assertIn("choque declarado: dis-002 con dis-003", out)
        self.assertIn("un solo momento animado", out)
        _, out, _ = self.correr("mano", "brief", "mano-prueba")
        self.assertIn("dis-002 y dis-003 están marcadas como cartas que chocan", out)

    def test_actualizar_y_borrar(self):
        self.correr("mano", "crear", entrada=self.mano())
        _, out, _ = self.correr("mano", "crear", entrada=self.mano(nombre="Otro nombre"))
        self.assertIn("Actualizada", out)
        d = json.loads((self.datos / "manos.json").read_text(encoding="utf-8"))
        self.assertEqual(len(d["manos"]), 1)
        self.assertEqual(d["manos"][0]["nombre"], "Otro nombre")
        self.correr("mano", "borrar", "mano-prueba")
        codigo, _, err = self.correr("mano", "ver", "mano-prueba")
        self.assertEqual(codigo, 1)
        self.assertIn("No existe la mano", err)

    def test_tipo_e_id_invalidos(self):
        codigo, _, err = self.correr("mano", "crear", entrada=self.mano(id="Mano X", tipo="trio"))
        self.assertEqual(codigo, 1)
        self.assertIn("id inválido", err)
        self.assertIn("tipo inválido", err)


class TestPotencia(Base):
    def test_calculo_con_desglose(self):
        self.correr("clasificar", entrada=[clas(
            "dis-001", campos=[{"campo": "frontend", "peso": 3, "aplicacion": "a"},
                               {"campo": "ux-ui", "peso": 2, "aplicacion": "b"}],
            impacto=4, carga="ligera", usada_en=["Proyecto real"])])
        d = json.loads((self.datos / "clasificacion.json").read_text(encoding="utf-8"))
        p = d["cartas"]["dis-001"]["potencia"]
        self.assertEqual(p, {"total": 75, "utilidad": 21.0, "impacto": 24.0, "evidencia": 10.0,
                             "facilidad": 10.0, "costo": 10.0})
        _, out, _ = self.correr("potencia", "dis-001")
        self.assertIn("potencia 75 de 100", out)
        self.assertIn("utilidad", out)

    def test_provisional_solo_con_datos_de_uatu(self):
        t = gambit.partes_potencia(self.cartas[0], None)
        self.assertTrue(t["provisional"])
        self.assertEqual(t["total"], 52)

    def test_percentiles_reparten_los_trece_rangos(self):
        combos = [(i, d) for i in range(1, 6) for d in (3, 2, 1)][:13]
        cartas = [carta(f"dis-{n:03d}", dificultad=d) for n, (_, d) in enumerate(combos, 1)]
        k = {c["id"]: {"campos": [{"campo": "frontend", "peso": 3}], "impacto": i, "costo": "gratis",
                       "carga": "ligera"} for c, (i, _) in zip(cartas, combos)}
        tabla = gambit.tabla_potencia(cartas, k)
        orden = sorted(tabla, key=lambda i: tabla[i]["exacto"])
        self.assertEqual([tabla[i]["rango"] for i in orden], list(gambit.RANGOS))
        self.assertEqual(sorted(t["puesto"] for t in tabla.values()), list(range(1, 14)))
        self.assertEqual(tabla[orden[-1]]["puesto"], 1)

    def test_empates_comparten_rango(self):
        cartas = [carta("dis-001"), carta("dis-002")]
        tabla = gambit.tabla_potencia(cartas, {})
        self.assertEqual(tabla["dis-001"]["rango"], tabla["dis-002"]["rango"])

    def test_carta_nueva_recibe_rango_sin_romper_las_demas(self):
        self.clasificar_todas()
        self.correr("puntuar", entrada=[{"id": "dis-001", "impacto": 5, "carga": "ligera"},
                                        {"id": "dis-002", "impacto": 2, "carga": "pesada"},
                                        {"id": "dis-003", "impacto": 3, "carga": "media"},
                                        {"id": "age-001", "impacto": 4, "carga": "media"}])
        self.cartas.append(carta("bac-001", "apis", "backend", dificultad=3))
        self.escribir_baraja()
        codigo, _, err = self.correr("demo")
        self.assertEqual(codigo, 0, err)
        datos = json.loads(self.demo.read_text(encoding="utf-8").split('id="datos">')[1].split("</script>")[0])
        por_id = {c["id"]: c for c in datos["cartas"]}
        self.assertEqual(len(por_id), 5)
        for c in por_id.values():
            self.assertIn(c["rango"], gambit.RANGOS)
            self.assertGreater(c["puesto"], 0)
        self.assertTrue(por_id["bac-001"]["pot"]["provisional"])
        self.assertFalse(por_id["dis-001"]["pot"]["provisional"])
        self.assertEqual(por_id["bac-001"]["naipe"], "picas")
        self.assertEqual(por_id["dis-001"]["puesto"], 1)
        self.assertEqual(sorted(datos["baraja"]), sorted(por_id))

    def test_comodin_va_sin_rango(self):
        self.clasificar_todas()
        self.correr("puntuar", entrada=[{"id": "dis-001", "impacto": 5, "comodin": True}])
        d = json.loads((self.datos / "clasificacion.json").read_text(encoding="utf-8"))
        self.assertEqual(d["cartas"]["dis-001"]["rango"], "")
        self.assertEqual(d["cartas"]["dis-001"]["puesto"], 0)
        self.assertEqual(sorted(k["puesto"] for i, k in d["cartas"].items() if i != "dis-001"), [1, 2, 3])
        _, out, _ = self.correr("ranking")
        self.assertIn("comodín", out)

    def test_puntuar_valida(self):
        self.clasificar_todas()
        codigo, _, err = self.correr("puntuar", entrada=[{"id": "dis-001", "impacto": 9, "carga": "enorme"}])
        self.assertEqual(codigo, 1)
        self.assertIn("impacto inválido", err)
        self.assertIn("carga inválida", err)
        self.cartas.append(carta("bac-001", "apis", "backend"))
        self.escribir_baraja()
        codigo, _, err = self.correr("puntuar", entrada=[{"id": "bac-001", "impacto": 3}])
        self.assertEqual(codigo, 1)
        self.assertIn("aún no está clasificada", err)

    def test_reclasificar_conserva_la_puntuacion(self):
        self.clasificar_todas()
        self.correr("puntuar", entrada=[{"id": "dis-001", "impacto": 5, "carga": "ligera", "usada_en": ["X"]}])
        self.correr("clasificar", entrada=[clas("dis-001", "ux-ui")])
        d = json.loads((self.datos / "clasificacion.json").read_text(encoding="utf-8"))
        k = d["cartas"]["dis-001"]
        self.assertEqual((k["impacto"], k["carga"], k["usada_en"]), (5, "ligera", ["X"]))
        self.assertEqual(k["campos"][0]["campo"], "ux-ui")

    def test_palo_de_naipe(self):
        casos = [(carta("x-1", "tipografía"), "corazones"), (carta("x-2", "presentación"), "diamantes"),
                 (carta("x-3", "3d y canvas"), "treboles"), (carta("x-4", "casos de uso", "agentes ia"), "picas"),
                 (carta("x-5", "apis", "backend"), "picas"), (carta("x-6", "copy de ventas", "marketing"), "diamantes"),
                 (carta("x-7", "animaciones", "apps móviles"), "treboles")]
        for c, esperado in casos:
            self.assertEqual(gambit.naipe_de(c), esperado, c["palo"])
        self.assertEqual(gambit.naipe_de(carta("x-8", "apis", "backend"), {"naipe": "corazones"}), "corazones")

    def test_ranking_y_escalera(self):
        self.clasificar_todas()
        self.correr("puntuar", entrada=[{"id": "dis-002", "impacto": 5}, {"id": "dis-003", "impacto": 1}])
        codigo, out, _ = self.correr("ranking", "--campo", "movimiento")
        self.assertEqual(codigo, 0)
        self.assertLess(out.index("dis-002"), out.index("dis-003"))
        self.assertNotIn("dis-001", out)
        codigo, out, _ = self.correr("mano", "escalera", "movimiento")
        self.assertEqual(codigo, 0)
        self.assertLess(out.index("dis-003"), out.index("dis-002"))
        codigo, _, err = self.correr("mano", "escalera", "magia")
        self.assertEqual(codigo, 1)
        self.assertIn("Campo fuera del catálogo", err)
        codigo, _, err = self.correr("ranking", "--palo", "oros")
        self.assertEqual(codigo, 1)

    def test_escalera_toma_las_siete_mas_fuertes(self):
        cartas = [carta(f"dis-{n:03d}", dificultad=1 + n % 3) for n in range(1, 11)]
        k = {c["id"]: {"campos": [{"campo": "frontend", "peso": 3}], "impacto": 1 + n % 5}
             for n, c in enumerate(cartas)}
        tabla = gambit.tabla_potencia(cartas, k)
        mano = gambit.escalera_campo("frontend", cartas, k, tabla)
        self.assertEqual(len(mano), 7)
        totales = [tabla[i]["exacto"] for i in mano]
        self.assertEqual(totales, sorted(totales))
        fuera = [tabla[c["id"]]["exacto"] for c in cartas if c["id"] not in mano]
        self.assertLessEqual(max(fuera), min(totales))
        self.assertEqual(len(gambit.escalera_campo("frontend", cartas, k, tabla, todas=True)), 10)


class TestFamilias(Base):
    def test_campos_generales_validos(self):
        self.cartas.append(carta("fin-001", "inversión", "finanzas"))
        self.escribir_baraja()
        codigo, _, err = self.correr("clasificar", entrada=[clas("fin-001", "finanzas", campos=[
            {"campo": "finanzas", "peso": 3, "aplicacion": "a"},
            {"campo": "productividad", "peso": 2, "aplicacion": "b"}])])
        self.assertEqual(codigo, 0, err)
        _, out, _ = self.correr("campos")
        self.assertLess(out.index("Desarrollo"), out.index("Conocimiento general"))
        self.assertLess(out.index("Conocimiento general"), out.index("finanzas"))
        d = json.loads((self.datos / "clasificacion.json").read_text(encoding="utf-8"))
        self.assertEqual(d["cartas"]["fin-001"]["familia"], "general")

    def test_familia_principal_y_mixta(self):
        c = carta("x-1")
        k = {"campos": [{"campo": "ia-general", "peso": 3}, {"campo": "frontend", "peso": 2}]}
        self.assertEqual(gambit.familia_de(c, k), ("general", ["desarrollo", "general"]))
        k = {"campos": [{"campo": "ia-general", "peso": 2}, {"campo": "frontend", "peso": 2}]}
        self.assertEqual(gambit.familia_de(c, k)[0], "desarrollo")
        k = {"campos": [{"campo": "cultura", "peso": 2}, {"campo": "actualidad", "peso": 2}, {"campo": "frontend", "peso": 2}]}
        self.assertEqual(gambit.familia_de(c, k)[0], "general")

    def test_familia_sin_clasificar_por_mazo(self):
        self.assertEqual(gambit.familia_de(carta("x-1"))[0], "desarrollo")
        self.assertEqual(gambit.familia_de(carta("x-2", mazo="agentes ia"))[0], "desarrollo")
        self.assertEqual(gambit.familia_de(carta("x-3", mazo="backend"))[0], "desarrollo")
        self.assertEqual(gambit.familia_de(carta("x-4", mazo="finanzas"))[0], "general")
        self.assertEqual(gambit.familia_de(carta("x-5", mazo="ciencia y salud"))[0], "general")

    def test_palos_de_mazos_generales(self):
        casos = [("ciencia y salud", "corazones"), ("cultura", "corazones"), ("finanzas", "diamantes"),
                 ("negocios", "diamantes"), ("actualidad", "treboles"), ("ia", "picas"),
                 ("tecnología", "picas"), ("productividad", "picas"), ("música", "corazones"),
                 ("emprendimiento", "diamantes"), ("noticias del día", "treboles"), ("otro tema", "picas")]
        for mazo, esperado in casos:
            self.assertEqual(gambit.naipe_de(carta("x-1", "consejos", mazo)), esperado, mazo)

    def test_ranking_por_familia(self):
        self.cartas.append(carta("fin-001", "inversión", "finanzas"))
        self.escribir_baraja()
        self.clasificar_todas()
        self.correr("clasificar", entrada=[clas("fin-001", "finanzas")])
        _, out, _ = self.correr("ranking", "--familia", "general")
        self.assertIn("fin-001", out)
        self.assertNotIn("dis-001", out)
        _, out, _ = self.correr("ranking", "--familia", "desarrollo")
        self.assertNotIn("fin-001", out)
        codigo, _, err = self.correr("ranking", "--familia", "otra")
        self.assertEqual(codigo, 1)
        self.assertIn("Familia inválida", err)


class TestDemo(Base):
    def test_genera_html_con_datos(self):
        self.clasificar_todas()
        self.correr("mano", "crear", entrada=TestManos.mano(self))
        codigo, out, err = self.correr("demo")
        self.assertEqual(codigo, 0, err)
        html = self.demo.read_text(encoding="utf-8")
        self.assertNotIn(gambit.MARCADOR, html)
        crudo = html.split('id="datos">')[1].split("</script>")[0]
        datos = json.loads(crudo)
        self.assertEqual(len(datos["cartas"]), 4)
        self.assertEqual(datos["cartas"][1]["choca"], ["dis-003"])
        self.assertEqual(datos["cartas"][0]["fuentes"][0]["creador"], "@alguien")
        self.assertEqual(datos["manos"][0]["id"], "mano-prueba")
        self.assertIn("BRIEF", datos["manos"][0]["brief"])
        self.assertEqual(len(datos["campos"]), 19)
        self.assertEqual([f["id"] for f in datos["familias"]], ["desarrollo", "general"])
        self.assertEqual(datos["cartas"][0]["familia"], "desarrollo")
        pages = (self.dir / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertTrue(pages.startswith("<!doctype html>"))
        self.assertIn('name="viewport"', pages)
        self.assertIn(crudo, pages)

    def test_no_rompe_el_script(self):
        self.cartas[0]["idea"] = "Cierra </script> a medias"
        self.escribir_baraja()
        self.correr("demo")
        html = self.demo.read_text(encoding="utf-8")
        self.assertEqual(html.count("</script>"), 1)

    def test_acepta_mazos_y_palos_nuevos(self):
        self.cartas.append(carta("pro-001", "hábitos", "productividad"))
        self.escribir_baraja()
        codigo, _, _ = self.correr("demo")
        self.assertEqual(codigo, 0)
        self.assertIn("productividad", self.demo.read_text(encoding="utf-8"))

    def test_plantilla_real_tiene_marcador(self):
        real = Path(gambit.__file__).resolve().parent / "plantilla.html"
        if real.exists():
            self.assertEqual(real.read_text(encoding="utf-8").count(gambit.MARCADOR), 1)


if __name__ == "__main__":
    unittest.main()
