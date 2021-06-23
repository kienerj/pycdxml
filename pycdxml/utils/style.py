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
        raise TypeError("Expected str or Path but got {} instead.".format(type(template)))

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
        raise ValueError("Template file {} does not exists.".format(template))

    return style_dict


def cdxml_str_to_style_dict(cdxml: str):
    cdxml = cdxml.encode('utf-8')
    tree = ET.fromstring(cdxml)
    return tree.attrib