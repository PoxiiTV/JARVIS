"""Genera el icono de J.A.R.V.I.S. (reactor arc) en .ico y .png.

Se dibuja a 1024 px y se reduce, para que los bordes salgan suaves sin
depender de fuentes ni de recursos externos.

Uso:  python make_icon.py
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024                      # lienzo de trabajo
C = S // 2                    # centro

FONDO = (8, 12, 20, 255)      # azul casi negro
CIAN = (94, 234, 255)
CIAN_TENUE = (46, 150, 190)
BLANCO = (232, 252, 255)


def anillo(draw, radio, grosor, color):
    caja = [C - radio, C - radio, C + radio, C + radio]
    draw.ellipse(caja, outline=color, width=grosor)


def main():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Disco de fondo
    d.ellipse([0, 0, S, S], fill=FONDO)
    anillo(d, C - 12, 14, CIAN_TENUE)

    # Capa de brillo (se difumina al final para el efecto "encendido")
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)

    # Anillo exterior segmentado: 12 arcos con hueco entre ellos
    r_ext = 385
    for i in range(12):
        ini = i * 30 + 4
        g.arc([C - r_ext, C - r_ext, C + r_ext, C + r_ext],
              ini, ini + 22, fill=CIAN, width=26)

    # Triángulo del reactor (la forma característica)
    r_tri = 255
    pts = [(C + r_tri * math.cos(math.radians(a)),
            C + r_tri * math.sin(math.radians(a)))
           for a in (-90, 30, 150)]
    g.polygon(pts, outline=CIAN, width=22)

    # Bobinas: circulitos en los vértices del triángulo
    for x, y in pts:
        g.ellipse([x - 34, y - 34, x + 34, y + 34], outline=CIAN, width=16)

    # Núcleo
    g.ellipse([C - 132, C - 132, C + 132, C + 132], outline=CIAN, width=20)
    g.ellipse([C - 78, C - 78, C + 78, C + 78], fill=BLANCO)

    # Difuminar una copia del brillo y componer: nitido encima, halo debajo
    halo = glow.filter(ImageFilter.GaussianBlur(26))
    img = Image.alpha_composite(img, halo)
    img = Image.alpha_composite(img, glow)

    # Recortar a circulo (evita esquinas oscuras en iconos redondeados)
    mascara = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mascara).ellipse([0, 0, S, S], fill=255)
    img.putalpha(mascara)

    png = os.path.join(HERE, "icon.png")
    ico = os.path.join(HERE, "icon.ico")
    img.resize((512, 512), Image.LANCZOS).save(png)
    # El .ico lleva todos los tamanos que Windows pide (barra, escritorio, alt-tab)
    img.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                         (64, 64), (128, 128), (256, 256)])
    print(f"OK icono generado:\n  {png}\n  {ico}")


if __name__ == "__main__":
    main()
