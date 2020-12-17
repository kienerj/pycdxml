import io
import yaml
from lxml import etree as ET
from pathlib import Path
from enum import Enum
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

    def __init__(self, value: str, style_starts=[], styles=[], charset='iso-8859-1'):
        self.str_value = value
        self.style_starts = style_starts
        self.styles = styles
        self.charset = charset

    @staticmethod
    def from_bytes(property_bytes:bytes, charset='iso-8859-1') -> 'CDXString':

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
        value = stream.read(text_length).decode(charset)        
        logger.debug("Read String '{}' with  {} different styles.".format(value, len(font_styles)))
        return CDXString(value, style_starts, font_styles, charset)

    def to_bytes(self) -> bytes:
        stream = io.BytesIO()
        # number of styles (s elements)
        stream.write(len(self.styles).to_bytes(2, byteorder='little'))
        for idx, style in enumerate(self.styles):
            stream.write(self.style_starts[idx].to_bytes(2, byteorder='little'))
            stream.write(style.to_bytes())
        stream.write(self.str_value.encode(self.charset))
        logger.debug('Wrote CDXString with value {}.'.format(self.str_value))
        stream.seek(0)
        return stream.read()

    def to_element(self, t: ET.Element):
        """
        Takes a t element and adds all the styles as 's' elements.
        This method must only be called from a text object and never for getting a properties value. To get a properties
        value use the 'value' attribute directly.
        :return: the passed in element with the style elements added
        """
        if len(self.style_starts) == 0:
            raise TypeError('Call of to_element on CDXString is invalid if no styles are present. If CDXString is part of a property there are no styles.')        
        for idx, style in enumerate(self.styles):
            s = style.to_element()
            text_start_index = self.style_starts[idx]
            if len(self.styles) > (idx + 1):
                text_end_index = self.style_starts[(idx+1)]
                txt = self.str_value[text_start_index:text_end_index]
                s.text = txt
            else:
                txt = self.str_value[text_start_index:]
                s.text = txt 
            t.append(s)
            logger.debug("Appended style to t element.")
        return t

    def to_property_value(self) -> str:
        return self.str_value


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
        s.attrib['font'] = str(self.font_id)
        s.attrib['size'] = str(self.font_size_points())
        s.attrib['face'] = str(self.font_type)
        s.attrib['color'] = str(self.font_color)
        logger.debug("Created element '{}'.".format(ET.tostring(s, encoding='unicode', method='xml')))
        return s

    def to_property_value(self) -> str:
        return 'font="{}" size="{}" face="{}" color="{}"'.format(self.font_id, self.font_size_points(), self.font_type, self.font_color)


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
        self.coordinate = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXCoordinate':

        value = int.from_bytes(property_bytes, "little", signed=True)
        return CDXCoordinate(value)

    def to_bytes(self) -> bytes:
        return self.coordinate.to_bytes(4, byteorder='little', signed=True)

    def to_property_value(self) -> str:

        return str(round(self.coordinate / CDXCoordinate.CDXML_CONVERSION_FACTOR, 2))


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

        self.bool_value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXBoolean':
        if len(property_bytes) != 1:
            raise ValueError("A Boolean should be exactly of length 1.")
        if property_bytes == b'\x00':
            return CDXBoolean(False)
        else:
            return CDXBoolean(True)

    def to_bytes(self) -> bytes:
        if self.bool_value:
            return b'\x01'
        else:
            return b'\x00'

    def to_property_value(self) -> str:
        if self.bool_value:
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

        self.bool_value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXBooleanImplied':
        if len(property_bytes) != 0:
            raise ValueError("A BooleanImplied should be 0-length.")
        return CDXBooleanImplied(True)

    def to_bytes(self) -> bytes:
        if not self.bool_value:
            raise ValueError("A BooleanImplied with value 'False' should not be written to cdx file.")
        return b'' # empty bytes, see doc comment -> presence marks True value, absence false

    def to_property_value(self) -> str:
        if self.bool_value:
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


class CDXAminoAcidTermini(CDXType, Enum):
    """
    This type doesn't exist in spec. It's stored as 1 byte in cdx and in ChemDraw 18 there are 2 possible settings
    which are shown as text in cdxml
    """
    HOH = 1
    NH2COOH = 2

    def __init__(self, value: int):
        if 1 > value > 2:
            raise ValueError("Currently only 2 values allowed: 1 or 2.")
        self.termini = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXAminoAcidTermini':
        if len(property_bytes) != 1:
            raise ValueError("CDXAminoAcidTermini should consist of exactly 1 byte.")
        value = int.from_bytes(property_bytes, "little", signed=False)
        return CDXAminoAcidTermini(value)

    def to_bytes(self) -> bytes:
        return self.termini.to_bytes(1, byteorder='little', signed=False)

    def to_property_value(self) -> str:
        val = str(CDXAminoAcidTermini(self.termini))
        return val.split('.')[1]


class CDXAutonumberStyle(CDXType, Enum):
    """
    This type doesn't exist in spec. It's stored as 1 byte in cdx and in ChemDraw 18 there are 2 possible settings
    which are shown as text in cdxml
    """
    Roman = 0
    Arabic = 1
    Alphabetic = 2

    def __init__(self, value: int):
        if 0 > value > 2:
            raise ValueError("Currently only 3 values allowed: 0-2.")
        self.autonumber_style = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXAutonumberStyle':
        if len(property_bytes) != 1:
            raise ValueError("CDXAutonumberStyle should consist of exactly 1 byte.")
        value = int.from_bytes(property_bytes, "little", signed=False)
        return CDXAutonumberStyle(value)

    def to_bytes(self) -> bytes:
        return self.autonumber_style.to_bytes(1, byteorder='little', signed=False)

    def to_property_value(self) -> str:
        val = str(CDXAutonumberStyle(self.autonumber_style))
        return val.split('.')[1]  # only actually value without enum name


class CDXBondSpacing(CDXType):

    def __init__(self, value: int):
        if -32768 > value > 32767:
            raise ValueError("Needs to be a 16-bit int in range -32768 to 32767.")
        self.value = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXBondSpacing':
        if len(property_bytes) != 2:
            raise ValueError("INT16 should consist of exactly 2 bytes.")
        value = int.from_bytes(property_bytes, "little", signed=True)
        return CDXBondSpacing(value)

    def to_bytes(self) -> bytes:
        return self.value.to_bytes(2, byteorder='little', signed=True)

    def to_property_value(self) -> str:
        return str(self.value / 10)


class CDXDoubleBondPosition(CDXType, Enum):

    Center = 0     # Double bond is centered, but was positioned automatically by the program
    Right = 1      # Double bond is on the right (viewing from the "begin" atom to the "end" atom), but was positioned automatically by the program
    Left = 2       # Double bond is on the left (viewing from the "begin" atom to the "end" atom), but was positioned automatically by the program
    Center_m = 256 # Double bond is centered, and was positioned manually by the user
    Right_m = 257  # Double bond is on the right (viewing from the "begin" atom to the "end" atom), and was positioned manually by the user
    Left_m = 258   # Double bond is on the left (viewing from the "begin" atom to the "end" atom), and was positioned manually by the user

    def __init__(self, value: int):
        if 0 > value > 258:
            raise ValueError("Needs to be in [0,1,2,256,257,258].")
        self.double_bond_position = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXDoubleBondPosition':
        if len(property_bytes) != 2:
            raise ValueError("CDXDoubleBondPosition should consist of exactly 2 bytes.")
        value = int.from_bytes(property_bytes, "little", signed=True)
        return CDXDoubleBondPosition(value)

    def to_bytes(self) -> bytes:
        return self.double_bond_position.to_bytes(2, byteorder='little', signed=True)

    def to_property_value(self) -> str:
        val = str(CDXDoubleBondPosition(self.double_bond_position))
        val = val.split('.')[1] # only actually value without enum name
        val = val.replace("_m", "") # cdxml only has 3 values, hence remove the trailing _m
        return val


class CDXBondDisplay(CDXType, Enum):

    Solid = 0
    Dash = 1
    Hash = 2
    WedgedHashBegin = 3
    WedgedHashEnd = 4
    Bold = 5
    WedgeBegin = 6
    WedgeEnd = 7
    Wavy = 8
    HollowWedgeBegin = 9
    HollowWedgeEnd = 10
    WavyWedgeBegin = 11
    WavyWedgeEnd = 12
    Dot = 13
    DashDot = 14

    def __init__(self, value: int):
        if 0 > value > 14:
            raise ValueError("Needs to be between 0 and 14")
        self.bond_display = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXBondDisplay':
        if len(property_bytes) != 2:
            raise ValueError("CDXBondDisplay should consist of exactly 2 bytes.")
        value = int.from_bytes(property_bytes, "little", signed=True)
        return CDXBondDisplay(value)

    def to_bytes(self) -> bytes:
        return self.bond_display.to_bytes(2, byteorder='little', signed=True)

    def to_property_value(self) -> str:
        val = str(CDXBondDisplay(self.bond_display))
        return val.split('.')[1]  # only actually value without enum name


class CDXAtomStereo(CDXType, Enum):
    """
    This type doesn't exist in spec. It's an enum and making is a sperate type makes top level parasing consistent.
    This is an enumerated property. Acceptible values are shown in the following list:
    Value	CDXML Name	Description
    0	U	Undetermined
    1	N	Determined to be symmetric
    2	R	Asymmetric: (R)
    3	S	Asymmetric: (S)
    4	r	Pseudoasymmetric: (r)
    5	s	Pseudoasymmetric: (s)
    6	u	Unspecified: The node is not symmetric (might be asymmetric or pseudoasymmetric), but lacks a hash/wedge so
            absolute configuration cannot be determined

    """

    U = 0
    N = 1
    R = 2
    S = 3
    r = 4
    s = 5
    u = 6

    def __init__(self, value: int):
        if 0 > value > 6:
            raise ValueError("Needs to be between 0-6")
        self.atom_stereo = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXAtomStereo':
        if len(property_bytes) != 1:
            raise ValueError("CDXAtomStereo should consist of exactly 1 byte.")
        value = int.from_bytes(property_bytes, "little", signed=True)
        return CDXAtomStereo(value)

    def to_bytes(self) -> bytes:
        return self.atom_stereo.to_bytes(1, byteorder='little', signed=True)

    def to_property_value(self) -> str:
        val = str(CDXAtomStereo(self.atom_stereo))
        return val.split('.')[1]  # only actually value without enum name


class CDXBondStereo(CDXType, Enum):
    """
    This type doesn't exist in spec. It's an enum and making is a sperate type makes top level parasing consistent.

    This is an enumerated property. Acceptible values are shown in the following list:
    Value	CDXML Name	Description
    0	U	Undetermined
    1	N	Determined to be symmetric
    2	E	Asymmetric: (E)
    3	Z	Asymmetric: (Z)
    """
    U = 0
    N = 1
    E = 2
    Z = 3

    def __init__(self, value: int):
        if 0 > value > 3:
            raise ValueError("Needs to be between 0-3")
        self.bond_stereo = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXBondStereo':
        if len(property_bytes) != 1:
            raise ValueError("CDXBondStereo should consist of exactly 1 byte.")
        value = int.from_bytes(property_bytes, "little", signed=True)
        return CDXBondStereo(value)

    def to_bytes(self) -> bytes:
        return self.bond_stereo.to_bytes(1, byteorder='little', signed=True)

    def to_property_value(self) -> str:
        val = str(CDXBondStereo(self.bond_stereo))
        return val.split('.')[1]  # only actually value without enum name


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


class INT16ListWithCounts(CDXType):
    """
    This data type consists of a series of UINT16 values.
    In CDX files, this data type is prefixed by an additional UINT16 value indicating 
    the total number of values to follow.
    """
    def __init__(self, values: list):
        self.values = values

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'INT16ListWithCounts':
        stream = io.BytesIO(property_bytes)
        length = int.from_bytes(stream.read(2), "little", signed=False)
        values=[]
        for i in range(length):
            value = int.from_bytes(stream.read(2), "little", signed=False)
            values.append(value)
        return INT16ListWithCounts(values)

    def to_bytes(self) -> bytes:  
        stream = io.BytesIO()
        length = len(self.values)
        stream.write(length.to_bytes(2, byteorder='little', signed=False))        
        for value in self.values:
            stream.write(value.to_bytes(2, byteorder='little', signed=False)) 
        stream.seek(0)
        return stream.read()
        
    def to_property_value(self) -> str:
        return str(self.values)


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


class CDXBracketUsage(CDXType):
    """
    BracketUsage property is a INT8 enum according to spec. However an example files contained this property as a
    2-byte value where additional byte was 0. So the hacky code in here works around this problem.

    Python doesn't seem to allow having to extend enums when init methods gets more than 1 argument? Hence the inner class
    enum.
    """
    def __init__(self, bracket_usage: int, additional_bytes: bytes = b''):
        self.bracket_usage = bracket_usage
        self.additional_bytes = additional_bytes
        
    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXBracketUsage':
        length = len(property_bytes)
        if length > 1:
            logger.warning("Passed bytes value of length {} to CDXBracketUsage which is an INT8 enum and should be only 1-byte.".format(length))
        additional_bytes = property_bytes[1:]
        val = property_bytes[0]
        return CDXBracketUsage(val)

    def to_bytes(self) -> bytes:
        val = self.bracket_usage.to_bytes(1, byteorder='little', signed=True)
        return val + self.additional_bytes

    def to_property_value(self) -> str:
        val = str(CDXBracketUsage.BracketUsage(self.bracket_usage))
        return val.split('.')[1] # only actually value without enum name

    class BracketUsage(Enum):
        Unspecified = 0
        Unused1 = 1
        Unused2 = 2
        SRU = 3
        Monomer = 4
        Mer = 5
        Copolymer = 6
        CopolymerAlternating = 7
        CopolymerRandom = 8
        CopolymerBlock = 9
        Crosslink = 10
        Graft = 11
        Modification = 12
        Component = 13
        MixtureUnordered = 14
        MixtureOrdered = 15
        MultipleGroup = 16
        Generic = 17
        Anypolymer = 18


class CDXBracketType(CDXType, Enum):

    RoundPair = 0
    SquarePair = 1
    CurlyPair = 2
    Square = 3
    Curly = 4
    Round = 5

    def __init__(self, value: int):
        if 0 > value > 5:
            raise ValueError("Needs to be between 0-5")
        self.bracket_type = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXBracketType':
        if len(property_bytes) != 2:
            raise ValueError("CDXBracketType should consist of exactly 2 byte.")
        value = int.from_bytes(property_bytes, "little", signed=True)
        return CDXBracketType(value)

    def to_bytes(self) -> bytes:
        return self.bracket_type.to_bytes(2, byteorder='little', signed=True)

    def to_property_value(self) -> str:
        val = str(CDXBracketType(self.bracket_type))
        return val.split('.')[1]  # only actually value without enum name


class CDXGraphicType(CDXType, Enum):

    Undefined = 0
    Line = 1
    Arc = 2
    Rectangle = 3
    Oval = 4
    Orbital = 5
    Bracket = 6
    Symbol = 7

    def __init__(self, value: int):
        if 0 > value > 7:
            raise ValueError("Needs to be between 0-7")
        self.graphic_type = value

    @staticmethod
    def from_bytes(property_bytes: bytes) -> 'CDXGraphicType':
        if len(property_bytes) != 2:
            raise ValueError("CDXGraphicType should consist of exactly 2 byte.")
        value = int.from_bytes(property_bytes, "little", signed=True)
        return CDXGraphicType(value)

    def to_bytes(self) -> bytes:
        return self.graphic_type.to_bytes(2, byteorder='little', signed=True)

    def to_property_value(self) -> str:
        val = str(CDXGraphicType(self.graphic_type))
        return val.split('.')[1]  # only actually value without enum name