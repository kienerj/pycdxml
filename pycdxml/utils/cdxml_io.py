from lxml import etree as ET

CDXML_HEADER = """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE CDXML SYSTEM "http://www.cambridgesoft.com/xml/cdxml.dtd" >
"""


def etree_to_cdxml(xml: ET):
    """
    Creates a cdxml string from the given lxml ElementTree instance with the correct xml headers.
    ChemDraw requires these headers to be set exactly like this or else the file is not recognized as cdxml
    """
    xml = ET.tostring(xml, encoding='unicode', method='xml')
    return CDXML_HEADER + xml