import io
import yaml
from anytree import NodeMixin
from pathlib import Path
from .chemdraw_types import *
import logging
import logging.config
from lxml import etree as ET

module_path = Path(__file__).parent
log_config_path = module_path / 'logging.yml'
with open(log_config_path, 'r') as stream:
    log_config = yaml.safe_load(stream)
logging.config.dictConfig(log_config)
logger = logging.getLogger('chemdraw_objects')


class ChemDrawObject(NodeMixin):
    """
    Abstract Base class for any ChemDraw object as defined by cdx format specification on:
    https://www.cambridgesoft.com/services/documentation/sdk/chemdraw/cdx/

    Objects have properties (or in cdxml attributes) which themselves can be objects
    """

    module_path = Path(__file__).parent
    cdx_objects_path = module_path / 'cdx_objects.yml'
    with open(cdx_objects_path, 'r') as stream:
        CDX_OBJECTS = yaml.safe_load(stream)
    cdx_properties_path = module_path / 'cdx_properties.yml'
    with open(cdx_properties_path, 'r') as stream:
        CDX_PROPERTIES = yaml.safe_load(stream)
    # Use this sequence to set missing id in xml docs
    OBJECT_ID_SEQUENCE = iter(range(5000,10000))

    def __init__(self, tag_id, type, element_name, id, properties=[],  parent=None, children=None):

        self.tag_id = tag_id
        self.type = type
        self.element_name = element_name
        self.id = id
        self.properties = properties
        self.parent = parent
        if children:
            self.children = children

    @staticmethod
    def from_bytes(cdx:io.BytesIO, tag_id: int, parent:'ChemDrawObject') -> 'ChemDrawObject':
        """
        cdx must be a BytesIO instance at the begining of the ID positon. Eg. the tag_id has been read and the next 4
        bytes are the objects id inside the document.
        :param cdx: BytesIO stream at position right before object ID
        :param tag_id: objects tag identifier
        :param parent: container of this new object
        :return: a new ChemDrawObject
        """
        object_id = int.from_bytes(cdx.read(4), "little")
        props = ChemDrawObject._read_properties(cdx)
        type = ChemDrawObject.CDX_OBJECTS[tag_id]['type']
        element_name = ChemDrawObject.CDX_OBJECTS[tag_id]['element_name']
        obj = ChemDrawObject(tag_id, type, element_name, object_id, properties=props, parent=parent)
        return obj

    @staticmethod
    def from_cdxml(element: ET.Element, parent: 'ChemDrawObject' = None) -> 'ChemDrawObject':

        if "id" in element.attrib:
            object_id = int(element.attrib["id"])
        else:
            object_id = next(ChemDrawObject.OBJECT_ID_SEQUENCE)
        props = ChemDrawObject._read_attributes(element)
        tag_id = next(key for key, value in ChemDrawObject.CDX_OBJECTS.items() if value['element_name'] == element.tag)
        type = ChemDrawObject.CDX_OBJECTS[tag_id]['type']
        obj = ChemDrawObject(tag_id, type, element.tag, object_id, properties=props, parent=parent)
        return obj

    @staticmethod
    def _read_properties(cdx:io.BytesIO) -> list:

        props = []
        tag_id = int.from_bytes(cdx.read(2), "little")

        while tag_id in ChemDrawObject.CDX_PROPERTIES:
            prop_name = ChemDrawObject.CDX_PROPERTIES[tag_id]['name']            
            length = int.from_bytes(cdx.read(2), "little")
            if length == 0xFFFF: #special meaning: property bigger than 65534 bytes
                length = int.from_bytes(cdx.read(4), "little")

            prop_bytes = cdx.read(length)
            chemdraw_type = ChemDrawObject.CDX_PROPERTIES[tag_id]["type"]
            logger.debug('Reading property {} of type {}.'.format(prop_name, chemdraw_type))
            klass = globals()[chemdraw_type]
            if prop_name == 'UTF8Text':
                type_obj = klass.from_bytes(prop_bytes, 'utf8')
            else:
                try:
                    type_obj = klass.from_bytes(prop_bytes)
                except ValueError as err:
                    if prop_name == 'color' and length == 4:
                        # A simple test while had a color property instance of length 4
                        # but it's an uint16 and should only be 2 bytes. first 2 bytes contained correct value
                        type_obj = klass.from_bytes(prop_bytes[:2])
                        length = 2
                        logger.warning("Property color of type UINT16 found with length {} instead of required length 2."
                                       "Fixed by taking only first 2 bytes into account.".format(length))
                    else:
                        raise err

            prop = ChemDrawProperty(tag_id, prop_name, type_obj)
            props.append(prop)
            # read next tag
            tag_id = int.from_bytes(cdx.read(2), "little")
            bit15 = tag_id >> 15 & 1
            # Determine if this is a unknown property. Properties have the most significant bit clear (=0).
            # If property is unknown, log it and read next property until a known one is found.
            # 0 is end of object hence ignore here
            while tag_id != 0 and bit15 == 0 and tag_id not in ChemDrawObject.CDX_PROPERTIES:
                length = int.from_bytes(cdx.read(2), "little")
                prop_bytes = cdx.read(length)
                logger.warning(
                    'Found unknown property {} with length {}. Ignoring this property.'.format(tag_id.to_bytes(2, "little"), length))
                # read next tag
                tag_id = int.from_bytes(cdx.read(2), "little")
                bit15 = tag_id >> 15 & 1

        logger.debug('Successfully finished reading properties.')
        # move back 2 positions, finished reading attributes
        cdx.seek(cdx.tell() - 2)
        return props

    @staticmethod
    def _read_attributes(element: ET.Element) -> list:

        props = []
        has_label_style = False
        has_caption_style = False

        for attribute, value in element.attrib.items():
            if attribute in ["LabelFont", "LabelSize", "LabelFace"]:
                has_label_style = True
                continue
            if attribute in ["CaptionFont", "CaptionSize", "CaptionFace"]:
                has_caption_style = True
                continue
            if attribute == "id":
                continue
            try:
                tag_id = next(key for key, value in ChemDrawObject.CDX_PROPERTIES.items() if value['name'] == attribute)
                chemdraw_type = ChemDrawObject.CDX_PROPERTIES[tag_id]["type"]

                logger.debug('Reading attribute {} of type {}.'.format(attribute, chemdraw_type))
                klass = globals()[chemdraw_type]

                type_obj = klass.from_string(value)

                prop = ChemDrawProperty(tag_id, attribute, type_obj)
                props.append(prop)
            except StopIteration as err:
                logger.warning('Found unknown attribute {}. Ignoring this attribute.'.format(attribute))

        if element.tag == 't':
            type_obj = CDXString.from_element(element)
            txt = ChemDrawProperty(0x0700, "Text", type_obj)
            props.append(txt)
        elif element.tag == "fonttable":
            type_obj = CDXFontTable.from_element(element)
            fonttable = ChemDrawProperty(0x0100, "fonttable", type_obj)
            props.append(fonttable)
        elif element.tag == "colortable":
            type_obj = CDXColorTable.from_element(element)
            colortable = ChemDrawProperty(0x0300, "colortable", type_obj)
            props.append(colortable)

        if has_label_style:

            if "LabelFont" in element.attrib:
                font_id = int(element.attrib["LabelFont"])
            else:
                font_id = -1

            if "LabelFace" in element.attrib:
                font_type = int(element.attrib["LabelFace"])
            else:
                font_type = -1

            if "LabelSize" in element.attrib:
                font_size = int(float(element.attrib["LabelSize"]) * 20)
            else:
                font_size = -1

            # color on labels is ignored according to spec
            type_obj = CDXFontStyle(font_id, font_type, font_size, 0)
            label_style = ChemDrawProperty(0x080A, "LabelStyle", type_obj)
            props.append(label_style)

        if has_caption_style:

            if "CaptionFont" in element.attrib:
                font_id = int(element.attrib["CaptionFont"])
            else:
                font_id = -1

            if "CaptionFace" in element.attrib:
                font_type = int(element.attrib["CaptionFace"])
            else:
                font_type = -1

            if "CaptionSize" in element.attrib:
                font_size = int(float(element.attrib["CaptionSize"]) * 20)
            else:
                font_size = -1

            # color on labels is ignored according to spec
            type_obj = CDXFontStyle(font_id, font_type, font_size, 0)
            caption_style = ChemDrawProperty(0x080B, "CaptionStyle", type_obj)
            props.append(caption_style)

        return props

    def add_as_element(self, parent: ET.Element):
        """
        Build and return the cdxml element for this object
        :return:
        """
        e = ET.SubElement(parent, self.element_name)
        e.attrib['id'] = str(self.id)
        for prop in self.properties:
            prop.add_as_attribute(e)

        return e

    def to_bytes(self) -> bytes:
        """
        Generates and returns the bytes of this object for adding to a cdx binary file
        The end tag \x00\x00 is not written and must be hnadeled by the Document object which is aware of the
        full tree structure.
        :return:
        """
        stream = io.BytesIO()
        stream.write(self.tag_id.to_bytes(2, "little"))
        stream.write(self.id.to_bytes(4, "little"))
        for prop in self.properties:
            stream.write(prop.to_bytes())
        stream.seek(0)
        return  stream.read()

    def __repr__(self):
        return '{}: {}'.format(self.element_name, self.id)


class ChemDrawProperty(object):

    def __init__(self, tag_id: int, name: str, type: CDXType):

        self.tag_id = tag_id
        self.name = name
        self.type = type

    def to_bytes(self) -> bytes:
        """
        Gets the bytes value representing this property in a cdx document

        :return: bytes representing this property
        """
        logger.debug("Writing property {} with value '{}'.".format(self.name, self.get_value()))
        stream = io.BytesIO()
        stream.write(self.tag_id.to_bytes(2, byteorder='little'))
        prop_bytes = self.type.to_bytes()
        length = len(prop_bytes)
        if length <= 65534:
            stream.write(length.to_bytes(2, byteorder='little'))
        else:
            stream.write(b'\xFF\xFF')
            stream.write(length.to_bytes(4, byteorder='little'))
        stream.write(prop_bytes)
        stream.seek(0)
        return stream.read()

    def add_as_attribute(self, element: ET.Element):
        """
        Adds this property as attribute to the passed in Element

        :param element: an ElementTree element instance
        """
        logger.debug("Adding attribute '{}' to element.".format(self.name))
        if self.name == "LabelStyle":
            element.attrib['LabelFont'] = str(self.type.font_id)
            element.attrib['LabelSize'] = str(self.type.font_size_points())
            element.attrib['LabelFace'] = str(self.type.font_type)
        elif self.name == "CaptionStyle":
            element.attrib['CaptionFont'] = str(self.type.font_id)
            element.attrib['CaptionSize'] = str(self.type.font_size_points())
            element.attrib['CaptionFace'] = str(self.type.font_type)
        elif self.name == 'fonttable' or self.name == 'colortable':
            tbl = self.type.to_element()
            element.append(tbl)
        elif self.name == 'Text':
            # adds style tags <s></s> to this t element containing styled text
            self.type.to_element(element)            
            logger.debug("Added {} styles to text object.".format(len(self.type.styles)))
        elif self.name == 'UTF8Text':
            # Do nothing. This is a new property no in official spec and represents the 
            # value of a text objext in UTF-8 inside a cdx file.
            pass
        else:
            element.attrib[self.name] = self.type.to_property_value()

    def get_value(self):
        return self.type.to_property_value()

    def __repr__(self):
        return '{}: {}'.format(self.name, self.get_value())


class ChemDrawDocument(ChemDrawObject):

    HEADER = b'VjCD0100\x04\x03\x02\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    CDXML_HEADER = """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE CDXML SYSTEM "http://www.cambridgesoft.com/xml/cdxml.dtd">
"""
    CDXML_DEFAULT_DOC_ID = 0
    # According to spec if a "tag_ids" most significant bit (15th bit, 0-based index) is clear, then it's a property
    # else it's an object. This leaves 15 bits resulting in a max value for a property tag equal to 32767 due to
    # 2^15-1 (max value bits can represent is 2^n-1)
    MAX_PROPERTY_VALUE = 32767

    def __init__(self, id, properties=[], children=None):

        super().__init__(0x8000, 'Document', 'CDXML', id, properties=properties, children=children)


    @staticmethod
    def from_bytes(cdx:io.BytesIO) -> 'ChemDrawDocument':
        """

        :param cdx: a BytesIO object
        :return:
        """
        header = cdx.read(22)
        if header != ChemDrawDocument.HEADER:
            raise ValueError('File is not a valid cdx file. Invalid header found.')
        document_tag = cdx.read(2)
        if document_tag != b'\x00\x80':
            raise ValueError('File is not a valid cdx file. Document tag not found.')
        object_id = int.from_bytes(cdx.read(4), "little")
        logger.debug('Reading document with id: {}'.format(object_id))
        # Document Properties
        props = ChemDrawObject._read_properties(cdx)

        chemdraw_document = ChemDrawDocument(object_id, props)
        parent_stack = [chemdraw_document]
        tag_id = int.from_bytes(cdx.read(2), "little")

        while tag_id in ChemDrawObject.CDX_OBJECTS:
            try:
                # class_name = ChemDrawObject.CDX_OBJECTS[tag_id]
                # klass = globals()[class_name]
                # obj = klass.from_bytes(cdx, parent_stack[-1])
                obj = ChemDrawObject.from_bytes(cdx, tag_id, parent_stack[-1])
                logger.debug('Created object of type {} with id: {}'.format(obj.type, obj.id))
                # read next tag
                tag_id = int.from_bytes(cdx.read(2), "little")
                if tag_id == 0:
                    # end of current object
                    # read next object tag,
                    tag_id = int.from_bytes(cdx.read(2), "little")
                    # check if also reached end of parent object
                    while tag_id == 0:
                        # while parent object is also at end, remove from stack
                        if len(parent_stack) > 0:
                            parent_stack.pop()
                            tag_id = int.from_bytes(cdx.read(2), "little")
                        else:
                            logger.info('Finished reading document.')
                            return chemdraw_document
                else:
                    # no object end found, hence we move deeper inside the object tree
                    parent_stack.append(obj)
            except KeyError as err:
                logger.error('Missing Object Implementation: {}. Ignoring object.'.format(err))

    @staticmethod
    def from_cdxml(root: ET.Element) -> 'ChemDrawDocument':

        if root.tag != "CDXML":
            raise ValueError('File is not a valid cdxml file. Invalid root tag {} found.'.format(root.tag))
        # Document Properties
        props = ChemDrawObject._read_attributes(root)

        chemdraw_document = ChemDrawDocument(ChemDrawDocument.CDXML_DEFAULT_DOC_ID, props)
        parent_stack = [chemdraw_document]

        for element in root.iterdescendants():
            if element.tag in ['s', 'font', 'color']:
                # s elements are always in t elements and hence already handeled by parent t element
                # this is needed as there is a missmatch between cdx and cdxml
                # same for fonts and colors in font/colortable
                continue
            try:
                parent = parent_stack[-1]
                obj = ChemDrawObject.from_cdxml(element, parent)
                logger.debug('Created object of type {} with id: {}'.format(obj.type, obj.id))
                parent_element = element.getparent()
                idx = parent_element.index(element)
                num_children = len(parent_element.getchildren())
                if idx == num_children - 1:
                    # last child of this element
                    parent_stack.pop()
                else:
                    parent_stack.append(obj)

            except KeyError as err:
                logger.error('Missing Object Implementation: {}. Ignoring object.'.format(err))

        return chemdraw_document

    def to_bytes(self) -> bytes:

        stream = io.BytesIO()
        stream.write(ChemDrawDocument.HEADER)
        stream.write(self.tag_id.to_bytes(2, byteorder='little'))  # object tag
        stream.write(self.id.to_bytes(4, byteorder='little'))  # object id

        for prop in self.properties:
            stream.write(prop.to_bytes())

        for child in self.children:
            ChemDrawDocument._traverse_cdx(child, stream)

        stream.write(b'\x00\x00\x00\x00') # end of document and end of file
        stream.seek(0)
        return stream.read()

    def to_cdxml(self) ->str:

        cdxml = ET.Element('CDXML')
        for prop in self.properties:
            prop.add_as_attribute(cdxml)

        for child in self.children:
            ChemDrawDocument._traverse_xml(child, cdxml)

        xml = ET.tostring(cdxml, encoding='unicode', method='xml')
        return ChemDrawDocument.CDXML_HEADER + xml

    @staticmethod
    def _traverse_cdx(node: ChemDrawObject, stream:io.BytesIO):
        stream.write(node.to_bytes())
        for child in node.children:
            ChemDrawDocument._traverse_cdx(child, stream)
        stream.write(b'\x00\x00')

    @staticmethod
    def _traverse_xml(node: ChemDrawObject, parent: ET.Element):
        elm = node.add_as_element(parent)
        for child in node.children:
            ChemDrawDocument._traverse_xml(child, elm)