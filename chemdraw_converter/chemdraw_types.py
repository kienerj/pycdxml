import io
import yaml
import xml.etree.ElementTree as ET
from pathlib import Path
import logging
import logging.config

module_path = Path(__file__).parent
log_config_path = module_path / 'logging.yml'
with open(log_config_path, 'r') as stream:
    log_config = yaml.safe_load(stream)
logging.config.dictConfig(log_config)
logger = logging.getLogger('chemdraw_types')


class CDXType(object):

    @staticmethod
    def from_bytes(property_bytes:bytes) -> 'CDXType':
        raise NotImplementedError("Should have implemented this")

    def to_bytes(self) -> bytes:
        raise NotImplementedError("Should have implemented this")

    def to_element(self) -> ET.Element:
        raise NotImplementedError("Should have implemented this")

    def to_property_value(self) -> str:
        raise NotImplementedError("Should have implemented this")


class CDXString(CDXType):
    # TODO: implement different charsets from fonttable
    BYTES_PER_STYLE = 10

    def __init__(self, value: str, style_starts=[], styles=[]):
        self.value = value
        self.style_starts = style_starts
        self.styles = styles

    @staticmethod
    def from_bytes(property_bytes:bytes) -> 'CDXString':

        stream = io.BytesIO(property_bytes)
        style_runs = int.from_bytes(stream.read(2), "little")
        font_styles = []
        style_starts = []
        for idx in range(style_runs):
            style_start = int.from_bytes(stream.read(2), "little")
            style_starts.append(style_start)
            font_style = CDXFontStyle.from_bytes(stream.read(8))
            font_styles.append(font_style)
        text_length = len(property_bytes) - (CDXString.BYTES_PER_STYLE * style_runs) - 2
        value = stream.read(text_length).decode('iso-8859-1')
        return CDXString(value, font_styles)

    def to_bytes(self) -> bytes:
        stream = io.BytesIO()
        # number of styles (s elements
        stream.write(len(self.styles).to_bytes(2, byteorder='little'))
        for idx, style in enumerate(self.styles):
            stream.write(self.style_starts[idx].to_bytes(2, byteorder='little'))
            stream.write(style.to_bytes())
        stream.write(self.value.encode('iso-8859-1'))
        logger.debug('Wrote CDXString with value {}.'.format(self.value))
        stream.seek(0)
        return stream.read()

    def to_element(self) -> ET.Element:
        """
        Generates a 't' element contains all the styles as 's' elements.
        This method must only be called from a text object and never for getting a properties value. To get a properties
        value use the 'value' attribute directly.
        :return:
        """
        if len(self.style_starts) == 0:
            raise TypeError('Call of to_element on CDXString is invalid if no styles are present. If CDXString is part of a property there are no styles.')

        t = ET.Element('t')
        for idx, style in enumerate(self.styles):
            s = style.to_element()
            s.text = self.value[self.style_starts[idx]:self.style_starts[idx+1]]
            t.append(s)
        return t

    def to_property_value(self) -> str:
        return self.value


class CDXFontStyle(CDXType):

    def __init__(self, font_id, font_type, font_size, font_color):

        self.font_id = font_id
        self.font_type = font_type
        self.font_size = font_size
        self.font_color = font_color

    @staticmethod
    def from_bytes(property_bytes:bytes) -> 'CDXFontStyle':

        stream = io.BytesIO(property_bytes)
        font_id = int.from_bytes(stream.read(2), "little")
        font_type = int.from_bytes(stream.read(2), "little")
        font_size = int.from_bytes(stream.read(2), "little")
        font_color = int.from_bytes(stream.read(2), "little")
        return CDXFontStyle(font_id, font_type, font_size, font_color)

    def font_size_points(self) -> float:
        return self.font_size / 20

    def to_bytes(self) -> bytes:

        return self.font_id.to_bytes(2, byteorder='little') + self.font_type.to_bytes(2, byteorder='little') \
        + self.font_size.to_bytes(2, byteorder='little') + self.font_color.to_bytes(2, byteorder='little')

    def to_element(self) -> ET.Element:
        s = ET.Element('s')
        s.attrib['font'] = self.font_id
        s.attrib['size'] = self.font_size_points()
        s.attrib['face'] = self.font_type
        s.attrib['color'] = self.font_color

        return s

    def to_property_value(self) -> str:
        return 'font={} size={} face={} color={}'.format(self.font_id, self.font_size_points(), self.font_type, self.font_color)


class Font(object):

    module_path = Path(__file__).parent
    charsets_path = module_path / 'charsets.yml'
    with open(charsets_path, 'r') as stream:
        CHARSETS = yaml.safe_load(stream)

    def __init__(self, id:int, charset: int, font_name: str):

        self.id = id
        self.charset = charset
        self.font_name = font_name


class CDXFontTable(CDXType):

    def __init__(self, platfrom:int, fonts=[]):

        self.platform = platfrom
        self.fonts = fonts

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXFontTable':
        stream = io.BytesIO(property_bytes)
        platform = int.from_bytes(stream.read(2), "little", signed=False)
        num_fonts = int.from_bytes(stream.read(2), "little", signed=False)
        fonts = []
        for i in range(num_fonts):
            font_id = int.from_bytes(stream.read(2), "little", signed=False)
            charset = int.from_bytes(stream.read(2), "little", signed=False)
            font_name_length = int.from_bytes(stream.read(2), "little", signed=False)
            font_name = stream.read(font_name_length).decode('ascii')
            fonts.append(Font(font_id, charset, font_name))
        return CDXFontTable(platform, fonts)

    def to_bytes(self) -> bytes:

        stream = io.BytesIO()
        stream.write(self.platform.to_bytes(2, byteorder='little'))
        # number of fonts
        stream.write(len(self.fonts).to_bytes(2, byteorder='little'))
        for font in self.fonts:
            stream.write(font.id.to_bytes(2, byteorder='little'))
            stream.write(font.charset.to_bytes(2, byteorder='little'))
            stream.write(len(font.font_name).to_bytes(2, byteorder='little'))
            stream.write(font.font_name.encode('ascii'))
        stream.seek(0)
        return stream.read()

    def to_element(self) -> ET.Element:
        ft = ET.Element('fonttable')
        for font in self.fonts:
            f = ET.SubElement(ft,'font')
            f.attrib['id'] = str(font.id)
            f.attrib['charset'] = Font.CHARSETS[font.charset]
            f.attrib['name'] = font.font_name
        return ft

    def to_property_value(self) -> str:
        return ET.tostring(self.to_element(), encoding='unicode', method='xml')


class Color(object):

    def __init__(self,r:int, g:int, b:int):

        self.r = r
        self.g = g
        self.b = b


class CDXColorTable(CDXType):

    COLOR_MAX_VALUE = 65535

    def __init__(self, colors=[]):

        self.colors = colors

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXColorTable':
        stream = io.BytesIO(property_bytes)
        num_colors = int.from_bytes(stream.read(2), "little", signed=False)
        colors = []
        for i in range(num_colors):
            r = int.from_bytes(stream.read(2), "little", signed=False)
            g = int.from_bytes(stream.read(2), "little", signed=False)
            b = int.from_bytes(stream.read(2), "little", signed=False)
            colors.append(Color(r, g, b))
        return CDXColorTable(colors)

    def to_bytes(self) -> bytes:

        stream = io.BytesIO()
        # number of colors
        stream.write(len(self.colors).to_bytes(2, byteorder='little'))
        for color in self.colors:
            stream.write(color.r.to_bytes(2, byteorder='little'))
            stream.write(color.g.to_bytes(2, byteorder='little'))
            stream.write(color.b.to_bytes(2, byteorder='little'))
        stream.seek(0)
        return stream.read()

    def to_element(self) -> ET.Element:
        ct = ET.Element('colortable')
        for color in self.colors:
            c = ET.SubElement(ct,'color')
            # scale colors as represented as float from 0 to 1 in cdxml
            c.attrib['r'] = str(color.r / CDXColorTable.COLOR_MAX_VALUE)
            c.attrib['g'] = str(color.g / CDXColorTable.COLOR_MAX_VALUE)
            c.attrib['b'] = str(color.b / CDXColorTable.COLOR_MAX_VALUE)
        return ct

    def to_property_value(self) -> str:
        return ET.tostring(self.to_element(), encoding='unicode', method='xml')


class CDXCoordinate(CDXType):
    """
    In CDX files, a CDXCoordinate is an INT32. 1 unit represents 1/65536 points, or 1/4718592 inches, or 1/1857710 cm.
    This permits a drawing space of about 23.1 meters. In contexts where appropriate, 1 unit represents 10-15 meters,
    permitting a coordinate space of approx. ±2.1x10-6 meters (±21,474 Angstroms).

    In CDXML files, a CDXCoordinate is scaled differently, so that 1 unit represents 1 point. CDXCoordinates in CDXML
    files may be represented as decimal values.

    In 2D coordinate spaces, the origin is at the top left corner, and the coordinates increase down and to the right.

    Example: 1 inch (72 points):
    CDX:	00 00 48 00
    CDXML:	"72"
    """
    CDXML_CONVERSION_FACTOR = 65536

    def __init__(self, value: int):
        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXCoordinate':

        value = int.from_bytes(property_bytes, "little", signed=True)
        return CDXCoordinate(value)

    def to_bytes(self) -> bytes:
        return self.value.to_bytes(4, byteorder='little', signed=True)

    def to_property_value(self) -> str:

        return str(round(self.value / CDXCoordinate.CDXML_CONVERSION_FACTOR, 2))


class CDXPoint2D(CDXType):
    """
    In CDX files, a CDXPoin t2D is an x- and a y-CDXCoordinate stored as a pair of INT32s, y coordinate followed by x
    coordinate.

    In CDXML files, a CDXPoint2D is a stored as a pair of numeric values, x coordinate followed by y coordinate.
    Note that this ordering is different than in CDX files!

    Example: 1 inch (72 points) to the right, and 2 inches down:
    CDX:	00 00 90 00 00 00 48 00
    CDXML:	"72 144"
    """

    def __init__(self, x: CDXCoordinate, y: CDXCoordinate):

        self.x = x
        self.y = y

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXPoint2D':

        y = CDXCoordinate.from_bytes(property_bytes[0:4])
        x = CDXCoordinate.from_bytes(property_bytes[4:8])

        return CDXPoint2D(x, y)

    def to_bytes(self) -> bytes:

        return self.y.to_bytes() + self.x.to_bytes()

    def to_property_value(self) -> str:

        return self.x.to_property_value() + " " + self.y.to_property_value()


class CDXPoint3D(CDXType):
    """
    In CDX files, a CDXPoint3D is an x- and a y-CDXCoordinate stored as a pair of INT32s, z coordinate followed by y
    coordinate followed by x coordinate.

    In CDXML files, a CDXPoint2D is a stored as a pair of numeric values, x coordinate followed by y coordinate followed
    by z coordinate. Note that this ordering is different than in CDX files!

    Example: 1 inch (72 points) to the right, 2 inches down, and 3 inches deep:
    CDX:	00 00 d8 00 00 00 90 00 00 00 48 00
    CDXML:	"72 144 216"
    """

    def __init__(self, x: CDXCoordinate, y: CDXCoordinate, z:CDXCoordinate):

        self.x = x
        self.y = y
        self.z = z

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXPoint3D':

        z = CDXCoordinate.from_bytes(property_bytes[0:4])
        y = CDXCoordinate.from_bytes(property_bytes[4:8])
        x = CDXCoordinate.from_bytes(property_bytes[8:12])

        return CDXPoint3D(x, y, z)

    def to_bytes(self) -> bytes:

        return self.z.to_bytes() + self.y.to_bytes() + self.x.to_bytes()

    def to_property_value(self) -> str:

        return self.x.to_property_value() + " " + self.y.to_property_value() + " " + self.z.to_property_value()


class CDXRectangle(CDXType):
    """
    In CDX files, rectangles are stored as four CDXCoordinate values, representing, in order: top, left, bottom, and
    right edges of the rectangle.

    In CDXML files, rectangles are stored as four CDXCoordinate values, representing, in order: left, top, right, and
    bottom edges of the rectangle. Note that this ordering is different than in CDX files!

    Example: top: 1 inch, left: 2 inches, bottom: 3 inches, right: 4 inches:
    CDX:	00 00 48 00 00 00 90 00 00 00 D8 00 00 00 20 01
    CDXML:	"144 72 288 216"
    """

    def __init__(self, top: CDXCoordinate, left: CDXCoordinate, bottom: CDXCoordinate, right: CDXCoordinate):

        self.top = top
        self.left = left
        self.bottom = bottom
        self.right = right

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXRectangle':

        top = CDXCoordinate.from_bytes(property_bytes[0:4])
        left = CDXCoordinate.from_bytes(property_bytes[4:8])
        bottom = CDXCoordinate.from_bytes(property_bytes[8:12])
        right = CDXCoordinate.from_bytes(property_bytes[12:16])

        return CDXRectangle(top, left, bottom, right)

    def to_bytes(self) -> bytes:

        return self.top.to_bytes() + self.left.to_bytes() + self.bottom.to_bytes() + self.right.to_bytes()

    def to_property_value(self) -> str:

        return self.left.to_property_value() + " " + self.top.to_property_value() + " " \
               + self.right.to_property_value() + " " + self.bottom.to_property_value()


class CDXBoolean(CDXType):
    """
    In CDX files, an INT8 value representing True or Yes if non-zero, and False or No if zero.

    In CDXML files, a enumerated value that may be either yes or no.

    Note that this data type actually has a third implied value, 'unknown'. Since CDX and CDXML are both tagged formats,
    any given property may be omitted altogether from the file. A missing property of this type cannot be assumed to be
    either true or false.
    """

    def __init__(self, value: bool):

        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXBoolean':
        if len(property_bytes) != 1:
            raise ValueError("A Boolean should be exactly of length 1.")
        if property_bytes == b'\x00':
            return CDXBoolean(False)
        else:
            return CDXBoolean(True)

    def to_bytes(self) -> bytes:
        if self.value:
            return b'\x01'
        else:
            return b'\x00'

    def to_property_value(self) -> str:
        if self.value:
            return "yes"
        else:
            return "no"


class CDXBooleanImplied(CDXType):
    """
    In CDX files, an INT8 value representing True or Yes if present, and False or No if absent.

    Note that properties of this type have zero length in CDX files: the only thing that matters is whether the property
    is or isn't present in the file. In contrast to the CDXBoolean data type (above), if a property of this type is
    missing from the CDX file, its value must be assumed to be False or No.

    In CDXML files, a enumerated value that may be either yes or no.

    I've found cases in which the documentation states a property is boolean implied while it actually is not in
    an example file (FractionalWidths, InterpretChemically)
    """

    def __init__(self, value: bool):

        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXBooleanImplied':
        if len(property_bytes) != 0:
            raise ValueError("A BooleanImplied should be 0-length.")
        return CDXBooleanImplied(True)

    def to_bytes(self) -> bytes:
        if not self.value:
            raise ValueError("A BooleanImplied with value 'False' should not be written to cdx file.")
        return b'' # empty bytes, see doc comment -> presence marks True value, absence false

    def to_property_value(self) -> str:
        if self.value:
            return "yes"
        else:
            return "no"


class CDXObjectIDArray(CDXType):

    def __init__(self, ids: list):
        self.ids = ids

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXObjectIDArray':
        if len(property_bytes) % 4 != 0:
            raise ValueError('CDXObjectIDArray must consist of n*4 bytes. Found {} bytes.'.format(len(property_bytes)))
        array_length = len(property_bytes) // 4
        ids = []
        stream = io.BytesIO(property_bytes)
        for i in range(array_length):
            id = int.from_bytes(stream.read(4), "little", signed=False)
            ids.append(id)
        return CDXObjectIDArray(ids)

    def to_bytes(self) -> bytes:
        stream = io.BytesIO()
        for id in self.ids:
            stream.write(id.to_bytes(4, byteorder='little', signed=False))
        stream.seek(0)
        return stream.read()

    def to_property_value(self) -> str:
        return ' '.join(str(x) for x in self.ids)



class CDXAminoAcidTermini(CDXType):
    """
    This type doesn't exist in spec. It's stored as 1 byte in cdx and in ChemDraw 18 there are 2 possible settings
    which are shown as text in cdxml
    """
    def __init__(self, value: int):
        if 1 > value > 2:
            raise ValueError("Currently only 2 values allowed: 1 or 2.")
        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXAminoAcidTermini':
        if len(property_bytes) != 1:
            raise ValueError("CDXAminoAcidTermini should consist of exactly 1 byte.")
        value = int.from_bytes(property_bytes, "little", signed=False)
        return CDXAminoAcidTermini(value)

    def to_bytes(self) -> bytes:
        return self.value.to_bytes(1, byteorder='little', signed=False)

    def to_property_value(self) -> str:
        if self.value == 1:
            return 'HOH'
        elif self.value == 2:
            return 'NH2COOH'


class CDXAutonumberStyle(CDXType):
    """
    This type doesn't exist in spec. It's stored as 1 byte in cdx and in ChemDraw 18 there are 2 possible settings
    which are shown as text in cdxml
    """
    def __init__(self, value: int):
        if 0 > value > 2:
            raise ValueError("Currently only 3 values allowed: 0-2.")
        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXAutonumberStyle':
        if len(property_bytes) != 1:
            raise ValueError("CDXAutonumberStyle should consist of exactly 1 byte.")
        value = int.from_bytes(property_bytes, "little", signed=False)
        return CDXAutonumberStyle(value)

    def to_bytes(self) -> bytes:
        return self.value.to_bytes(1, byteorder='little', signed=False)

    def to_property_value(self) -> str:
        if self.value == 0:
            return 'Roman'
        elif self.value == 1:
            return 'Arabic'
        elif self.value == 2:
            return 'Alphabetic'


class INT8(CDXType):
    """
    This is kind of stupid but makes the upper-level parsing code easier
    """
    def __init__(self, value: int):
        if -128 > value > 127:
            raise ValueError("Needs to be a 16-bit int in range -128 to 127.")
        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'INT8':
        if len(property_bytes) != 1:
            raise ValueError("INT8 should consist of exactly 1 byte.")
        value = int.from_bytes(property_bytes, "little", signed=True)
        return INT8(value)

    def to_bytes(self) -> bytes:
        return self.value.to_bytes(1, byteorder='little', signed=True)

    def to_property_value(self) -> str:
        return str(self.value)


class UINT8(CDXType):
    """
    This is kind of stupid but makes the upper-level parsing code easier
    """
    def __init__(self, value: int):
        if 0 > value > 255:
            raise ValueError("Needs to be a 8-bit uint in range 0 to 255.")
        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'UINT8':
        if len(property_bytes) != 1:
            raise ValueError("UINT8 should consist of exactly 1 byte.")
        value = int.from_bytes(property_bytes, "little", signed=False)
        return UINT8(value)

    def to_bytes(self) -> bytes:
        return self.value.to_bytes(1, byteorder='little', signed=False)

    def to_property_value(self) -> str:
        return str(self.value)


class INT16(CDXType):
    """
    This is kind of stupid but makes the upper-level parsing code easier
    """
    def __init__(self, value: int):
        if -32768 > value > 32767:
            raise ValueError("Needs to be a 16-bit int in range -32768 to 32767.")
        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'INT16':
        if len(property_bytes) != 2:
            raise ValueError("INT16 should consist of exactly 2 bytes.")
        value = int.from_bytes(property_bytes, "little", signed=True)
        return INT16(value)

    def to_bytes(self) -> bytes:
        return self.value.to_bytes(2, byteorder='little', signed=True)

    def to_property_value(self) -> str:
        return str(self.value)


class UINT16(CDXType):
    """
    This is kind of stupid but makes the upper-level parsing code easier
    """
    def __init__(self, value: int):
        if 0 > value > 65535:
            raise ValueError("Needs to be a 16-bit uint in range 0 to 65535.")
        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'UINT16':
        if len(property_bytes) != 2:
            raise ValueError("UINT16 should consist of exactly 2 bytes.")
        value = int.from_bytes(property_bytes, "little", signed=False)
        return UINT16(value)

    def to_bytes(self) -> bytes:
        return self.value.to_bytes(2, byteorder='little', signed=False)

    def to_property_value(self) -> str:
        return str(self.value)


class INT32(CDXType):
    """
    This is kind of stupid but makes the upper-level parsing code easier
    """
    def __init__(self, value: int):
        if -2147483648 > value > 2147483647:
            raise ValueError("Needs to be a 16-bit int in range -32768 to 32767.")
        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'INT32':
        if len(property_bytes) != 4:
            raise ValueError("INT32 should consist of exactly 4 bytes.")
        value = int.from_bytes(property_bytes, "little", signed=True)
        return INT32(value)

    def to_bytes(self) -> bytes:
        return self.value.to_bytes(4, byteorder='little', signed=True)

    def to_property_value(self) -> str:
        return str(self.value)


class UINT32(CDXType):
    """
    This is kind of stupid but makes the upper-level parsing code easier
    """
    def __init__(self, value: int):
        if 0 > value > 4294967295:
            raise ValueError("Needs to be a 32-bit uint in range 0 to 4294967295.")
        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'UINT32':
        if len(property_bytes) != 4:
            raise ValueError("INT32 should consist of exactly 4 bytes.")
        value = int.from_bytes(property_bytes, "little", signed=False)
        return UINT32(value)

    def to_bytes(self) -> bytes:
        return self.value.to_bytes(4, byteorder='little', signed=False)

    def to_property_value(self) -> str:
        return str(self.value)


class Unformatted(CDXType):

    def __init__(self, value: bytes):

        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'Unformatted':
        return Unformatted(property_bytes)

    def to_bytes(self) -> bytes:
        return self.value

    def to_property_value(self) -> str:
        return self.value.hex()