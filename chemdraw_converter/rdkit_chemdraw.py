from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import *
from .chemdraw_objects import *
from .chemdraw_io import *
from lxml import etree as ET
from pathlib import Path
import numpy as np
import math

CM_TO_POINTS = 28.346456693
DEFAULT_ATOM_LABEL_FONT_ID = 3
DEFAULT_ATOM_LABEL_FONT_FACE = 96
DEFAULT_ATOM_LABEL_FONT_SIZE = 10
DEFAULT_ATOM_LABEL_FONT_COLOR = 0

def mol_to_document(mol: rdchem.Mol, style: dict = None, conformer_id: int = -1, margin=1):
    """
    Converts an rdkit molecule into an internal document representation.

    style is a dict containing basic document level settings that influence newly! drawn molecules.

    :param mol: rdkit molecule to convert to document
    :param style: style settings of the document. None takes default settings
    :param conformer_id: id of the conformer to use. Defines 2D coords / orientation of the molecule
    :param margin: margin in cm from the edges of the document. Defines placement of molecule inside document
    :return:
    """

    if style is None:
        m_path = Path(__file__).parent
        template_path = m_path / "ACS 1996.cdxml"
        style, document_properties = get_style_from_template(template_path)
    else:
        document_properties = _dict_to_properties(style)
    document = ChemDrawDocument(properties=document_properties) # or build cdxml doc?

    object_id_sequence = iter(range(1, 10000))
    page = ChemDrawObject(0x8001, "Page", "page", next(object_id_sequence), properties=_get_default_page_properties(),
                          parent=document, children=[])

    # For proper detection and setting of Wedge Bonds
    mol = Chem.Draw.rdMolDraw2D.PrepareMolForDrawing(mol, kekulize = True, addChiralHs = True, wedgeBonds = True)

    conformer = mol.GetConformer(conformer_id)

    atom_coords = _get_coordinates(mol, conformer, float(style["BondLength"]), margin)
    min_coords = np.amin(atom_coords, axis=0)
    max_coords = np.amax(atom_coords, axis=0)
    bb = str(min_coords[0]) + " " + str(min_coords[1]) + " " + str(max_coords[0]) + " " + str(max_coords[1])
    props = {"BoundingBox": bb, "Z": 20}

    frg_obj = ChemDrawObject(0x8003, "Fragment", "fragment", next(object_id_sequence),
                             properties=_dict_to_properties(props), parent=page)

    atom_idx_id = {}
    for idx, atom in enumerate(mol.GetAtoms()):
        object_id = next(object_id_sequence)
        atom_idx_id[idx] = object_id
        p = str(atom_coords[idx][0]) + " " + str(atom_coords[idx][1])
        props = {"p": p, "Z": 20 + object_id, "Element": str(atom.GetAtomicNum())}
        if atom.GetAtomicNum() != 6:
            props["NumHydrogens"] = str(atom.GetNumImplicitHs())
        if atom.HasProp('_CIPCode'):
            props["AS"] = atom.GetProp('_CIPCode')
        elif atom.HasProp('_ChiralityPossible') and atom.GetProp('_ChiralityPossible') == 1:
            props["AS"] = 'U'
        elif atom.HasProp('_ringStereochemCand') and atom.GetProp('_ringStereochemCand') == 1:
            props["AS"] = 'u'
        else:
            props["AS"] = 'N'

        if atom.GetFormalCharge() != 0:
            props["Charge"] = str(atom.GetFormalCharge())

        atom_obj = ChemDrawObject(0x8004, "Node", "n", object_id, properties=_dict_to_properties(props),
                             parent=frg_obj)

        # text label for Heteroatoms or charged carbons
        if atom.GetAtomicNum() != 6 or atom.GetFormalCharge() != 0:
            lbl = atom.GetSymbol()
            if atom.GetTotalNumHs() > 0:
                lbl += "H"
                if atom.GetTotalNumHs() > 1:
                    lbl += str(atom.GetTotalNumHs())

            if atom.GetFormalCharge() > 0:
                if atom.GetFormalCharge() == 1:
                    lbl += "+"
                else:
                    lbl += "+" + str(atom.GetFormalCharge())
            elif atom.GetFormalCharge() < 0:
                if atom.GetFormalCharge() == -1:
                    lbl += "-"
                else:
                    # charge already contains minus symbol no need to add
                    lbl += str(atom.GetFormalCharge())


            cdx_style = CDXFontStyle(int(style.get('LabelFont', DEFAULT_ATOM_LABEL_FONT_ID)),
                                     int(style.get('LabelFace', DEFAULT_ATOM_LABEL_FONT_FACE)),
                                     # Font Size in cdx is 1/20ths of a point
                                     int(float(style.get('LabelSize', DEFAULT_ATOM_LABEL_FONT_SIZE)) * 20),
                                     DEFAULT_ATOM_LABEL_FONT_COLOR)

            cdx_string = CDXString(lbl, style_starts=[0], styles=[cdx_style])
            txt_prop = ChemDrawProperty(0x0700, "Text", cdx_string)
            t = ChemDrawObject(0x8006, "Text", "t", object_id, properties=[txt_prop], parent=atom_obj)

    bonds = {}
    for bond in mol.GetBonds():
        object_id = next(object_id_sequence)
        begin_atom_id = atom_idx_id[bond.GetBeginAtomIdx()]
        end_atom_id = atom_idx_id[bond.GetEndAtomIdx()]
        props = {"Z": 20 + object_id, "B": str(begin_atom_id), "E": str(end_atom_id)}

        bond_type = bond.GetBondType()
        bond_stereo = bond.GetStereo()
        bond_direction = bond.GetBondDir()

        if bond_stereo == rdchem.BondStereo.STEREONONE:
            props["BS"] = "N"
        elif bond_stereo == rdchem.BondStereo.STEREOANY:
            props["BS"] = "U"
        elif bond_stereo == rdchem.BondStereo.STEREOCIS:
            props["BS"] = "Z"
        elif bond_stereo == rdchem.BondStereo.STEREOZ:
            props["BS"] = "Z"
        elif bond_stereo == rdchem.BondStereo.STEREOTRANS:
            props["BS"] = "E"
        elif bond_stereo == rdchem.BondStereo.STEREOE:
            props["BS"] = "E"

        #if bond_type == rdchem.BondType.SINGLE:
            # props["Order"] = "1"
            # Do nothing as absence means single bond in ChemDraw and reduces file size.
        if bond_type == rdchem.BondType.DOUBLE:
            props["Order"] = "2"
        elif bond_type == rdchem.BondType.TRIPLE:
            props["Order"] = "3"
        elif bond_type == rdchem.BondType.QUADRUPLE:
            props["Order"] = "4"
        elif bond_type == rdchem.BondType.QUINTUPLE:
            props["Order"] = "5"
        elif bond_type == rdchem.BondType.HEXTUPLE:
            props["Order"] = "6"
        elif bond_type == rdchem.BondType.ONEANDAHALF:
            props["Order"] = "1.5"
        elif bond_type == rdchem.BondType.AROMATIC:
            props["Order"] = "1.5"
        elif bond_type == rdchem.BondType.TWOANDAHALF:
            props["Order"] = "2.5"
        elif bond_type == rdchem.BondType.THREEANDAHALF:
            props["Order"] = "3.5"
        elif bond_type == rdchem.BondType.FOURANDAHALF:
            props["Order"] = "4.5"
        elif bond_type == rdchem.BondType.FIVEANDAHALF:
            props["Order"] = "5.5"
        elif bond_type == rdchem.BondType.IONIC:
            props["Order"] = "ionic"
        elif bond_type == rdchem.BondType.HYDROGEN:
            props["Order"] = "hydrogen"
        elif bond_type == rdchem.BondType.THREECENTER:
            props["Order"] = "threecenter"
        elif bond_type == rdchem.BondType.DATIVE:
            props["Order"] = "dative"
            #TODO: other dative types

        # Bond Display
        if bond_direction == rdchem.BondDir.BEGINDASH:
            props["Display"] = "WedgedHashBegin"
            _set_end_wedge_display_style(bonds, bond, "WedgedHashEnd")
        elif bond_direction == rdchem.BondDir.BEGINWEDGE:
            props["Display"] = "WedgeBegin"
            _set_end_wedge_display_style(bonds, bond, "WedgeEnd")

        if bond.HasProp("_CDXDisplay"):
            props["Display"] = bond.GetProp("_CDXDisplay")

        bond_obj = ChemDrawObject(0x8005, "Bond", "b", object_id, properties=_dict_to_properties(props), parent=frg_obj)
        bonds[bond.GetIdx()] = bond_obj

    return document


def _set_end_wedge_display_style(bonds: dict, wedge_bond: rdchem.Bond, display: str):
    """
    RDKit only defines start od wedge bond. In ChemDraw if the end of the wegde is connected to another bond said other
    bond needs to have a WedgeEnd display type or else no Wedge is shown. Hence we need to find the bonds connected to
    the end atom

    :param bonds: list of already processed bonds
    :param wedge_bond: the bond to be displayed as Wedge
    :param display: type to display, WedgeEnd or WedgeHashEnd
    :return:
    """
    for b in wedge_bond.GetEndAtom().GetBonds():
        # Avoid self match
        if b.GetIdx() != wedge_bond.GetIdx():
            if b.GetIdx() in bonds:
                props = {}
                bond_obj = bonds[b.GetIdx()]
                props["Display"] = display
                bond_obj.properties.extend(_dict_to_properties(props))
            else:
                b.SetProp("_CDXDisplay", display)


def _dict_to_properties(properties: dict):

    props = []

    for prop_name, prop_value in properties.items():
        tag_id = next(key for key, value in ChemDrawObject.CDX_PROPERTIES.items() if value['name'] == prop_name)
        chemdraw_type = ChemDrawObject.CDX_PROPERTIES[tag_id]["type"]
        logger.debug('Creating property {} of type {}.'.format(prop_name, chemdraw_type))
        klass = globals()[chemdraw_type]

        type_obj = klass.from_string(prop_value)

        prop = ChemDrawProperty(tag_id, prop_name, type_obj)
        props.append(prop)

    return props


def get_style_from_template(template):
    """
    Generates a style dict from an existing chemdraw file

    :param template: a file object, a path or str to a cdx or cdxml file or a string containing the xml
    """
    if isinstance(template, str):
        p = Path(template)
    elif isinstance(template, Path):
        p = template
    else:
        raise TypeError("Expected str or Path but got {} instead.".format(type(template)))

    if p.exists():
        if p.suffix == '.cdxml':
            with open(template, mode='r') as file:
                cdxml = file.read()
                style_dict = _cdxml_str_to_style_dict(cdxml)
        elif p.suffix == '.cdx' or p.suffix == '.cds':
            doc = read_cdx(template)
            cdxml = doc.to_cdxml()
            style_dict = _cdxml_str_to_style_dict(cdxml)
    elif template.startswith("<?xml"):
        style_dict = _cdxml_str_to_style_dict(template)
    else:
        raise ValueError("Template file {} does not exists.".format(template))

    return style_dict, _dict_to_properties(style_dict)


def _cdxml_str_to_style_dict(cdxml: str):
    cdxml = cdxml.encode('utf-8')
    tree = ET.fromstring(cdxml)
    return tree.attrib


def _get_default_page_properties():

    props = {"BoundingBox": "0 0 540 719.75",
             "HeaderPosition": "36",
             "FooterPosition": "36",
             "PrintTrimMarks": "yes",
             "HeightPages": 1,
             "WidthPages": 1
             }
    return _dict_to_properties(props)


def _get_coordinates(mol: rdchem.Mol, conformer: rdchem.Conformer, bond_length: float, margin: float):
    """
    Assume coordinates are already in points (not true) but it works. Then we simply determine the current bond length
    (usually 1.5 = rdkit default) and scale all coordinates so that bond length then matches to the used styles bond
    length in points.

    :param mol: the molecule to scale
    :param conformer: conformer to take coordinates from
    :param bond_length: target bond lengths in points (1 inch = 72 points)
    :param margin: margin from document borders in cm (user input)
    :return:
    """

    coords = conformer.GetPositions()
    max_coords = np.amax(coords, axis=0)
    if max_coords[2] > 0:
        # 3D coords. convert to 2D
        AllChem.Compute2DCoords(mol, bondLength=1.5)
        mol.UpdatePropertyCache()
        conformer = mol.GetConformer()

    bonds = mol.GetBonds()

    if len(bonds) == 0:
        return np.array([[0.0, 0.0, 0.0]])

    total = 0
    for bond in bonds:

        ai = bond.GetBeginAtomIdx()
        aj = bond.GetEndAtomIdx()
        bl = AllChem.GetBondLength(conformer, ai, aj)
        if not math.isnan(bl):
            total += bl

    avg_bl = (total / len(bonds))

    if avg_bl > 0.0:
        #scale
        bl_ratio = bond_length / avg_bl
        coords = conformer.GetPositions()
        c_scaled = coords * bl_ratio
        # make 2 D
        c_scaled = np.delete(c_scaled, 2, 1)
        #transform
        cmin = np.amin(c_scaled, axis=0)
        tx = margin * CM_TO_POINTS  - cmin[0]
        ty = margin * CM_TO_POINTS - cmin[1]
        t = np.array([tx, ty])
        coords_trans = c_scaled + t
        return np.around(coords_trans, decimals=2)
    else:
        raise ValueError("Average Bond Lenght is 0 or negative.")