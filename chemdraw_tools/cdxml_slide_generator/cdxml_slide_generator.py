import xml.etree.ElementTree as ET
import numpy as np
import math
from pathlib import Path
from cdxml_styler import CDXMLStyler


class CDXMLSlideGenerator(object):

    def __init__(self, columns=7, rows=3, font_size=10, font='Arial', number_of_properties=4, slide_width=30.4,
                 slide_height=13, style='ACS 1996'):

        self.style_name = "ACS 1996"
        self.font_size = font_size
        self.font = font
        self.columns = columns
        self.rows = rows
        self.mols_per_slide = columns * rows
        self.number_of_properties = number_of_properties
        # in ChemDraw units (= points with default being 72 DPI)
        self.slide_width = slide_width / 2.54 * 72
        self.slide_height = slide_height / 2.54 * 72
        self.column_width = self.slide_width / columns
        self.row_height = self.slide_height / rows

        self.margin = 5
        self.line_height = font_size + 3
        self.text_height = math.ceil(self.line_height * number_of_properties)
        self.molecule_height = self.row_height - self.text_height - self.margin
        self.molecule_width = self.column_width - self.margin
        self.colortable = {}
        self.fonttable = {}
        self.slide = self._build_base_document(style)
        style_dict = self.extract_style_as_dict()
        self.styler = CDXMLStyler(style_dict=style_dict)

    def generate_slide(self, cdxml_documents, properties):
        """
        Each document is expected to contain exactly 1 entry (=one structure) for the slide there for only the first
        fragment in the first page is extracted and place in the slide per document.

        :param properties:
        :param cdxml_documents:
        :return:
        """

        if cdxml_documents is None:
            raise ValueError('Expected a list of cdxml documents but got \'None\'')

        # cut-off mols + properties silently. I think this is better than raising a ValueError
        cdxml_documents = cdxml_documents[:self.mols_per_slide]
        properties = properties[:self.mols_per_slide]
        if len(cdxml_documents) != len(properties):
            raise ValueError('Number of documents must match number of properties.')

        for index, cdxml in enumerate(cdxml_documents):
            cdxml = self.styler.apply_style_to_string(cdxml)
            root = ET.fromstring(cdxml)
            # Only first structure in document is put into slide
            # fragment can also be in a group inside page so just find inside page doesn't work
            fragment = root.findall('.//fragment')[0]

            # shrinks fragment in case it doesn't fit into available space
            self._shrink_to_fit(fragment)

            # determine final molecule position
            row = index // self.columns
            column = index % self.columns
            x_center = (column + 0.5) * self.column_width
            y_center = row * self.row_height + 0.5 * self.molecule_height

            # get translation coords
            all_coords, node_id_mapping, bonds, label_coords = self.styler.get_coords_and_mapping(fragment)
            # current_x_center, current_y_center = self.styler.get_center(all_coords)
            fragment_bb = np.asarray([float(x) for x in fragment.attrib['BoundingBox'].split(" ")])
            current_x_center = (fragment_bb[0] + fragment_bb[2]) / 2
            current_y_center = (fragment_bb[1] + fragment_bb[3]) / 2

            x_translate = x_center - current_x_center
            y_translate = y_center - current_y_center

            translate = np.array([x_translate, y_translate])
            final_coords = np.round(all_coords + translate, 2)

            # translate in xml
            CDXMLSlideGenerator._translate_bounding_box(fragment, x_translate, y_translate)

            idx = 0
            for node in fragment.iter('n'):
                coords_xml = str(round(final_coords[idx][0], 2)) + " " + str(round(final_coords[idx][1], 2))
                node.attrib['p'] = coords_xml
                idx += 1

            # handle properties
            if self.number_of_properties > 0:
                props = properties[index][:self.number_of_properties]
                y_top = row * self.row_height + self.molecule_height + self.margin
                y_bottom = y_top + self.text_height
                # y_center_props = y_top + 0.5 * self.text_height
                x_left = column * self.column_width + self.margin
                x_right = (column + 1) * self.column_width - self.margin

                txt = ET.Element('t')
                txt.attrib["LineHeight"] = str(self.line_height)
                txt.attrib["id"] = str(5000 + index)
                txt.attrib['BoundingBox'] = "{} {} {} {}".format(x_left, y_top, x_right, y_bottom)
                # TODO: proper position calculation
                # with Arial font 10 the y-coord of p of a t element is 8.95 points higher than the bounding box top edge
                # For Arial this "margin seems to be 89.5 % if the font size
                # But it's different for other fonts
                txt.attrib['p'] = "{} {}".format(x_left, y_top + 0.895 * self.font_size)
                line_starts = []
                text_length = 0
                font_id = self.register_font(self.font)

                for prop_index, prop in enumerate(props):
                    s = ET.SubElement(txt, 's')
                    s.attrib['font'] = str(font_id)
                    s.attrib['color'] = str(self.register_color(prop.color))
                    s.attrib['size'] = str(self.font_size)

                    if prop_index + 1 == self.number_of_properties:
                        s.text = prop.get_display_value()
                    else:
                        s.text = prop.get_display_value() + '\n'
                    text_length += len(s.text)
                    line_starts.append(str(text_length))

                    # Add properties as annotations so that they are exported to sdf!
                    annotation = ET.SubElement(fragment, 'annotation')
                    annotation.attrib['Keyword'] = prop.name
                    annotation.attrib['Content'] = str(prop.value)

                txt.attrib['LineStarts'] = ' '.join(line_starts)
                self.slide.find('page').append(txt)

            self.slide.find('page').append(fragment)

        xml = ET.tostring(self.slide, encoding='unicode', method='xml')
        return self.styler.xml_header + xml

    @staticmethod
    def _translate_bounding_box(element, x_translate, y_translate):

        fragment_bb = np.asarray([float(x) for x in element.attrib['BoundingBox'].split(" ")])
        translate_bb = np.array([x_translate, y_translate, x_translate, y_translate])
        final_bb = fragment_bb + translate_bb
        final_bb = np.round(final_bb, 2)
        element.attrib['BoundingBox'] = "{} {} {} {}".format(final_bb[0], final_bb[1], final_bb[2], final_bb[3])

    def _shrink_to_fit(self, fragment):
        """
        :param fragment: fragment ET element from cdxml
        """
        # scaling factor
        bb = fragment.attrib['BoundingBox']
        bounding_box = [float(x) for x in bb.split(" ")]
        width = bounding_box[2] - bounding_box[0]
        height = bounding_box[3] - bounding_box[1]
        width_factor = self.molecule_width / width
        height_factor = self.molecule_height / height
        scaling_factor = min([width_factor, height_factor])

        annotation = ET.SubElement(fragment, 'annotation')
        annotation.attrib['Keyword'] = "Scaling Factor"

        if scaling_factor < 1:
            all_coords, node_id_mapping, bonds, label_coords = self.styler.get_coords_and_mapping(fragment)
            scaled_coords = all_coords * scaling_factor
            final_coords = self.styler.translate(all_coords, scaled_coords)
            self.styler.fix_bounding_box(fragment, scaling_factor)
            idx = 0
            for node in fragment.iter('n'):
                coords_xml = str(final_coords[idx][0]) + " " + str(final_coords[idx][1])
                node.attrib['p'] = coords_xml
                for t in node.iter('t'):
                    for s in t.iter('s'):
                        # scales Atom Labels
                        s.attrib["size"] = str(float(self.styler.style["LabelSize"]) * scaling_factor)
                idx += 1
            annotation.attrib['Content'] = str(1/scaling_factor * 100)
        else:
            annotation.attrib['Content'] = "100"

    def _build_base_document(self, style):

        sb = ['<page\n id="146"\n HeaderPosition="36"\n FooterPosition="36"\n PageOverlap="0"\n PrintTrimMarks="yes"\n '
              'HeightPages="1"\n WidthPages="1"\n DrawingSpace="poster"', '\n BoundingBox="0 0 ', str(self.slide_width),
              " ", str(self.slide_height), '"\n Width="', str(self.slide_width), '"\n Height="', str(self.slide_height),
              '"\n></page>']
        page = ''.join(sb)

        template_name = style + '.cdxml'
        module_path = Path(__file__).parent
        template_path = module_path / template_name
        tree = ET.parse(template_path)
        root = tree.getroot()
        root.append(ET.fromstring(page))

        # register fonts
        fonttable_xml = root.find("fonttable")

        for font in fonttable_xml.iter("font"):
            font_name = font.attrib["name"]
            font_id = font.attrib["id"]
            self.fonttable[font_name] = int(font_id)

        return root

    def register_color(self, color):
        """

        :param color: a FontColor object
        :return:
        """

        if color.rgb == (0, 0, 0):
            return 0  # black
        if color.rgb == (1, 1, 1):
            return 1  # white

        if color.hex not in self.colortable:

            colortable_xml = self.slide.find('colortable')
            c = ET.SubElement(colortable_xml, 'color')
            c.attrib["r"] = str(color.rgb[0])
            c.attrib["g"] = str(color.rgb[1])
            c.attrib["b"] = str(color.rgb[2])
            # 0=black, 1=white,2=bg,3=fg
            color_index = len(self.colortable) + 4
            self.colortable[color.hex] = color_index
            return color_index
        else:
            return self.colortable[color.hex]

    def register_font(self, font):
        """

        :param font: a Font name like Arial
        :return: int, id of the font
        """

        if font not in self.fonttable:

            font_id = max(self.fonttable.values()) + 1

            fonttable_xml = self.slide.find('fonttable')
            c = ET.SubElement(fonttable_xml, 'font')
            c.attrib["id"] = str(font_id)
            c.attrib["charset"] = "iso-8859-1"
            c.attrib["name"] = font
            self.fonttable[font] = font_id
            return font_id
        else:
            return self.fonttable[font]

    def extract_style_as_dict(self):

        style = {}
        style["BondSpacing"] = self.slide.attrib["BondSpacing"]
        style["BondLength"] = self.slide.attrib["BondLength"]
        style["BoldWidth"] = self.slide.attrib["BoldWidth"]
        style["LineWidth"] = self.slide.attrib["LineWidth"]
        style["MarginWidth"] = self.slide.attrib["MarginWidth"]
        style["HashSpacing"] = self.slide.attrib["HashSpacing"]
        style["CaptionSize"] = self.slide.attrib["CaptionSize"]
        style["LabelSize"] = self.slide.attrib["LabelSize"]
        style["LabelFace"] = self.slide.attrib["LabelFace"]
        style["LabelFont"] = self.slide.attrib["LabelFont"]

        return style


class TextProperty(object):

    def __init__(self, name, value, show_name=False, color=(0, 0, 0)):
        """
        Sets options of the data below the molecule is displayed.

        Color is either a HEX value or a RGB 3-tuple.

        :param name: display name of the property
        :param value: the value of the property
        :param show_name: if the name of the property should be displayed or not
        :param color: color of the text for this property. Default is black.
        """
        self.name = name
        self.value = value
        self.show_name = show_name
        self.color = FontColor(color)

    def get_display_value(self):

        if self.show_name:
            return self.name + ': ' + str(self.value)
        else:
            return str(self.value)


class FontColor(object):

    def __init__(self, color=(0, 0, 0)):

        if isinstance(color, tuple):
            if len(color) == 3:
                # hacky Assumption: if no value bigger 1 -> color range 0->1 /float) else 0-255 (int)
                if max(color) > 1:
                    self.rgb = FontColor._scale_color(color)
                else:
                    self.rgb = color
                self.hex = FontColor.rgb_to_hex(self.rgb)
            else:
                raise ValueError('Expected a RGB color tuple of 3 values. Got tuple with {} values'.format(len(color)))
        elif isinstance(color, str) and color[0] == '#':
            self.rgb = FontColor.hex_to_rgb(color)
            self.hex = color.upper()
        else:
            raise ValueError('Expected a hex color string or RGB 3-tuple but got {}.'.format(color))

    @staticmethod
    def _scale_color(rgb):

        return tuple([round(x/255, 2) for x in rgb])

    @staticmethod
    def hex_to_rgb(hex_code):
        # from stackoverflow
        hex_code = hex_code.lstrip('#').upper()
        rgb = tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))
        return FontColor._scale_color(rgb)

    @staticmethod
    def rgb_to_hex(rgb):
        if 1 > max(rgb) > 0:
            rgb = tuple([round(x * 255, 2) for x in rgb])
        return '#' + ''.join(f'{i:02X}' for i in rgb)
