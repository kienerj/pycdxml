from .chemdraw_types import *
import io
import yaml
from pathlib import Path
from lxml import etree as ET
import logging

from ..utils.cdxml_io import etree_to_cdxml

logger = logging.getLogger('pycdxml.chemdraw_objects')


class ConversionException(Exception):
    pass


class UnknownPropertyException(ConversionException):
    pass


class UnknownObjectException(ConversionException):
    pass


class LegacyDocumentException(ConversionException):
    pass


class ChemDrawDocument(object):
    HEADER = b'VjCD0100\x04\x03\x02\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

    CDXML_DEFAULT_DOC_ID = 0
    # According to spec if a "tag_ids" most significant bit (15th bit, 0-based index) is clear, then it's a property
    # else it's an object. This leaves 15 bits resulting in a max value for a property tag equal to 32767 due to
    # 2^15-1 (max value bits can represent is 2^n-1)
    MAX_PROPERTY_VALUE = 32767

    module_path = Path(__file__).parent

    cdx_objects_path = module_path / 'cdx_objects.yml'
    with open(cdx_objects_path, 'r') as stream:
        CDX_OBJECTS = yaml.safe_load(stream)
    ELEMENT_NAME_TO_OBJECT_TAG = {value["element_name"]: key for key, value in CDX_OBJECTS.items()}

    cdx_properties_path = module_path / 'cdx_properties.yml'
    with open(cdx_properties_path, 'r') as stream:
        CDX_PROPERTIES = yaml.safe_load(stream)
    PROPERTY_NAME_TO_TAG = {value["name"]: key for key, value in CDX_PROPERTIES.items()}

    def __init__(self, cdxml: ET.ElementTree, max_object_id=5000, document_id=None):
        self.cdxml = cdxml
        # Use this sequence to set missing id in xml docs
        self.object_id_sequence = iter(range(max_object_id, 100000))
        # To use for determining charset of a font when writing CDXString
        self.fonttable = CDXFontTable.from_element(cdxml.getroot().find("fonttable"))
        # manage document id on this level as this is not exported as attribute in cdxml
        if document_id is None:
            self.document_id = next(self.object_id_sequence)
        else:
            self.document_id = document_id

    @staticmethod
    def from_bytes(cdx: io.BytesIO, convert_legacy_doc: bool = False, ignore_unknown_properties: bool = False,
                   ignore_unknown_object: bool = False) -> 'ChemDrawDocument':
        """
        :param cdx: a BytesIO object
        :param convert_legacy_doc: if conversion of a legacy document should be attempted or an exception thrown
        :param ignore_unknown_properties: if unknown properties should be ignored or an exception raised
        :param ignore_unknown_object: if unknown objects should be ignored or an exception raised
        :return: ChemDrawDocument
        """
        r = CDXReader(cdx, convert_legacy_doc, ignore_unknown_properties, ignore_unknown_object)
        return r.read()

    @staticmethod
    def from_cdxml(cdxml: str) -> 'ChemDrawDocument':
        cdxml_bytes = io.BytesIO(cdxml.encode('utf-8'))
        et = ET.parse(cdxml_bytes)
        # Get maximum id
        elm_list = et.findall(".//*[@id]")
        max_id = max(map(int, [x.attrib["id"] for x in elm_list]))
        return ChemDrawDocument(et, max_id)

    def to_bytes(self, ignore_unknown_attribute: bool = False, ignore_unknown_element: bool = False) -> bytes:
        """
        Generates a cdx file as bytes in memory

        :param ignore_unknown_attribute: if unknown attributes should be ignored or exception raised
        :param ignore_unknown_element: if unknown elements should be ignored or exception raised
        """

        logger.info("Starting to convert document to cdx.")
        stream = io.BytesIO()
        # Write document to bytes. needs special handling due to font and color tables.
        stream.write(ChemDrawDocument.HEADER)
        root = self.cdxml.getroot()
        self._element_to_stream(root, stream, ignore_unknown_attribute, ignore_unknown_element)
        colortable = root.find("colortable")
        fonttable = root.find("fonttable")
        if colortable is not None:
            type_obj = CDXColorTable.from_element(colortable)
            tag_id = ChemDrawDocument.PROPERTY_NAME_TO_TAG['colortable']
            stream.write(tag_id.to_bytes(2, byteorder='little'))
            self._type_to_stream(type_obj, stream)
        if fonttable is not None:
            type_obj = CDXFontTable.from_element(fonttable)
            tag_id = ChemDrawDocument.PROPERTY_NAME_TO_TAG['fonttable']
            stream.write(tag_id.to_bytes(2, byteorder='little'))
            self._type_to_stream(type_obj, stream)

        for child in root:
            self._traverse_tree(child, stream, ignore_unknown_attribute, ignore_unknown_element)

        # end of document and end of file
        stream.write(b'\x00\x00\x00\x00')
        logger.info("Finished converting document to cdx.")
        return stream.getvalue()

    def to_cdxml(self) -> str:

        return etree_to_cdxml(self.cdxml)

    def _traverse_tree(self, node: ET.Element, stream: io.BytesIO,
                       ignore_unknown_attribute: bool, ignore_unknown_element: bool):

        # s elements are always in t elements and hence already handled by parent t element
        # this is needed as there is a mismatch between cdx and cdxml
        # same for fonts and colors and font and colortable
        if node.tag not in ['s', 'font', 'color', 'fonttable', 'colortable']:
            # See Issue 13: Stereochemistry symbols are shown twice after cdxml to cdx conversion
            # A cdxml that contains stereochemistry symbol in an ojecttag will lead to duplicate display of the tag
            # in ChemDraw when included in the cdx
            # hence we simply do not write such a objecttag to cdx to fix the issue
            # Same for residueID in peptides - unclear why duplication is shown as there is no obvious difference
            # to cdx generated form chemdraw in terms of settings
            if node.tag == "objecttag" and (node.attrib["Name"] == "stereo" or node.attrib["Name"] == "enhancedstereo"
                                            or node.attrib["Name"] == "residueID"):
                return
            self._element_to_stream(node, stream, ignore_unknown_attribute, ignore_unknown_element)
            for child in node:
                if child.tag != "represent":
                    self._traverse_tree(child, stream, ignore_unknown_attribute, ignore_unknown_element)
            stream.write(b'\x00\x00')

    def _element_to_stream(self, element: ET.Element, stream: io.BytesIO,
                           ignore_unknown_attribute: bool, ignore_unknown_element: bool):

        try:
            tag_id = ChemDrawDocument.ELEMENT_NAME_TO_OBJECT_TAG[element.tag]
            logger.debug(f"Writing object {element.tag}.")
            stream.write(tag_id.to_bytes(2, "little"))
            if 'id' in element.attrib:
                stream.write(int(element.attrib['id']).to_bytes(4, "little"))
            elif element.tag == "CDXML":
                # Write document id to cdx
                stream.write(self.document_id.to_bytes(4, "little"))
            else:
                # Object Read from cdxml with no ID assigned, give it a default one
                stream.write(next(self.object_id_sequence).to_bytes(4, "little"))

            has_label_style = False
            has_caption_style = False
            for attrib, value in element.attrib.items():
                if attrib in ["LabelFont", "LabelSize", "LabelFace"]:
                    has_label_style = True
                elif attrib in ["CaptionFont", "CaptionSize", "CaptionFace"]:
                    has_caption_style = True
                elif attrib == "id":
                    pass
                elif attrib == "Value":
                    # "Value" is a special attribute. The type of the attribute depends on the attribute "TagType".
                    try:
                        tag_type = CDXTagType[element.attrib["TagType"]]
                    except KeyError:
                        logger.warning("Found attribute of type 'Value' without a 'TagType'. Using 'Unknown'.")
                        tag_type = CDXTagType.Unknown

                    tag_id = ChemDrawDocument.PROPERTY_NAME_TO_TAG["Value"]
                    klass = globals()["CDXValue"]
                    type_obj = klass.from_string(value, tag_type)
                    logger.debug(f"Writing attribute {attrib} with value '{value}'.")
                    stream.write(tag_id.to_bytes(2, byteorder='little'))
                    ChemDrawDocument._type_to_stream(type_obj, stream)
                elif element.tag == "gepband" and (attrib == "Height" or attrib == "Width"):
                    # Height and Width in gepband behave like INT32 and not a CDXCoordinate
                    # They have the same value in cdx and cdxml
                    tag_id = ChemDrawDocument.PROPERTY_NAME_TO_TAG[attrib]
                    klass = globals()["INT32"]
                    type_obj = klass.from_string(value)
                    logger.debug(f"Writing attribute {attrib} with value '{value}'.")
                    stream.write(tag_id.to_bytes(2, byteorder='little'))
                    ChemDrawDocument._type_to_stream(type_obj, stream)
                else:
                    ChemDrawDocument._attribute_to_stream(attrib, value, stream, ignore_unknown_attribute)

            # check if element has child with tag "represent"
            # in cdx this is a property of the "represent" parent element
            represent = element.find("represent")
            if represent is not None:
                type_obj = CDXRepresents.from_element(represent)
                tag_id = ChemDrawDocument.ELEMENT_NAME_TO_OBJECT_TAG["represent"]
                stream.write(tag_id.to_bytes(2, byteorder='little'))
                self._type_to_stream(type_obj, stream)

            if element.tag == 't':
                type_obj = CDXString.from_element(element, self.fonttable)
                tag_id = ChemDrawDocument.PROPERTY_NAME_TO_TAG['Text']
                stream.write(tag_id.to_bytes(2, byteorder='little'))
                ChemDrawDocument._type_to_stream(type_obj, stream)

            if has_label_style:
                if "LabelFont" in element.attrib:
                    font_id = int(element.attrib["LabelFont"])
                else:
                    logger.info("Setting default label font id to 1. This might cause an issue if no font with id 1 "
                                "exists.")
                    font_id = 1
                if "LabelFace" in element.attrib:
                    font_type = int(element.attrib["LabelFace"])
                else:
                    font_type = 0  # plain
                if "LabelSize" in element.attrib:
                    font_size = int(float(element.attrib["LabelSize"]) * 20)
                else:
                    # assume 12 points as default font size. Factor 20 in conversion to cdx units.
                    font_size = 12 * 20

                # color on labels is ignored according to spec
                type_obj = CDXFontStyle(font_id, font_type, font_size, 0)
                tag_id = ChemDrawDocument.PROPERTY_NAME_TO_TAG['LabelStyle']
                stream.write(tag_id.to_bytes(2, byteorder='little'))
                ChemDrawDocument._type_to_stream(type_obj, stream)

            if has_caption_style:
                if "CaptionFont" in element.attrib:
                    font_id = int(element.attrib["CaptionFont"])
                else:
                    logger.info(
                        "Setting default caption font id to 1. This might cause an issue if no font with id 1 exists.")
                    font_id = 1
                if "CaptionFace" in element.attrib:
                    font_type = int(element.attrib["CaptionFace"])
                else:
                    font_type = 0  # plain
                if "CaptionSize" in element.attrib:
                    font_size = int(float(element.attrib["CaptionSize"]) * 20)
                else:
                    # assume 12 points as default font size. Factor 20 in conversion to cdx units.
                    font_size = 12 * 20

                # color on labels is ignored according to spec
                type_obj = CDXFontStyle(font_id, font_type, font_size, 0)
                tag_id = ChemDrawDocument.PROPERTY_NAME_TO_TAG['CaptionStyle']
                stream.write(tag_id.to_bytes(2, byteorder='little'))
                ChemDrawDocument._type_to_stream(type_obj, stream)

        except KeyError as err:
            logger.error(f"Missing implementation for element: {element.tag}. {err}.")
            if not ignore_unknown_element:
                raise UnknownPropertyException(f"Can't convert unknown element {element.tag} to cdx.") from err

    @staticmethod
    def _attribute_to_stream(attrib: str, value: str, stream: io.BytesIO, ignore_unknown_attribute: bool):
        try:
            tag_id = ChemDrawDocument.PROPERTY_NAME_TO_TAG[attrib]
            chemdraw_type = ChemDrawDocument.CDX_PROPERTIES[tag_id]['type']
            klass = globals()[chemdraw_type]
            type_obj = klass.from_string(value)
            logger.debug(f"Writing attribute {attrib} with value '{value}'.")
            stream.write(tag_id.to_bytes(2, byteorder='little'))
            ChemDrawDocument._type_to_stream(type_obj, stream)
        except KeyError:
            logger.error(f"Found unknown attribute '{attrib} with value '{value}'. Ignoring attribute.")
            if not ignore_unknown_attribute:
                raise UnknownPropertyException(f"Can't convert unknown attribute '{attrib}' to cdx.")
        except ValueError as err:
            logger.error(f"Found attribute {attrib} with invalid value '{value}'. Omitting this property in output")

    @staticmethod
    def _type_to_stream(type_obj: CDXType, stream: io.BytesIO):
        prop_bytes = type_obj.to_bytes()
        length = len(prop_bytes)
        if length <= 65534:
            stream.write(length.to_bytes(2, byteorder='little'))
        else:
            stream.write(b'\xFF\xFF')
            stream.write(length.to_bytes(4, byteorder='little'))
        stream.write(prop_bytes)


class CDXReader(object):

    def __init__(self, cdx: io.BytesIO, convert_legacy_doc: bool = False, ignore_unknown_properties: bool = False,
                 ignore_unknown_object: bool = False):

        """
        Constructor for CDXReader Helper class.

         :param cdx: a BytesIO object
         :param convert_legacy_doc: if conversion of a legacy document should be attempted or an exception thrown
         :param ignore_unknown_properties: if unknown properties should be ignored or an exception raised
         :param ignore_unknown_object: if unknown objects should be ignored or an exception raised
        """

        self.cdx = cdx
        self.convert_legacy_doc = convert_legacy_doc
        self.ignore_unknown_object = ignore_unknown_object
        self.ignore_unknown_properties = ignore_unknown_properties
        self.colortable = None
        self.fonttable = None
        self.max_id = 0

    def read(self) -> ChemDrawDocument:
        """
         :return: ChemDrawDocument
        """
        header = self.cdx.read(22)
        if header != ChemDrawDocument.HEADER:
            raise ValueError('File is not a valid cdx file. Invalid header found.')
        document_tag = self.cdx.read(2)
        legacy_doc = False
        if document_tag != b'\x00\x80':
            # legacy files in registration start like below
            # VjCD0100\x04\x03\x02\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03
            # instead of
            # VjCD0100\x04\x03\x02\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00\x00\x03
            # No document tag and one additional byte. read and ignore said additional byte
            if self.convert_legacy_doc:
                logger.warning('The file seems to be a legacy cdx file. There might be issues in the generated output.')
                self.cdx.read(1)
                legacy_doc = True
            else:
                raise LegacyDocumentException("The file has a legacy document header. Can't ensure correct conversion.")

        document_id = int.from_bytes(self.cdx.read(4), "little")
        self.max_id = document_id
        logger.debug(f"Reading document with id: {document_id}")
        root = ET.Element("CDXML")
        cdxml = ET.ElementTree(root)
        if legacy_doc:
            # legacy document has additional 23 bytes with unknown meaning, ignore
            # then first property usually is creation program
            self.cdx.read(23)
        # Document Attributes
        self._read_attributes(root)

        parent_stack = [root]
        tag_id = int.from_bytes(self.cdx.read(2), "little")

        while tag_id in ChemDrawDocument.CDX_OBJECTS:
            try:
                el = self._element_from_bytes(tag_id, parent_stack[-1])
                logger.debug(f'Created element of type {el.tag} with id: {el.attrib["id"]}')
                # read next tag
                tag_id = int.from_bytes(self.cdx.read(2), "little")
                if tag_id == 0:
                    # end of current object
                    # read next object tag,
                    tag_id = int.from_bytes(self.cdx.read(2), "little")
                    # check if also reached end of parent object
                    while tag_id == 0:
                        # while parent object is also at end, remove from stack
                        if len(parent_stack) > 0:
                            parent_stack.pop()
                            tag_id = int.from_bytes(self.cdx.read(2), "little")
                        else:
                            logger.info('Finished reading document.')
                            return ChemDrawDocument(cdxml, max_object_id=self.max_id, document_id=document_id)
                else:
                    # no object end found, hence we move deeper inside the object tree
                    parent_stack.append(el)
            except KeyError as err:
                if self.ignore_unknown_object:
                    logger.error(f"Missing Object Implementation: {err}. Ignoring object.")
                else:
                    raise UnknownObjectException(f"Unknown object with tag_id {tag_id} found.") from err

    def _element_from_bytes(self, tag_id: int, parent: ET.Element):
        """
        :param cdx: BytesIO stream at position right before object ID
        :param tag_id: objects tag identifier
        :return: a new ChemDrawObject
        """
        object_id = int.from_bytes(self.cdx.read(4), "little")
        if object_id > self.max_id:
            self.max_id = object_id
        element_name = ChemDrawDocument.CDX_OBJECTS[tag_id]['element_name']
        el = ET.SubElement(parent, element_name)
        el.attrib["id"] = str(object_id)
        self._read_attributes(el)
        return el

    def _read_attributes(self, element: ET.Element):

        # control structures for type "Value" which depends on "TagType".
        # the type of  "Value" is defined in "TagType"
        tag_type = CDXTagType.Unknown
        value_read = False

        while True:
            tag_id = int.from_bytes(self.cdx.read(2), "little")
            # Properties have the most significant bit clear (=0).
            # If it is not 0, then it is not a property but the next object
            bit15 = tag_id >> 15 & 1
            # end of object or start of next object
            if tag_id == 0 or bit15 != 0:
                break

            if tag_id not in ChemDrawDocument.CDX_PROPERTIES:
                if self.ignore_unknown_properties:
                    # If property is unknown, log it and read next property until a known one is found.
                    # tag_id of 0 is end of object
                    while tag_id != 0 and bit15 == 0 and tag_id not in ChemDrawDocument.CDX_PROPERTIES:
                        length = int.from_bytes(self.cdx.read(2), "little")
                        self.cdx.read(length)
                        logger.warning(f'Found unknown property {tag_id.to_bytes(2, "little")} with length {length}. '
                                       f'Ignoring this property.')
                        # read next tag
                        tag_id = int.from_bytes(self.cdx.read(2), "little")
                        bit15 = tag_id >> 15 & 1

                    # end of object
                    if tag_id == 0 or bit15 != 0:
                        break
                else:
                    raise UnknownPropertyException(f"Unknown property with tag_id {tag_id} found.")

            prop_name = ChemDrawDocument.CDX_PROPERTIES[tag_id]["name"]
            length = int.from_bytes(self.cdx.read(2), "little")
            if length == 0xFFFF:  # special meaning: property bigger than 65534 bytes
                length = int.from_bytes(self.cdx.read(4), "little")
            prop_bytes = self.cdx.read(length)
            chemdraw_type = ChemDrawDocument.CDX_PROPERTIES[tag_id]["type"]
            logger.debug(f"Reading property {prop_name} of type {chemdraw_type}.")
            klass = globals()[chemdraw_type]
            if prop_name == "UTF8Text":
                type_obj = klass.from_bytes(prop_bytes, charset="utf8")
            elif chemdraw_type == "CDXString":
                type_obj = klass.from_bytes(prop_bytes, fonttable=self.fonttable)
            elif prop_name == "Value":
                # if order in cdx is wrong as "Value" appears before "tag_type", the value is set to unknown.
                type_obj = klass.from_bytes(prop_bytes, tag_type)
                value_read = True
            elif element.tag == "gepband" and (prop_name == "Height" or prop_name == "Width"):
                # Height and Width on gepband are INT32 while else they are CDXCoordinate
                klass = globals()["INT32"]
                type_obj = klass.from_bytes(prop_bytes)
            else:
                try:
                    type_obj = klass.from_bytes(prop_bytes)
                    if prop_name == "TagType":
                        tag_type = type_obj
                        # if value has been read before tag_type, fix it as it was set to unknown
                        if value_read and tag_type != CDXTagType.Unknown:
                            old_val = element.attrib["Value"]
                            val = CDXValue.from_string(old_val, tag_type)
                            element.attrib["Value"] = val.to_property_value()

                except ValueError as err:
                    if prop_name == 'color' and length == 4:
                        # A simple test file had a color property instance of length 4
                        # but it's an uint16 and should only be 2 bytes. first 2 bytes contained correct value
                        type_obj = klass.from_bytes(prop_bytes[:2])
                        length = 2
                        logger.warning(f"Property color of type UINT16 found with length {length} instead of required "
                                       "length 2. Fixed by taking only first 2 bytes into account.")
                    else:
                        raise err

            if prop_name == 'LabelStyle':
                element.attrib['LabelFont'] = str(type_obj.font_id)
                element.attrib['LabelSize'] = str(type_obj.font_size_points())
                element.attrib['LabelFace'] = str(type_obj.font_type)
            elif prop_name == 'CaptionStyle':
                element.attrib['CaptionFont'] = str(type_obj.font_id)
                element.attrib['CaptionSize'] = str(type_obj.font_size_points())
                element.attrib['CaptionFace'] = str(type_obj.font_type)
            elif prop_name == 'fonttable':
                self.fonttable = type_obj
                tbl = type_obj.to_element()
                element.append(tbl)
            elif prop_name == 'colortable':
                self.colortable = type_obj
                tbl = type_obj.to_element()
                element.append(tbl)
            elif prop_name == 'represent':
                rpr = type_obj.to_element()
                element.append(rpr)
            elif prop_name == 'Text':
                # adds style tags <s></s> to this t element containing styled text
                type_obj.to_element(element)
            else:
                element.attrib[prop_name] = type_obj.to_property_value()

        logger.debug('Successfully finished reading attributes.')
        # move back 2 positions, finished reading attributes
        self.cdx.seek(self.cdx.tell() - 2)
