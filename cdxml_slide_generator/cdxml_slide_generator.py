import xml.etree.ElementTree as ET
import numpy as np
import math
from pathlib import Path
import sys
sys.path.insert(0, 'C:\\Users\\kienerj\\PycharmProjects\\CDXMLStyler')
from cdxml_styler import CDXMLStyler


class CDXMLSlideGenerator(object):

    def __init__(self, columns=7, rows=3, font_size=10, font='Arial', number_of_properties=4, slide_width=30.4,
                 slide_height=13):

        self.style_name = "ACS 1996"
        self.font_size = font_size
        self.font = font
        self.columns = columns
        self.rows = rows
        self.mols_per_slide = columns * rows
        self.number_of_properties = number_of_properties
        #in ChemDraw units (= points with default being 72 DPI)
        self.slide_width = slide_width / 2.54 * 72
        self.slide_height = slide_height / 2.54 * 72
        self.column_width = self.slide_width / columns
        self.row_height = self.slide_height / rows

        self.margin = 5
        self.line_height = font_size + 2
        self.text_height = math.ceil(self.line_height * number_of_properties)
        self.molecule_height = self.row_height - self.text_height - self.margin
        self.molecule_width = self.column_width - self.margin
        self.styler = CDXMLStyler()

    def generate_slide(self, cdxml_documents):
        """
        Each document is expected to contain exactly 1 entry (=one structure) for the slide there for only the first
        fragment in the first page is extracted and place in the slide per document.

        :param cdxml_documents:
        :return:
        """

        slide = self._build_base_document()

        for index, cdxml in enumerate(cdxml_documents):
            # Set style to ACS 1996
            cdxml = self.styler.apply_style_to_string(cdxml)
            root = ET.fromstring(cdxml)
            # Only first structure in document is put into slide
            fragment = root.find('page').find('fragment')

            #shrinks fragment in case it doesn't fit into available space
            self._shrink_to_fit(fragment)

            #determine final molecule position
            row = index // self.columns
            column = index % self.columns
            x_center = (column + 0.5) * self.column_width
            y_center = row * self.row_height+ 0.5 * self.molecule_height

            # get translation coords
            all_coords, node_id_mapping, bonds, label_coords = self.styler.get_coords_and_mapping(fragment)
            #current_x_center, current_y_center = self.styler.get_center(all_coords)
            fragment_bb = np.asarray([float(x) for x in fragment.attrib['BoundingBox'].split(" ")])
            current_x_center = (fragment_bb[0] + fragment_bb[2]) / 2
            current_y_center = (fragment_bb[1] + fragment_bb[3]) / 2

            x_translate = x_center - current_x_center
            y_translate = y_center - current_y_center

            translate = np.array([x_translate, y_translate])
            final_coords = np.round(all_coords + translate,2)

            # translate in xml
            CDXMLSlideGenerator._translate_bounding_box(fragment, x_translate, y_translate)

            idx = 0
            for node in fragment.iter('n'):
                coords_xml = str(round(final_coords[idx][0], 2)) + " " + str(round(final_coords[idx][1], 2))
                node.attrib['p'] = coords_xml
                idx += 1

            slide.find('page').append(fragment)

        xml = ET.tostring(slide, encoding='unicode', method='xml')
        return self.styler.xml_header + xml

    @staticmethod
    def _translate_bounding_box(element, x_translate, y_translate):

        fragment_bb = np.asarray([float(x) for x in element.attrib['BoundingBox'].split(" ")])
        translate_bb = np.array([x_translate, y_translate, x_translate, y_translate])
        final_bb = fragment_bb + translate_bb
        final_bb = np.round(final_bb, 2)
        element.attrib['BoundingBox'] = "{} {} {} {}".format(final_bb[0], final_bb[1], final_bb[2], final_bb[3])

    def _shrink_to_fit(self, fragment):

        # scaling factor
        bb = fragment.attrib['BoundingBox']
        bounding_box = [float(x) for x in bb.split(" ")]
        width = bounding_box[2] - bounding_box[0]
        height = bounding_box[3] - bounding_box[1]
        width_factor = self.molecule_width / width
        height_factor = self.molecule_height / height
        scaling_factor = min([width_factor, height_factor])

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

    def _build_base_document(self):

        sb = ['<page\n id="146"\n HeaderPosition="36"\n FooterPosition="36"\n PageOverlap="0"\n PrintTrimMarks="yes"\n '
              'HeightPages="1"\n WidthPages="1"\n DrawingSpace="poster"', '\n BoundingBox="0 0 ', str(self.slide_width), " ",
              str(self.slide_height), '"\n Width="', str(self.slide_width), '"\n Height="', str(self.slide_height), '"\n></page>']
        page = ''.join(sb)

        module_path = Path(__file__).parent
        template_path = module_path / 'template.cdxml'
        tree = ET.parse(template_path)
        root = tree.getroot()
        root.append(ET.fromstring(page))

        return root
