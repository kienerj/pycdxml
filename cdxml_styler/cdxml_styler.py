import xml.etree.ElementTree as ET
import numpy as np


class CDXMLStyler(object):

    xml_header = """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE CDXML SYSTEM "http://www.cambridgesoft.com/xml/cdxml.dtd" >
"""

    def __init__(self, style_name="ACS 1996", style_source=None):
        """
        The output style can either be defined by selecting one of the built in styles (ACS 1996 or Wiley) or by
        specifying a path to a cdxml file that has the desired style. Note that the structures within a cdxml file
        do not necessarily have the style defined in the cdxml. A easy way to get a style is to open a style sheet (cds)
        and save it as cdxml. But any cdxml document can be used.

        :param style_name: name of built-in style to use (ACS 1996 or Wiley)
        :param style_source: path to cdxml file with the desired style
        """
        if style_source is None:
            self.style = self.get_style(style_name)
        else:
            self.style = self.get_style_from_cdxml(style_source)
    
    def apply_style_to_file(self, cdxml_path, outpath=None):
        """
        Converts the passed in cdxml to the defined style and writes the result to outpath. If outpath is none, the input
        will be overwritten.
        :param cdxml_path: path of cdxml file to convert
        :param outpath: path to write converted file. If None will overwrite input file.
        :return:
        """
        tree = ET.parse(cdxml_path)
        root = tree.getroot()
        result = self._apply_style(root)
        xml = ET.tostring(result, encoding='unicode', method='xml')
        if outpath is None:
            outpath = cdxml_path
        with open(outpath, "w", encoding='UTF-8') as xf:
            file = f"{self.xml_header}{xml}"
            xf.write(file)

    def apply_style_to_string(self, cdxml):

        root = ET.fromstring(cdxml)
        result = self._apply_style(root)

        xml = ET.tostring(result, encoding='unicode', method='xml')
        return self.xml_header + xml

    def _apply_style(self, root) ->str:

        """Applies the selected style to the input cdxml string and all contained drawings and returns the modified
        cdxml as string.

        Parameters:
        root (string): the root element of the cdxml
       """
        # Set stlye on document level

        root.attrib["BondSpacing"] = self.style["BondSpacing"]
        root.attrib["BondLength"] = self.style["BondLength"]
        root.attrib["BoldWidth"] = self.style["BoldWidth"]
        root.attrib["LineWidth"] = self.style["LineWidth"]
        root.attrib["MarginWidth"] = self.style["MarginWidth"]
        root.attrib["HashSpacing"] = self.style["HashSpacing"]
        root.attrib["CaptionSize"] = self.style["CaptionSize"]
        root.attrib["LabelSize"] = self.style["LabelSize"]
        root.attrib["LabelFace"] = self.style["LabelFace"]
        root.attrib["LabelFont"] = self.style["LabelFont"]

        bond_length = float(self.style["BondLength"])

        # Get all nodes (atoms) and bonds
        try:
            for fragment in root.iter('fragment'):

                all_coords, node_id_mapping, bonds, label_coords = CDXMLStyler.get_coords_and_mapping(fragment)

                avg_bl = CDXMLStyler.get_avg_bl(all_coords, bonds, node_id_mapping)

                # Scale Nodes (=Atoms)
                scaling_factor = bond_length / avg_bl
                scaled_coords = all_coords * scaling_factor
                final_coords = CDXMLStyler.translate(all_coords, scaled_coords)
                # Scale atom labels
                if len(label_coords) > 0:
                    scaled_labels = label_coords * scaling_factor
                    final_labels = CDXMLStyler.translate(label_coords, scaled_labels)

                # bounding box of fragment
                CDXMLStyler.fix_bounding_box(fragment, scaling_factor)

                node_attributes = ['id', 'p', 'Z', 'AS', 'Element', 'NumHydrogens', 'Geometry']
                t_attributes = ['p', 'BoundingBox', 'LabelJustification', 'LabelAlignment']

                idx = 0
                label_idx = 0
                for node in fragment.iter('n'):
                    coords_xml = str(final_coords[idx][0]) + " " + str(final_coords[idx][1])
                    node.attrib['p'] = coords_xml

                    unwanted = set(node.attrib) - set(node_attributes)
                    for unwanted_key in unwanted: del node.attrib[unwanted_key]

                    for t in node.iter('t'):
                        #set new coordinates for lables (t elements)
                        coords_label = str(final_labels[label_idx][0]) + " " + str(final_labels[label_idx][1])
                        t.attrib['p'] = coords_label
                        label_idx +=1

                        unwanted = set(t.attrib) - set(t_attributes)
                        for unwanted_key in unwanted: del t.attrib[unwanted_key]

                        for s in t.iter('s'):
                            s.attrib["size"] = self.style["LabelSize"]
                            s.attrib["face"] = self.style["LabelFace"]
                            s.attrib["font"] = self.style["LabelFont"]
                    idx += 1

            return root

        except KeyError:
            # When atoms (the nodes) have no coordinates, attribute p doesn't exist -> Key error
            # If this applies to one fragment, assumption is all fragments have no coordinates
            raise ValueError("Molecule has no coordinates")

    @staticmethod
    def get_coords_and_mapping(fragment):

        bond_attributes = ['id', 'Z', 'B', 'E', 'BS', 'Order', 'BondCircularOrdering', 'Display']

        all_coords = []
        node_id_mapping = {}
        bounding_boxes = {}
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
                label_p= [float(x) for x in t.attrib['p'].split(" ")]
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
            for unwanted_key in unwanted: del bond.attrib[unwanted_key]

        all_coords = np.asarray(all_coords)
        label_coords = np.asarray(label_coords)

        return all_coords, node_id_mapping, bonds, label_coords

    @staticmethod
    def fix_bounding_box(element, scaling_factor):

        fragment_bb = np.asarray([float(x) for x in element.attrib['BoundingBox'].split(" ")])
        scaled_coords = fragment_bb * scaling_factor

        x_center = (fragment_bb[0] + fragment_bb[2]) / 2
        y_center = (fragment_bb[1] + fragment_bb[3]) / 2
        scaled_x_center = (scaled_coords[0] + scaled_coords[2]) / 2
        scaled_y_center = (scaled_coords[1] + scaled_coords[3]) / 2

        x_translate = x_center - scaled_x_center
        y_translate = y_center - scaled_y_center
        translate = np.array([x_translate, y_translate, x_translate, y_translate])
        final_coords = scaled_coords + translate
        final_coords = np.round(final_coords, 2)
        element.attrib['BoundingBox'] = "{} {} {} {}".format(final_coords[0], final_coords[1], final_coords[2], final_coords[3])

    @staticmethod
    def get_center(all_coords):
        """Gets the center of current fragment

        Parameters:
        all_coords (numpy): coordiantes of all nodes(atoms) of the fragment

        Returns:
        tuple: (x,y) center point of fragment

       """

        max_x, max_y = all_coords.max(axis=0)
        min_x, min_y = all_coords.min(axis=0)

        x_center = (min_x + max_x) / 2
        y_center = (min_y + max_y) / 2

        return x_center, y_center

    @staticmethod
    def get_avg_bl(all_coords, bonds, node_id_mapping):
        """Gets the average bond length of current fragment

        Parameters:
        all_coords (numpy): coordiantes of all nodes(atoms) of the fragment
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
    def translate(all_coords, scaled_coords):
        """Translates the scaled fragment back to it's previous center

        Parameters:
        all_coords (numpy): coordinates of all nodes(atoms) of the fragment
        scaled_coords(numpy): coordinates of all nodes(atoms) of the fragment after scaling


        Returns:
        numpy: array of translated coordinates

       """

        x_center, y_center = CDXMLStyler.get_center(all_coords)
        scaled_x_center, scaled_y_center = CDXMLStyler.get_center(scaled_coords)

        x_translate = x_center - scaled_x_center
        y_translate = y_center - scaled_y_center
        translate = np.array([x_translate, y_translate])
        final_coords = scaled_coords + translate
        return final_coords

    @staticmethod
    def get_style_from_cdxml(style_source):

        tree = ET.parse(style_source)
        root = tree.getroot()

        # Set stlye from document
        style = {}
        style["BondSpacing"] = root.attrib["BondSpacing"]
        style["BondLength"] = root.attrib["BondLength"]
        style["BoldWidth"] = root.attrib["BoldWidth"]
        style["LineWidth"] = root.attrib["LineWidth"]
        style["MarginWidth"] = root.attrib["MarginWidth"]
        style["HashSpacing"] = root.attrib["HashSpacing"]
        style["CaptionSize"] = root.attrib["CaptionSize"]
        style["LabelSize"] = root.attrib["LabelSize"]
        style["LabelFace"] = root.attrib["LabelFace"]
        style["LabelFont"] = root.attrib["LabelFont"]

        return style

    @staticmethod
    def get_style(style_name):

        style = {}

        if style_name == "ACS 1996":

            style["BondSpacing"] = "18"
            style["BondLength"] = "14.4"
            style["BoldWidth"] = "2"
            style["LineWidth"] = "0.6"
            style["MarginWidth"] = "1.6"
            style["HashSpacing"] = "2.5"
            style["CaptionSize"] = "10"
            style["LabelSize"] = "10"
            style["LabelFont"] = "3"
            style["LabelFace"] = "96"

        elif style_name == "Wiley":

            style["BondSpacing"] = "18"
            style["BondLength"] = "17"
            style["BoldWidth"] = "2.6"
            style["LineWidth"] = "0.75"
            style["MarginWidth"] = "2"
            style["HashSpacing"] = "2.6"
            style["CaptionSize"] = "12"
            style["LabelSize"] = "12"
            style["LabelFont"] = "3"
            style["LabelFace"] = "96"

        else:
            raise ValueError('{} is not a valid style.'.format(style_name))

        return style
