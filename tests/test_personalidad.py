"""El tono lo elige el ajuste PERSONALIDAD, no el nombre del chip de voz."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.brain import _mensajes_base
from app.config import Config
from app.personalidad import bloque, opciones, slug_activo, slug_de


def test_slug_fermin_por_alias():
    assert slug_de("Fermín Trujillo") == "fermin"
    assert slug_de("fermin") == "fermin"


def test_slug_kratos_y_tobey_por_alias():
    assert slug_de("Kratos") == "kratos"
    assert slug_de("Tobey Maguire") == "tobey"
    assert slug_de("Spider-Man") == "tobey"


def test_slug_amador_por_alias():
    assert slug_de("Amador") == "amador"
    assert slug_de("Amador Rivas") == "amador"


def test_slug_saul_por_alias():
    assert slug_de("Saul") == "saul"
    assert slug_de("Saúl") == "saul"


def test_slug_sergio_por_alias():
    assert slug_de("Sergio") == "sergio"


def test_slug_activo_sale_del_ajuste():
    assert slug_activo("jarvis") is None
    assert slug_activo("") is None
    assert slug_activo("-") is None
    assert slug_activo("fermin") == "fermin"
    assert slug_activo("kratos") == "kratos"
    assert slug_activo("tobey") == "tobey"
    assert slug_activo("amador") == "amador"
    assert slug_activo("saul") == "saul"
    assert slug_activo("sergio") == "sergio"
    assert slug_activo("no-existe") is None


def test_opciones_empiezan_por_jarvis():
    ops = opciones()
    slugs = [o["slug"] for o in ops]
    assert slugs[0] == "jarvis"
    assert "fermin" in slugs
    assert "kratos" in slugs
    assert "tobey" in slugs
    assert "amador" in slugs
    assert "saul" in slugs
    assert "sergio" in slugs


def test_bloque_por_slug():
    t = bloque("fermin")
    assert t
    assert "fermín" in t.lower() or "fermin" in t.lower()
    assert "nunca inventes" in t.lower() or "verdad" in t.lower()
    assert bloque("jarvis") is None
    assert "kratos" in bloque("kratos").lower()
    assert "tobey" in bloque("tobey").lower() or "spider" in bloque("tobey").lower()
    a = bloque("amador")
    assert a
    assert "amador" in a.lower()
    assert "nunca inventes" in a.lower() or "verdad" in a.lower()
    bajo = a.lower()
    assert "merengue" in bajo
    assert "solo si" in bajo or "no las sueltes" in bajo or "no recites" in bajo


SECCIONES_LQSA = (
    "IDENTIDAD", "MENTALIDAD", "CÓMO HABLA", "NUNCA", "ÓRDENES", "COLETILLAS", "BOCA",
)


def _seccion(texto, titulo):
    marca = "\n" + titulo + "\n"
    idx = texto.find(marca)
    if idx < 0 and texto.startswith(titulo + "\n"):
        idx = 0
        marca = titulo + "\n"
    assert idx >= 0, titulo
    rest = texto[idx + len(marca):]
    cut = len(rest)
    for s in SECCIONES_LQSA:
        if s == titulo:
            continue
        p = rest.find("\n" + s + "\n")
        if 0 <= p < cut:
            cut = p
    return rest[:cut]


def test_fichas_lqsa_tienen_plantilla():
    for slug in ("fermin", "amador", "saul", "sergio"):
        t = bloque(slug)
        for s in SECCIONES_LQSA:
            assert s in t, f"{slug} sin {s}"
        nunca = _seccion(t, "NUNCA").lower()
        assert "no recit" in nunca or "sin ninguna frase" in nunca or "anti-recit" in nunca
        ordenes = _seccion(t, "ÓRDENES")
        assert "escritorio" in ordenes.lower()
        assert "html" in ordenes.lower()
        assert "[confident]" in ordenes
        assert "[angry]" in ordenes or "[calm]" in ordenes
        assert "[happy]" in ordenes


def test_ordenes_no_mezclan_personajes():
    f = _seccion(bloque("fermin"), "ÓRDENES").lower() + _seccion(bloque("fermin"), "BOCA").lower()
    a = _seccion(bloque("amador"), "ÓRDENES").lower() + _seccion(bloque("amador"), "BOCA").lower()
    assert "merengue" not in f
    assert "salami" not in f
    assert "cuqui" not in f
    assert "whiskyto" not in a
    assert "telespeto" not in a
    s = _seccion(bloque("saul"), "ÓRDENES").lower() + _seccion(bloque("saul"), "BOCA").lower()
    assert "whiskyto" not in s
    assert "merengue" not in s
    assert "telespeto" not in s
    assert "señor" not in s


def test_tics_se_inyectan_y_se_abusan():
    from app.personalidad import DIR
    for slug in ("fermin", "amador"):
        assert (DIR / f"{slug}.tics.txt").is_file()
        t = bloque(slug).lower()
        assert "casi cada" in t
        assert "tics" in t
    f = _seccion(bloque("fermin"), "ÓRDENES").lower()
    assert "madre mía" in f or "madre mia" in f
    assert "eh?" in f
    a = _seccion(bloque("amador"), "ÓRDENES").lower()
    assert "te lo digo yo" in a
    assert a.count("tío") + a.count("tio") >= 4
    assert "colega" not in a
    assert "tronco" not in a
    tics = (DIR / "amador.tics.txt").read_text(encoding="utf-8").lower()
    assert "colega" not in tics
    assert "tronco" not in tics
    boca = _seccion(bloque("amador"), "BOCA").lower()
    assert "colega" not in boca
    assert "tronco" not in boca


def test_saul_habla_como_en_el_chat():
    from app.personalidad import DIR
    assert (DIR / "saul.tics.txt").is_file()
    t = bloque("saul")
    bajo = t.lower()
    assert "bro" in bajo
    assert "vale" in bajo
    assert "en plan" in bajo
    assert "fuera coñas" in bajo
    assert "un tic" in bajo
    o = _seccion(t, "ÓRDENES").lower()
    assert "bro" in o
    assert "xd" not in o
    assert "uwu" not in o
    assert "tío" not in o and "tio" not in o
    k = (bloque("kratos") or "").lower()
    assert "fuera coñas" not in k


def test_colegas_no_citan_el_origen():
    for slug in ("saul", "sergio"):
        t = bloque(slug).lower()
        assert "whatsapp" not in t
        assert "discord" not in t
        assert "colega de" not in t


def test_sergio_habla_como_en_el_chat():
    from app.personalidad import DIR
    assert (DIR / "sergio.tics.txt").is_file()
    t = bloque("sergio")
    bajo = t.lower()
    assert "brother" in bajo
    assert "da igual" in bajo
    assert "qué locura" in bajo or "que locura" in bajo
    assert "un tic" in bajo
    o = _seccion(t, "ÓRDENES").lower()
    assert "brother" in o
    assert "jajaja" not in o
    assert "fuera coñas" not in o
    s = _seccion(bloque("saul"), "ÓRDENES").lower()
    assert "fuera coñas" in s
    assert "qué locura" not in s and "que locura" not in s


def test_amador_tuerce_refranes():
    from app.personalidad import DIR
    assert (DIR / "amador.dichos.txt").is_file()
    t = bloque("amador").lower()
    assert "poco de pato" in t
    assert "godzilla" in t
    assert "obelisco" in t
    assert "al reves" in t or "al revés" in t or "troc" in t
    assert "dislex" in t


def test_historia_se_inyecta_y_no_se_mezcla():
    from app.personalidad import DIR
    assert (DIR / "amador.historia.md").is_file()
    assert (DIR / "fermin.historia.md").is_file()
    a = bloque("amador").lower()
    f = bloque("fermin").lower()
    assert "memoria del personaje" in a
    assert "memoria del personaje" in f
    assert "no recites" in a or "no recit" in a
    assert "limpia-cacas" in a
    assert "amador arias" in a
    assert "temporada 13" in a
    assert "payaso justiciero" in f
    assert "kornelious" in f
    assert "temporada 16" in f
    assert "limpia-cacas" not in f
    assert "payaso justiciero" not in a
    k = (bloque("kratos") or "").lower()
    assert "limpia-cacas" not in k
    assert "payaso justiciero" not in k


def test_mensajes_siguen_personalidad_no_el_chip():
    orig_p = getattr(Config, "PERSONALIDAD", "jarvis")
    orig_v = getattr(Config, "VOZ_NOMBRE", "")
    try:
        Config.VOZ_NOMBRE = "Kratos"
        Config.PERSONALIDAD = "jarvis"
        sys_j = "\n".join(
            m["content"] for m in _mensajes_base("hola", None) if m["role"] == "system"
        )
        assert "kratos" not in sys_j.lower()
        Config.PERSONALIDAD = "tobey"
        sys_t = "\n".join(
            m["content"] for m in _mensajes_base("hola", None) if m["role"] == "system"
        )
        assert "tobey" in sys_t.lower() or "spider" in sys_t.lower()
        assert "kratos" not in sys_t.lower()
    finally:
        Config.PERSONALIDAD = orig_p
        Config.VOZ_NOMBRE = orig_v


if __name__ == "__main__":
    test_slug_fermin_por_alias()
    test_slug_kratos_y_tobey_por_alias()
    test_slug_amador_por_alias()
    test_slug_saul_por_alias()
    test_slug_sergio_por_alias()
    test_slug_activo_sale_del_ajuste()
    test_opciones_empiezan_por_jarvis()
    test_bloque_por_slug()
    test_fichas_lqsa_tienen_plantilla()
    test_ordenes_no_mezclan_personajes()
    test_tics_se_inyectan_y_se_abusan()
    test_saul_habla_como_en_el_chat()
    test_colegas_no_citan_el_origen()
    test_sergio_habla_como_en_el_chat()
    test_amador_tuerce_refranes()
    test_historia_se_inyecta_y_no_se_mezcla()
    test_mensajes_siguen_personalidad_no_el_chip()
    print("OK")
