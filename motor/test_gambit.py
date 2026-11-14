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
        self.assertEqual(len(datos["campos"]), 12)
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
