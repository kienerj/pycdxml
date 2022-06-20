from .chemdraw_objects import *
import io
import base64
from lxml import etree as ET


def read_cdx(cdx_file) -> ChemDrawDocument:
    """

    :param cdx_file: a file-like object or path (str) to a cdx file
    """
    if isinstance(cdx_file, str):
        with open(cdx_file, mode='rb') as file:
            cdx = file.read()
        cdx = io.BytesIO(cdx)
    elif isinstance(cdx_file, io.BytesIO):
        cdx = cdx_file
    else:
        # assume opened file-handle
        cdx = cdx_file.read()
        cdx = io.BytesIO(cdx)

    document = ChemDrawDocument.from_bytes(cdx)
    return document


def read_b64_cdx(base64_cdx, convert_legacy_doc: bool = False, ignore_unknown_properties: bool = False,
                   ignore_unknown_object: bool = False) -> ChemDrawDocument:

    cdx = io.BytesIO(base64.b64decode(base64_cdx))
    document = ChemDrawDocument.from_bytes(cdx, convert_legacy_doc, ignore_unknown_properties, ignore_unknown_object)

    return document


def read_cdxml(cdxml_file) -> ChemDrawDocument:
    """

    :param cdxml_file: a file object, a path (str) to a cdxml file or a string containing the xml
    """
    if isinstance(cdxml_file, str):
        if cdxml_file.startswith("<?xml"):
            cdxml = cdxml_file.encode('utf-8')
        else:
            with open(cdxml_file, mode='rb') as file:
                cdxml = file.read()
    else:
        # assume opened file-handle
        cdxml = cdxml_file.read()
    cdxml_stream = io.BytesIO(cdxml)
    return ChemDrawDocument(ET.parse(cdxml_stream))


def write_cdxml_file(document: ChemDrawDocument, file):
    with open(file, "w", encoding='UTF-8') as xf:
        xf.write(document.to_cdxml())


def write_cdx_file(document: ChemDrawDocument, file,
                   ignore_unknown_attribute: bool = False, ignore_unknown_element: bool = False):
    with open(file, 'wb') as file:
        file.write(document.to_bytes(ignore_unknown_attribute, ignore_unknown_element))


def to_b64_cdx(document: ChemDrawDocument, ignore_unknown_attribute: bool = False, ignore_unknown_element: bool = False) -> str:
    return base64.b64encode(document.to_bytes(ignore_unknown_attribute, ignore_unknown_element)).decode('ASCII')


def b64_cdx_to_cdxml(b64_cdx: str) -> str:
    document = read_b64_cdx(b64_cdx)
    return document.to_cdxml()
