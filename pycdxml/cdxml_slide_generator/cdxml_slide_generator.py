from lxml import etree as ET
import numpy as np
import math
from pathlib import Path
from ..cdxml_styler import CDXMLStyler
from ..utils import cdxml_io
from ..utils import geometry
from ..utils.style import FontTable
from ..utils.font_handling import *


class CDXMLSlideGenerator(object):

    def __init__(self, columns=7, rows=3, font_size=10, font="Arial", number_of_properties=4, slide_width=30.4,
                 slide_height=13, style="ACS 1996"):

        self.style_name = "ACS 1996"
        self.font_size = font_size
        self.font = font
        self.tt_font = get_font_by_name(self.font)
        self.columns = columns
        self.rows = rows
        self.mols_per_slide = columns * rows
        self.number_of_properties = number_of_properties
        # in ChemDraw units (= points with default being 72 DPI)
        self.slide_width = slide_width / 2.54 * 72
        self.slide_height = slide_height / 2.54 * 72
        self.column_width = self.slide_width / columns
        self.row_height = self.slide_height / rows

        self.margin = 10
        self.line_height = font_size + 3
        self.text_height = math.ceil(self.line_height * number_of_properties)
        self.molecule_height = self.row_height - self.text_height - self.margin
        self.molecule_width = self.column_width - self.margin
        self.colortable = {}
        self.style = style
        self.slide, self.font_table = self._build_base_document(style)
        style_dict = self.slide.attrib
        self.styler = CDXMLStyler(style_dict=style_dict)

    def generate_slides(self, cdxml_documents, properties) -> list:
        """
        Generates as many slides as needed to fit all the documents
        """
        if len(cdxml_documents) != len(properties):
            raise ValueError("Number of documents must match number of properties.")

        nr_of_slides = math.ceil(len(cdxml_documents) / self.mols_per_slide)
        slides = []
        for i in range(nr_of_slides):
            start = i * self.mols_per_slide
            end = (i+1) * self.mols_per_slide
            slide = self.generate_slide(cdxml_documents[start:end], properties[start:end])
            slides.append(slide)
        return slides

    def generate_slide(self, cdxml_documents, properties) -> str:
        """
        Generate a cdxml document containing all the based in documents and property up to how many fit into the
        defined grid of the slide.

        Each document is expected to contain one structure but all of them are taken into account. Having many
        structures in one document likely leads to shrinking of these structures to fit in the space.

        :param cdxml_documents: cdxml documents each one containing 1 molecule to show on the slide
        :param properties: properties of the molecules
        :return:
        """

        if cdxml_documents is None:
            raise ValueError("Expected a list of cdxml documents but got 'None'")

        # cut-off mols + properties silently. I think this is better than raising a ValueError
        cdxml_documents = cdxml_documents[:self.mols_per_slide]
        properties = properties[:self.mols_per_slide]
        if len(cdxml_documents) != len(properties):
            raise ValueError("Number of documents must match number of properties.")

        # initialize slide
        # document must be re-initialized or subsequent calls will use the same document already containing
        # chemical structures and write on top of them
        self.slide, self.font_table = self._build_base_document(self.style)
        self.colortable = {}

        for index, cdxml in enumerate(cdxml_documents):
            cdxml = self.styler.apply_style_to_string(cdxml)
            root = ET.fromstring(bytes(cdxml, encoding="utf8"))

            grp = self._build_group_element(root, index)

            # handle properties
            if self.number_of_properties > 0:
                # determine grid position
                row = index // self.columns
                column = index % self.columns

                props = properties[index][:self.number_of_properties]
                y_top = row * self.row_height + self.molecule_height + self.margin
                y_bottom = y_top + self.text_height
                # y_center_props = y_top + 0.5 * self.text_height
                x_left = column * self.column_width + self.margin
                x_right = (column + 1) * self.column_width - self.margin

                txt = ET.Element("t")
                txt.attrib["LineHeight"] = str(self.line_height)
                txt.attrib["id"] = str(5000 + index)
                txt.attrib["BoundingBox"] = f"{x_left} {y_top} {x_right} {y_bottom}"
                # TODO: proper position calculation
                # with Arial font 10 the y-coord of p of a t element is 8.95 points higher than the bounding box top edge
                # For Arial this "margin seems to be 89.5 % if the font size
                # But it's different for other fonts
                txt.attrib["p"] = f"{x_left} {y_top + 0.895 * self.font_size}"
                line_starts = []
                text_length = 0
                font_id = self.font_table.add_font(self.font)

                for prop_index, prop in enumerate(props):
                    s = ET.SubElement(txt, "s")
                    s.attrib["font"] = str(font_id)
                    s.attrib["color"] = str(self.register_color(prop.color))
                    s.attrib["size"] = str(self.font_size)

                    if prop_index + 1 == self.number_of_properties:
                        s.text = prop.get_display_value()
                    else:
                        s.text = prop.get_display_value() + "\n"
                    text_length += len(s.text)
                    line_starts.append(str(text_length))

                    # Add properties as annotations so that they are exported to sdf!
                    annotation = ET.SubElement(grp, "annotation")
                    annotation.attrib["Keyword"] = prop.name
                    annotation.attrib["Content"] = str(prop.value)

                txt.attrib["LineStarts"] = " ".join(line_starts)
                #self.slide.find('page').append(txt)
                grp.append(txt)

            self.slide.find("page").append(grp)

        return cdxml_io.etree_to_cdxml(self.slide)

    def generate_document(self, cdxml_documents, properties):
        """
        Build a cdxml document containing all the passed in molecules.

        The document will have a fixed width and fixed amount of columns taken from this instances number of columns.
        The height of the document and number of rows will be flexible and depend on the number of input documents

        The height of the individual row can be controlled via `slide_height` and `rows` parameters of this instance.
        eg row_height = slide_height / rows
        """

        if cdxml_documents is None:
            raise ValueError("Expected a list of cdxml documents but got 'None'")

        if len(cdxml_documents) != len(properties):
            raise ValueError("Number of documents must match number of properties.")

        old_num_rows = self.rows
        old_slide_height = self.slide_height
        old_mols_per_slide = self.mols_per_slide
        self.rows = math.ceil(len(cdxml_documents) / self.columns)
        self.slide_height = self.rows * self.row_height
        self.mols_per_slide = len(cdxml_documents)

        doc = self.generate_slide(cdxml_documents, properties)

        # revert settings to prevent side-effects
        self.rows = old_num_rows
        self.slide_height = old_slide_height
        self.mols_per_slide = old_mols_per_slide

        return doc

    def _build_group_element(self, cdxml_root, document_idx: int):
        """
        Build a new group element that contains all the fragments in this document.

        The initial size of the element is the most upper left corner including all fragments and the most lower right
        corner. Then it is scaled to fit into the grid including all fragments.
        """

        fragments = cdxml_root.findall(".//fragment")

        # determine grid position
        row = document_idx // self.columns
        column = document_idx % self.columns

        if len(fragments) == 0:
            # return an empty group element
            grp = ET.Element("group")
            grp.attrib["BoundingBox"] = f"0 0 {self.molecule_width} {self.molecule_height}"
            x_translate, y_translate = self._get_translation_to_grid_position(grp, row, column)
            geometry.fix_bounding_box(grp, x_translate, y_translate)
            return grp

        # determine "minimum" bound box for all fragments
        min_left = 10000
        min_top = 10000
        max_right = 0
        max_bottom = 0

        for fragment in fragments:
            bb = fragment.attrib["BoundingBox"]
            bounding_box = [float(x) for x in bb.split(" ")]
            if bounding_box[0] < min_left:
                min_left = bounding_box[0]
            if bounding_box[1] < min_top:
                min_top = bounding_box[1]
            if bounding_box[2] > max_right:
                max_right = bounding_box[2]
            if bounding_box[3] > max_bottom:
                max_bottom = bounding_box[3]

        # calculate additional margin for atom labels not part of above bounding box
        label_margins = self._get_label_margins(cdxml_root, min_left, min_top, max_right, max_bottom)
        min_left = min_left - label_margins[0]
        min_top = min_top - label_margins[1]
        max_right = max_right + label_margins[2]
        max_bottom = max_bottom + label_margins[3]

        # scaling factor for group bounding box (and hence all fragments
        width = max_right - min_left
        height = max_bottom - min_top
        width_factor = self.molecule_width / width
        height_factor = self.molecule_height / height
        scaling_factor = min([width_factor, height_factor])

        grp = ET.Element("group")
        grp.attrib["BoundingBox"] = f"{min_left} {min_top} {max_right} {max_bottom}"
        annotation = ET.SubElement(grp, "annotation")
        annotation.attrib["Keyword"] = "Scaling Factor"

        if scaling_factor < 1:
            annotation.attrib["Content"] = str(1 / scaling_factor * 100)

            # Scale bounding box of new group element
            coords = np.asarray([[min_left, min_top], [max_right, max_bottom]])
            grp_center = geometry.get_element_center(grp)
            bb_scaled = coords * scaling_factor
            x_translate, y_translate = geometry.get_translation(coords, bb_scaled)
            geometry.fix_bounding_box(grp, x_translate, y_translate, scaling_factor)

            # Translate group element to final position
            x_translate, y_translate = self._get_translation_to_grid_position(grp, row, column)
            geometry.fix_bounding_box(grp, x_translate, y_translate)
            grp_center_final = geometry.get_element_center(grp)

            for fragment in fragments:
                # Final position of fragment is calculated using the distance from the groups center
                # 1. Get distance vector between fragment center and group center unscaled
                # 2. Multiply above vector with scaling factor
                # 3. Scale the fragment
                # 4. Determine distance vector of scaled fragment center from scaled group center
                # 5. Translate fragment by that amount so distance from center remains proportional
                frg_center = geometry.get_element_center(fragment)
                center_distance = np.array(geometry.get_translation_vector(frg_center, grp_center)) * scaling_factor
                self._scale_fragment(fragment, scaling_factor)
                frg_center_scaled = geometry.get_element_center(fragment)
                x_translate = (grp_center_final[0] + center_distance[0]) - frg_center_scaled[0]
                y_translate = (grp_center_final[1] + center_distance[1]) - frg_center_scaled[1]
                self._translate_fragment(fragment, x_translate, y_translate)
                grp.append(fragment)

        else:
            annotation.attrib["Content"] = "100"
            # Translate group element to final position
            x_translate, y_translate = self._get_translation_to_grid_position(grp, row, column)
            geometry.fix_bounding_box(grp, x_translate, y_translate)
            for fragment in fragments:
                # translate by the same amount of the new group element
                self._translate_fragment(fragment, x_translate, y_translate)
                grp.append(fragment)

        return grp

    def _get_label_margins(self, cdxml_root: ET.Element, min_left: float, min_top: float, max_right: float,
                           max_bottom: float):

        # Only nodes with contained text (usually hetero atoms) are relevant
        nodes = cdxml_root.findall(".//n[t]")
        # left, top, right, bottom
        label_margins = [0, 0, 0, 0]
        for node in nodes:
            p = [float(x) for x in node.attrib["p"].split(" ")]
            s = node.find("t").find("s")
            text_width = get_text_width(s.text, self.tt_font, self.font_size)
            # for left and right, a node not at the outer edge can still have text outside the bounding box
            # this text needs to be part of the margin
            # Ideally bond direction is known so text direction could be determined
            # Edge-cases with long labels might still get cut-off labels if abs_tol is too small
            if math.isclose(p[0], min_left,  abs_tol=self.font_size):
                most_left = p[0] - text_width
                margin = p[0] - most_left
                if most_left < p[0] and margin > label_margins[0]:
                    label_margins[0] = margin
            elif math.isclose(p[0], max_right,  abs_tol=self.font_size):
                most_right= p[0] + text_width
                margin = most_right - p[0]
                if most_right < p[0] and margin > label_margins[2]:
                    label_margins[2] = margin
            # Top/Bottom is 1 line always, doesn't depend on text length
            elif math.isclose(p[1], min_top, abs_tol=5):
                label_margins[1] = self.font_size
            elif math.isclose(p[1], max_bottom, abs_tol=5):
                label_margins[3] = self.font_size

        return label_margins

    def _get_translation_to_grid_position(self, element: ET.Element, row: int, column: int):
        """
        Get x and y translation amount for moving the element into the desired grid position.
        The element will be centered vertically and left-aligned.
        """
        bounding_box = np.asarray([float(x) for x in element.attrib["BoundingBox"].split(" ")])
        # grid_center_x = (column + 0.5) * self.column_width
        grid_center_y = row * self.row_height + 0.5 * self.molecule_height + 0.5*self.margin
        # current_x_center = (fragment_bb[0] + fragment_bb[2]) / 2
        current_y_center = (bounding_box[1] + bounding_box[3]) / 2
        x_translate = column * self.column_width + self.margin - bounding_box[0]
        # x_translate = x_center - current_x_center
        # y_translate = row * self.row_height + self.margin - bounding_box[1]
        y_translate = grid_center_y - current_y_center

        return x_translate, y_translate

    def _scale_fragment(self, fragment: ET.Element, scaling_factor):

        all_coords, node_id_mapping, bonds, label_coords = self.styler.get_coords_and_mapping(fragment)
        scaled_coords = all_coords * scaling_factor

        x_translate, y_translate = geometry.get_translation(all_coords, scaled_coords)
        final_coords = geometry.translate(scaled_coords, x_translate, y_translate)
        geometry.fix_bounding_box(fragment, x_translate, y_translate, scaling_factor)

        self._translate_nodes(fragment, final_coords, scaling_factor)

    def _translate_fragment(self, fragment: ET.Element, x_translate: float, y_translate: float):

        all_coords, node_id_mapping, bonds, label_coords = self.styler.get_coords_and_mapping(fragment)
        final_coords = geometry.translate(all_coords, x_translate, y_translate)
        geometry.fix_bounding_box(fragment, x_translate, y_translate)

        self._translate_nodes(fragment, final_coords)

    def _translate_nodes(self, fragment: ET.Element, destination_coordinates, scaling_factor=None):

        idx = 0
        for node in fragment.iter("n"):
            coords_xml = str(destination_coordinates[idx][0]) + " " + str(destination_coordinates[idx][1])
            node.attrib["p"] = coords_xml
            idx += 1
        if scaling_factor is not None:
            # scale all text
            for t in fragment.iter("t"):
                for s in t.iter("s"):
                    # scales Atom Labels
                    s.attrib["size"] = str(round(float(self.styler.style["LabelSize"]) * scaling_factor, 2))
            # TODO: scaling for graphics and other elements like arrows, curves...

    def _build_base_document(self, style):

        sb = ['<page\n id="146"\n HeaderPosition="36"\n FooterPosition="36"\n PageOverlap="0"\n PrintTrimMarks="yes"\n '
              'HeightPages="1"\n WidthPages="1"\n DrawingSpace="poster"', '\n BoundingBox="0 0 ', str(self.slide_width),
              " ", str(self.slide_height), '"\n Width="', str(self.slide_width), '"\n Height="', str(self.slide_height),
              '"\n></page>']
        page = "".join(sb)

        template_name = style + ".cdxml"
        module_path = Path(__file__).parent
        template_path = module_path / template_name
        tree = ET.parse(template_path.__str__())
        root = tree.getroot()
        root.append(ET.fromstring(page))

        # register fonts
        fonttable_xml = root.find("fonttable")

        font_table = FontTable(fonttable_xml)

        return root, font_table

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

            colortable_xml = self.slide.find("colortable")
            c = ET.SubElement(colortable_xml, "color")
            c.attrib["r"] = str(color.rgb[0])
            c.attrib["g"] = str(color.rgb[1])
            c.attrib["b"] = str(color.rgb[2])
            # 0=black, 1=white,2=bg,3=fg
            color_index = len(self.colortable) + 4
            self.colortable[color.hex] = color_index
            return color_index
        else:
            return self.colortable[color.hex]


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
            return self.name + ": " + str(self.value)
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
                raise ValueError(f"Expected a RGB color tuple of 3 values. Got tuple with {len(color)} values")
        elif isinstance(color, str) and color[0] == "#":
            self.rgb = FontColor.hex_to_rgb(color)
            self.hex = color.upper()
        else:
            raise ValueError(f"Expected a hex color string or RGB 3-tuple but got {color}.")

    @staticmethod
    def _scale_color(rgb):

        return tuple([round(x/255, 2) for x in rgb])

    @staticmethod
    def hex_to_rgb(hex_code):
        # from stackoverflow
        hex_code = hex_code.lstrip("#").upper()
        rgb = tuple(int(hex_code[i:i + 2], 16) for i in (0, 2, 4))
        return FontColor._scale_color(rgb)

    @staticmethod
    def rgb_to_hex(rgb):
        if 1 > max(rgb) > 0:
            rgb = tuple([round(x * 255, 2) for x in rgb])
        return "#" + "".join(f"{i:02X}" for i in rgb)
