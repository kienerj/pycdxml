from pathlib import Path
from lxml import etree as ET
from pycdxml.cdxml_converter import read_cdx
import logging

logger = logging.getLogger('pycdxml.utils.style')


def get_style_from_template(template):
    """
    Generates a style dict from an existing chemdraw file

    :param template: a file object, a path or str to a cdx or cdxml file or a string containing the xml
    """
    if isinstance(template, str):
        p = Path(template)
    elif isinstance(template, Path):
        p = template
    else:
        raise TypeError(f"Expected str or Path but got {type(template)} instead.")

    if p.exists():
        if p.suffix == '.cdxml':
            with open(template, mode='r') as file:
                cdxml = file.read()
                style_dict = cdxml_str_to_style_dict(cdxml)
        elif p.suffix == '.cdx' or p.suffix == '.cds':
            doc = read_cdx(template)
            cdxml = doc.to_cdxml()
            style_dict = cdxml_str_to_style_dict(cdxml)
    elif template.startswith("<?xml"):
        style_dict = cdxml_str_to_style_dict(template)
    else:
        raise ValueError(f"Template file {template} does not exists.")

    return style_dict


def cdxml_str_to_style_dict(cdxml: str):
    cdxml = cdxml.encode('utf-8')
    tree = ET.fromstring(cdxml)
    # determine default font
    font_table = get_font_table(tree)
    style_dict = tree.attrib
    font_id = int(style_dict["LabelFont"])
    style_dict["LabelFont"] = font_table.get_font_name(font_id)
    return style_dict


def get_font_table(cdxml: ET.Element):

    fonttable_xml = cdxml.find("fonttable")
    if fonttable_xml is None:
        fonttable_xml = ET.SubElement(cdxml, 'fonttable')
    font_table = FontTable(fonttable_xml)
    return font_table


class FontTable:
    """
    Helper class to manage font_table in cdxml documents.

    font_table is the xml fonttable element
    """

    def __init__(self, font_table: ET.Element):

        if font_table is None:
            raise ValueError("font_table argument can't be None.")
        self.font_table = font_table
        self.font_table_dict = {}
        # initialize helper dict
        for font in font_table.iter("font"):
            font_name = font.attrib["name"]
            font_id = int(font.attrib["id"])
            self.font_table_dict[font_id] = font_name

    def get_font_name(self, font_id: int) -> str:
        return self.font_table_dict[font_id]

    def get_font_id(self, font_name) -> int:
        for key, value in self.font_table_dict.items():
            if font_name == value:
                return key

    def contains_font(self, font_name):
        return font_name in self.font_table_dict.values()

    def get_default_font_id(self):
        """
        Returns font with the lowest font_id
        """
        return min(self.font_table_dict.keys())

    def add_font(self, font_name: str, charset: str = "iso-8859-1") -> int:
        """
        Add new font to font table and return the id of the new font.

        Font name and charset are not validated. They are taken as-is (string value). It is up to the caller to
        ensure proper values.

        :param font_name: a Font name like Arial
        :param charset: character set of this font. Default is latin-1 (iso-8859-1)
        :return: int, id of the font
        """
        if self.contains_font(font_name):
            return self.get_font_id(font_name)
        else:
            if len(self.font_table_dict) > 0:
                font_id = max(self.font_table_dict.keys()) + 1
            else:
                # first font entry
                font_id = 1

            c = ET.SubElement(self.font_table, 'font')
            c.attrib["id"] = str(font_id)
            c.attrib["charset"] = charset
            c.attrib["name"] = font_name
            self.font_table_dict[font_id] = font_name
            return font_id

