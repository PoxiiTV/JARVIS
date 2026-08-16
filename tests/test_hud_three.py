"""El HUD carga la esfera holográfica (demo núcleo 3D), no el reactor plano."""
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def test_esfera_holografica_en_el_hud():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "hud.css").read_text(encoding="utf-8")
    js_path = STATIC / "hud-three.js"
    assert js_path.is_file()
    js = js_path.read_text(encoding="utf-8")

    assert "hud-three.js" in html
    blob = html + js
    assert "OrbitControls" in blob
    assert "UnrealBloomPass" in blob
    assert "function initThree" in js
    assert "autoRotate" in js
    assert "IcosahedronGeometry" in js
    assert "SphereGeometry(16" not in html
    canvas = next(ln for ln in css.splitlines() if "#hud canvas" in ln)
    assert "pointer-events: none" not in canvas
    assert re.search(r"#core-label\s*\{[^}]*display:\s*none", css, re.S)


def test_nucleo_tiene_jarvis_3d():
    js = (STATIC / "hud-three.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "TextGeometry" in js
    assert "FontLoader" in js
    assert "'JARVIS'" in js or '"JARVIS"' in js
    assert "marca.lookAt" in js
    assert "marca.rotation.y" not in js
    assert "marca.rotateY(Math.PI)" not in js
    assert "globe.add(marca)" in js
    assert "PlaneGeometry(52" not in js
    assert "/static/fonts/" in js
    font = STATIC / "fonts" / "helvetiker_bold.typeface.json"
    assert font.is_file()
    assert "hud-three.js" in html
    assert "matFront = new THREE.MeshBasicMaterial({ color: 0xffffff })" in js


def test_ajustes_tienen_enfadado():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "['angry', 'Enfadado']" in html


def test_ajustes_tienen_selector_personalidad():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="cfg-persona"' in html
    assert "Personalidad" in html


if __name__ == "__main__":
    test_esfera_holografica_en_el_hud()
    test_nucleo_tiene_jarvis_3d()
    test_ajustes_tienen_enfadado()
    test_ajustes_tienen_selector_personalidad()
    print("OK")
