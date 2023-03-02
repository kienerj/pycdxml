from fontTools.ttLib import TTFont
from matplotlib import font_manager


def get_font_by_name(name: str, fallback_to_default=False):
    """
    Returns path to ttf-file of the given font-name
    Raises ValueError if font is not found
    """
    font_path = font_manager.findfont("Arial", fontext='ttf', fallback_to_default=True)
    return TTFont(font_path)


def get_text_width(text, font: TTFont, font_size: int):
    cmap = font['cmap']
    t = cmap.getBestCmap()
    s = font.getGlyphSet()
    units_per_em = font['head'].unitsPerEm
    total = 0
    for c in text:
        if ord(c) in t and t[ord(c)] in s:
            total += s[t[ord(c)]].width
        else:
            total += s['.notdef'].width
    total = total*float(font_size)/units_per_em;
    return total