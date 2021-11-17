from lxml import etree as ET
import re

CDXML_HEADER = """<?xml version="1.0" encoding="UTF-8" ?>
"""


def etree_to_cdxml(xml: ET) -> str:
    """
    Creates a cdxml string from the given lxml ElementTree instance with the correct xml headers.
    ChemDraw requires these headers to be set exactly like this or else the file is not recognized as cdxml
    """
    xml = ET.tostring(xml, encoding='unicode', method='xml',
                      doctype="<!DOCTYPE CDXML SYSTEM \"http://www.cambridgesoft.com/xml/cdxml.dtd\" >")
    return CDXML_HEADER + xml


def clean_cdxml(cdxml: str) -> str:
    """
    In some cases, especially legacy files from older ChemDraw versions converted to cdxml, the cdxml file contains many
    unneeded attributes like "attrib4000" with what appears to be a long hex string as value or sometimes there are many
    unneeded attributes like "attrib044a="|x|00" which are often coupled with color="|x|0000" and bgcolor="|x|0100"
    which when opened in ChemDraw simply leads to a all black document.

    This method cleans up this "legacy junk".
    """

    cdxml = re.sub(r"(?m) attrib[a-z0-9]{4,}=\".+?\"\r?\n", "", cdxml)
    cdxml = cdxml.replace(" color=\"|x|0000\"\n", "")
    cdxml = cdxml.replace(" bgcolor=\"|x|0100\"\n", "")

    return cdxml