from ..utils import style
from ..utils import cdxml_io
from ..utils import geometry
from ..cdxml_converter import ChemDrawDocument
from lxml import etree as ET
import numpy as np
import logging
from pathlib import Path
import yaml

logger = logging.getLogger('pycdxml.cdxml_styler')


class CDXMLStyler(object):

    def __init__(self, style_name: str = "ACS 1996", style_source=None, style_dict: dict = None):
        """
        The output style can be defined by selecting one of the built-in styles (ACS 1996 or Wiley), by
        specifying a path to a cdxml file that has the desired style or by supplying a dictionary containing the needed
        style settings.

        Note that the structures within a cdxml file do not necessarily have the style defined in the cdxml. An easy way
        to get a style is to open a style sheet (cds) and save it as cdxml. But any cdxml document can be used.

        For a style_dict the required settings are:

       BondSpacing, BondLength, BoldWidth, LineWidth, MarginWidth, HashSpacing, CaptionSize, LabelSize, LabelFace
       and LabelFont.

       Font Handling:

       text objects contain a reference (and id) to a font in the documents' font table.
       In case of a named style, that styles default font is used.
       In case of a template (style_source), the font with the lowest id is used
       In case of style_dict, 'LabelFont' must be a name of a valid font (not verified) like 'Arial'.


        :param style_name: name of built-in style to use (ACS 1996 or Wiley)
        :param style_source: path to cdxml file with the desired style
        :param style_dict: dict containing the required style settings
        """
        if style_source is not None:
            self.style = style.get_style_from_template(style_source)
        elif style_dict is not None:
            self.style = style_dict
        else:
            self.style = self.get_style(style_name)

    def apply_style_to_file(self, cdxml_path, outpath=None):
        """
        Converts the passed in cdxml to the defined style and writes the result to outpath. If outpath is none, the
        input will be overwritten.
        :param cdxml_path: path of cdxml file to convert
        :param outpath: path to write converted file. If None overwrite input file.
        """
        logger.debug("Applying style {} to file {}.".format(self.style, cdxml_path))
        tree = ET.parse(cdxml_path)
        root = tree.getroot()
        result = self._apply_style(root)
        logger.debug("Style applied. Preparing for output.")
        xml = cdxml_io.etree_to_cdxml(result)
        if outpath is None:
            logger.info("Output path is None, overwriting input file.")
            outpath = cdxml_path
        with open(outpath, "w", encoding='UTF-8') as xf:
            xf.write(xml)
        logger.debug("Style successfully applied and written output to file {}.".format(outpath))

    def apply_style_to_string(self, cdxml: str) -> str:
        """
        Takes a cdxml as string, applies the style and returns a new cdxml as string.

        :param cdxml: string containing cdxml data

        :return: string containing cdxml with the desired style applied
        """
        logger.debug("Applying style {} to a cdxml string.".format(self.style))
        root = ET.fromstring(bytes(cdxml, encoding='utf8'))
        result = self._apply_style(root)
        logger.debug("Style applied. Returning result cdxml string.")
        return cdxml_io.etree_to_cdxml(result)

    def apply_style_to_doc(self, doc: ChemDrawDocument):
        """
        Applies style to the given ChemDrawDocument instance

        :param doc: Document to apply style to
        """
        self._apply_style(doc.cdxml.getroot())

    def _apply_style(self, root: ET.Element) -> ET.Element:
        """
        Applies the selected style to the input cdxml string and all contained drawings and returns the modified
        cdxml as string.

        :param root: root element of the cdxml document
       """
        # Set style on document level
        logger.debug("Setting style on document level.")

        # Change LabelFont from font_name to font_id
        font_table = style.get_font_table(root)
        font_id = font_table.add_font(self.style["LabelFont"])

        root.attrib["BondSpacing"] = self.style["BondSpacing"]
        root.attrib["BondLength"] = self.style["BondLength"]
        root.attrib["BoldWidth"] = self.style["BoldWidth"]
        root.attrib["LineWidth"] = self.style["LineWidth"]
        root.attrib["MarginWidth"] = self.style["MarginWidth"]
        root.attrib["HashSpacing"] = self.style["HashSpacing"]
        root.attrib["CaptionSize"] = self.style["CaptionSize"]
        root.attrib["LabelSize"] = self.style["LabelSize"]
        root.attrib["LabelFace"] = self.style["LabelFace"]
        root.attrib["LabelFont"] = str(font_id)

        # if not present, specification says it means "no"
        implicit_h_source = root.attrib.get("HideImplicitHydrogens", 'no')
        root.attrib["HideImplicitHydrogens"] = self.style["HideImplicitHydrogens"]
        implicit_h_changed = implicit_h_source != self.style["HideImplicitHydrogens"]

        bond_length = float(self.style["BondLength"])

        # Get all nodes (atoms) and bonds
        logger.debug("Start applying style to molecules.")
        try:
            global_coords, global_avg_bl = CDXMLStyler.get_coords_for_document(root)
            if global_avg_bl > 0:
                scaling_factor = bond_length / global_avg_bl
            else:
                scaling_factor = 1
            scaled_global_coords = global_coords * scaling_factor
            x_translate, y_translate = geometry.get_translation(global_coords, scaled_global_coords)

            # 3D attributes tobe deleted since they can't be transformed; BoundingBox is enough for correct rendering
            graphic_deletable = ['Center3D', 'MajorAxisEnd3D', 'MinorAxisEnd3D']
            for element in root.xpath("//page/*[not(ancestor-or-self::fragment)]"):
                if 'p' in element.attrib:
                    # set new coordinates for p outside any fragment
                    p_coords = element.attrib['p']
                    p_coords = [float(c) * scaling_factor for c in p_coords.split(' ')]
                    p_coords = [p_coords[0] + x_translate, p_coords[1] + y_translate]
                    coords_label = str(p_coords[0]) + ' ' + str(p_coords[1])
                    element.attrib['p'] = coords_label

                if 'BoundingBox' in element.attrib:
                    geometry.fix_bounding_box(element, x_translate, y_translate, scaling_factor)

                if element.tag == 'graphic':
                    for gda in graphic_deletable:
                        if gda in element.attrib:
                            del element.attrib[gda]

            for fragment in root.iter('fragment'):
                logger.debug("Applying style to fragment with id {}.".format(fragment.attrib["id"]))
                CDXMLStyler.add_missing_bounding_box(fragment)
                logger.debug("Getting coordinates and mapping.")
                all_coords, node_id_mapping, bonds, label_coords = CDXMLStyler.get_coords_and_mapping(fragment)

                num_nodes = len(node_id_mapping)
                if num_nodes == 0:
                    raise ValueError("Molecule has no Atoms")

                scaled_coords = all_coords * scaling_factor

                logger.debug("Determining new coordinates.")
                final_coords = geometry.translate(scaled_coords, x_translate, y_translate)
                # Scale atom labels
                if len(label_coords) > 0:
                    scaled_labels = label_coords * scaling_factor
                    x_translate_label, y_translate_label = \
                        geometry.get_translation(label_coords, scaled_labels)
                    final_labels = geometry.translate(scaled_labels, x_translate_label, y_translate_label)

                # bounding box of fragment
                geometry.fix_bounding_box(fragment, x_translate, y_translate, scaling_factor)

                for graphic in fragment.iter('graphic'):
                    geometry.fix_bounding_box(graphic, x_translate, y_translate, scaling_factor)
                    for gda in graphic_deletable:
                        if gda in graphic.attrib:
                            del graphic.attrib[gda]

                for cv in fragment.iter('curve'):
                    CDXMLStyler.fix_curve_points(cv, x_translate, y_translate, scaling_factor)

                logger.debug("Applying new coordinates and label styles.")

                unwanted_node_attributes = ['LabelFont', 'LabelSize', 'LabelFace', 'LineWidth']
                t_attributes = ['p', 'BoundingBox', 'LabelJustification', 'LabelAlignment', 'Z']

                idx = 0
                label_idx = 0
                for node in fragment.iter('n'):
                    coords_xml = str(final_coords[idx][0]) + " " + str(final_coords[idx][1])
                    node.attrib['p'] = coords_xml

                    for unwanted_key in unwanted_node_attributes:
                        logger.info("Deleting unneeded attribute {} from node element.".format(unwanted_key))
                        if unwanted_key in node.attrib:
                            del node.attrib[unwanted_key]

                    for t in node.iter('t'):
                        if 'p' in t.attrib:
                            # set new coordinates for labels (t elements)
                            coords_label = str(final_labels[label_idx][0]) + " " + str(final_labels[label_idx][1])
                            t.attrib['p'] = coords_label
                            label_idx += 1

                        unwanted = set(t.attrib) - set(t_attributes)
                        for unwanted_key in unwanted:
                            logger.info("Deleting unneeded attribute {} from text element.".format(unwanted_key))
                            del t.attrib[unwanted_key]

                        for s in t.iter('s'):
                            s.attrib["size"] = self.style["LabelSize"]
                            # see https://www.cambridgesoft.com/services/documentation/sdk/chemdraw/cdx/DataType/CDXString.htm
                            # for explanation on magic numbers. 64 = superscript, >64 with additional styling
                            # eg, 65 would be superscript and bold
                            if "face" in s.attrib and int(s.attrib["face"]) ^ 64 < 32:
                                # preserve style of superscript if default label face is bold or italic
                                # I label face by default is 96 for formula. if it is also bold it would be 98
                                # 98 - 96 = 2 and we add that to the superscript style of 64 -> 66 -> bold superscript
                                s.attrib["face"] = str(64 | (int(self.style["LabelFace"]) - 96))
                            else:
                                # by default this is usually 96 for atom labels which handles subscripts automatically
                                s.attrib["face"] = self.style["LabelFace"]
                            s.attrib["font"] = str(font_id)

                            # Change implicit hydrogen display if needed
                            if implicit_h_changed \
                                    and "NumHydrogens" in node.attrib and int(node.attrib["NumHydrogens"]) > 0:
                                if self.style["HideImplicitHydrogens"] == "no":
                                    # add implicit Hs to text
                                    txt = s.text
                                    if int(node.attrib["NumHydrogens"]) == 1:
                                        txt += "H"
                                    else:
                                        txt += "H" + str(node.attrib["NumHydrogens"])
                                    s.text = txt
                                else:
                                    # remove Hs from text
                                    txt = s.text
                                    if txt[1] == "H":
                                        # One letter atom Symbol
                                        txt = txt[0]
                                    else:
                                        # Two letter atom Symbol
                                        txt = txt[:2]
                                    s.text = txt
                    idx += 1

                # scale font size of bond labels for query bonds like the S/D bond type
                query_bond_texts = fragment.xpath('b/objecttag[@Name="query"]/t/s')
                for s in query_bond_texts:
                    s.attrib["size"] = str(float(self.style["LabelSize"]) * 0.75)
                    s.attrib["face"] = self.style["LabelFace"]
                    s.attrib["font"] = str(font_id)

            return root

        except KeyError as err:
            # When atoms (the nodes) have no coordinates, attribute 'p' doesn't exist and a KeyError is raised
            # If this applies to one fragment, assumption is all fragments have no coordinates. It also seems bad
            # to fix the file partially and ignore this issue.
            logger.error(err)
            raise ValueError("A likely cause of the original KeyError is that the molecule has no coordinates. "
                             "This is the case if the key error is caused by a missing key of 'p'.") from err

    @staticmethod
    def add_missing_bounding_box(fragment: ET.Element):

        if 'BoundingBox' not in fragment.attrib:
            all_coords = []
            for node in fragment.iter('n'):
                if 'p' in node.attrib:
                    coords_raw = node.attrib['p']
                    coords = [float(x) for x in coords_raw.split(" ")]
                    all_coords.append(coords)
                else:
                    raise ValueError("Molecule has no coordinates")
            # add missing BoundingBox
            all_coords = np.asarray(all_coords)
            max_x, max_y = all_coords.max(axis=0)
            min_x, min_y = all_coords.min(axis=0)
            fragment.attrib['BoundingBox'] = "{} {} {} {}".format(min_x, min_y, max_x, max_y)

    @staticmethod
    def get_coords_for_document(root: ET.Element):
        all_coords_doc = []
        bond_counts = []
        bond_lengths = []
        for fragment in root.iter('fragment'):
            all_coords, node_id_mapping, bonds, label_coords = CDXMLStyler.get_coords_and_mapping(fragment)
            if len(bonds) > 0:
                avg_bl = CDXMLStyler.get_avg_bl(all_coords, bonds, node_id_mapping)
                bond_counts.append(len(bonds))
                bond_lengths.append(avg_bl)
            for c in all_coords:
                all_coords_doc.append(c)
        if len(bond_counts) == 0:
            return np.asarray(all_coords_doc), 0
        # get index of the biggest fragment
        max_idx = bond_counts.index(max(bond_counts))
        avg_bl = round(bond_lengths[max_idx], 2)
        return np.asarray(all_coords_doc), avg_bl

    @staticmethod
    def get_coords_and_mapping(fragment: ET.Element) -> tuple:

        bond_attributes = ['id', 'Z', 'B', 'E', 'BS', 'Order', 'BondCircularOrdering', 'Display']

        all_coords = []
        node_id_mapping = {}
        label_coords = []
        label_bbs = []
        bonds = []

        idx = 0
        for node in fragment.iter('n'):
            coords_raw = node.attrib['p']
            coords = [float(x) for x in coords_raw.split(" ")]
            all_coords.append(coords)
            node_id_mapping[int(node.attrib['id'])] = idx
            for t in node.iter('t'):
                if 'p' in t.attrib:
                    label_p = [float(x) for x in t.attrib['p'].split(" ")]
                    label_coords.append(label_p)
                    label_bb = [float(x) for x in t.attrib['BoundingBox'].split(" ")]
                    label_bbs.append(label_bb)
            idx += 1
        for bond in fragment.iter('b'):
            bond_dict = {'start': int(bond.attrib['B']), 'end': int(bond.attrib['E'])}
            bonds.append(bond_dict)
            # Remove bond attributes set at bond level
            # Removing them will use the document level settings
            unwanted = set(bond.attrib) - set(bond_attributes)
            for unwanted_key in unwanted:
                logger.info("Deleting unneeded attribute {} from bond element.".format(unwanted_key))
                del bond.attrib[unwanted_key]

        all_coords = np.asarray(all_coords)
        label_coords = np.asarray(label_coords)

        return all_coords, node_id_mapping, bonds, label_coords

    @staticmethod
    def get_avg_bl(all_coords: dict, bonds: list, node_id_mapping: dict) -> float:
        """Gets the average bond length of current fragment

        Parameters:
        all_coords (numpy): coordinates of all nodes(atoms) of the fragment
        bonds (list of dict): list of bonds where bond is a dict with start and end node id
        node_id_mapping (dict): maps node id to node idx

        Returns:
        float: average bond length rounded to 1 digit after dot

       """

        a = []
        b = []
        for bond in bonds:
            index_start = node_id_mapping[bond['start']]
            index_end = node_id_mapping[bond['end']]
            a.append(all_coords[index_start])
            b.append(all_coords[index_end])

        a = np.asarray(a)
        b = np.asarray(b)

        bond_length = np.linalg.norm(a - b, axis=1)  # thanks to stackoverflow
        avg_bl = round(np.mean(bond_length), 1)
        return avg_bl

    @staticmethod
    def fix_curve_points(element: ET.Element, xt: float, yt: float, scaling_factor: float):
        if 'CurvePoints' not in element.attrib:
            return
        p_val = element.attrib['CurvePoints']
        frs = p_val.split(' ')
        trans_array = []
        for idx in range(0, len(frs)):
            if idx % 2 == 0:
                trans_array.append(float(frs[idx]) * scaling_factor + xt)
            else:
                trans_array.append(float(frs[idx]) * scaling_factor + yt)
        trans_array = np.round(trans_array, 2)
        trans_array_text = [str(f) for f in trans_array]
        element.attrib['CurvePoints'] = ' '.join(trans_array_text)

    @staticmethod
    def get_style(style_name):

        if not hasattr(CDXMLStyler, "STYLES"):
            module_path = Path(__file__).parent

            styles_path = module_path / 'styles.yml'
            with open(styles_path, 'r') as stream:
                CDXMLStyler.STYLES = yaml.safe_load(stream)

        if style_name in CDXMLStyler.STYLES:
            return CDXMLStyler.STYLES[style_name]
        else:
            logger.exception(f"Trying to apply unknown named style {style_name}.")
            raise ValueError(f'{style_name} is not an available named style.')
