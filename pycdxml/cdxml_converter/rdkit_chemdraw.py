from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem.Draw import rdMolDraw2D
from rdkit.Chem import *
from .chemdraw_objects import *
from .chemdraw_io import *
from ..utils import style
from lxml import etree as ET
from pathlib import Path
import numpy as np
import math
import logging

logger = logging.getLogger('pycdxml.rdkit_chemdraw')

CM_TO_POINTS = 28.346456693
DEFAULT_ATOM_LABEL_FONT_ID = 3
DEFAULT_ATOM_LABEL_FONT_FACE = 96
DEFAULT_ATOM_LABEL_FONT_SIZE = 10
DEFAULT_ATOM_LABEL_FONT_COLOR = 0
# Empirically determined value
DEFAULT_AVG_BOND_LENGTH = 0.825


def mol_to_document(mol: Chem.Mol, chemdraw_style: dict = None, conformer_id: int = -1, margin=1,
                    include_enhanced_stereo=True, crossed_bonds=True):
    """
    Converts a rdkit molecule into an internal document representation.

    style is a dict containing basic document level settings that influence newly! drawn molecules.

    :param mol: rdkit molecule to convert to document
    :param chemdraw_style: style settings of the document. None takes default settings
    :param conformer_id: id of the conformer to use. Defines 2D coords / orientation of the molecule
    :param margin: margin in cm from the edges of the document. Defines placement of molecule inside document
    :param include_enhanced_stereo: if enhanced stereo should be included in the cdxml
    :param crossed_bonds: if double bonds with undefined stereo should be drawn as crossed bonds (wavy bond)
    :return:
    """

    if mol is None:
        raise ValueError("Argument 'mol' is None. Expected valid RDKit molecule object.")

    # Use ACS 1996 as default style to build cdxml document
    # m_path = Path('C:/Users/kienerj/PycharmProjects/PyCDXML/pycdxml/cdxml_slide_generator')
    m_path = Path(__file__).parent.parent
    template_path = m_path / "cdxml_slide_generator" / "ACS 1996.cdxml"
    cdxml = ET.parse(str(template_path))
    root = cdxml.getroot()

    if chemdraw_style is not None:
        # if style is passed in, overwrite the attributes
        for key, value in chemdraw_style.items():
            root.attrib[key] = str(value)

    if len(mol.GetAtoms()) < 1:
        # Empty molfile -> return empty cdxml
        return ChemDrawDocument(cdxml)

    object_id_sequence = iter(range(1, 10000))
    page = ET.SubElement(root, "page")
    page.attrib['id'] = str(next(object_id_sequence))
    page.attrib.update(_get_default_page_properties())

    # For proper detection and setting of Wedge Bonds
    mol = Chem.Draw.rdMolDraw2D.PrepareMolForDrawing(mol, kekulize=True, addChiralHs=True, wedgeBonds=True)

    conformer = mol.GetConformer(conformer_id)

    atom_coords = _get_coordinates(mol, conformer, float(root.attrib["BondLength"]), margin)
    min_coords = np.amin(atom_coords, axis=0)
    max_coords = np.amax(atom_coords, axis=0)
    bb = str(min_coords[0]) + " " + str(min_coords[1]) + " " + str(max_coords[0]) + " " + str(max_coords[1])
    props = {"BoundingBox": bb, "Z": "20"}

    fragment = ET.SubElement(page, "fragment")
    fragment.attrib['id'] = str(next(object_id_sequence))
    fragment.attrib.update(props)

    # Advanced Stereo handling
    # remap based on ato, idx
    if include_enhanced_stereo:
        adv_stereo_grps = mol.GetStereoGroups()
        adv_stereo_by_atom = {}
        group_id = 1
        for stereo_grp in adv_stereo_grps:
            stereo_type = stereo_grp.GetGroupType()
            stereo_name = ''
            if stereo_type == Chem.StereoGroupType.STEREO_ABSOLUTE:
                stereo_name = 'Absolute'
            elif stereo_type == Chem.StereoGroupType.STEREO_AND:
                stereo_name = 'And'
            elif stereo_type == Chem.StereoGroupType.STEREO_OR:
                stereo_name = 'Or'
            else:
                raise ValueError(f"Unknown StereoGroupType {stereo_type}.")
            for atom in stereo_grp.GetAtoms():
                atom_idx = atom.GetIdx()
                adv_stereo_by_atom[atom_idx] = {"group_number": group_id, "group_type": stereo_name}
            group_id = group_id + 1

    atom_idx_id = {}
    for idx, atom in enumerate(mol.GetAtoms()):
        object_id = next(object_id_sequence)
        atom_idx_id[idx] = object_id
        p = str(atom_coords[idx][0]) + " " + str(atom_coords[idx][1])
        props = {"p": p, "Z": str(20 + object_id), "Element": str(atom.GetAtomicNum())}

        # hacky handling of Radicals and LonePairs
        # offset values empirically determined - likely to not work for different styles / font sizes
        # Offset values required for BoundingBox for graphics type as else display of graphics is at wrong place
        radical_electrons = atom.GetNumRadicalElectrons()
        if radical_electrons == 1:
            offset_1 = 4.52
            offset_2 = 3.0
            props["Radical"] = "Doublet"
            graphic = ET.SubElement(fragment, "graphic")
            bb_y = round(atom_coords[idx][1] - offset_1, 2)
            graphic.attrib["BoundingBox"] = f"{round(atom_coords[idx][0] + offset_1, 2)} {bb_y} " \
                                            f"{round(atom_coords[idx][0] - offset_2, 2)} {bb_y}"
            graphic.attrib["id"] = str(next(object_id_sequence))
            graphic.attrib["GraphicType"] = "Symbol"
            graphic.attrib["SymbolType"] = "Electron"
            represents = ET.SubElement(graphic, "represent")
            represents.attrib["attribute"] = "Radical"
            represents.attrib["object"] = str(object_id)
        elif radical_electrons == 2:
            offset_1 = 1.87
            offset_2 = 7.87
            props["Radical"] = "Singlet"
            graphic = ET.SubElement(fragment, "graphic")
            bb_y = round(atom_coords[idx][1] - offset_2, 2)
            graphic.attrib["BoundingBox"] = f"{round(atom_coords[idx][0] + offset_1, 2)} {bb_y} " \
                                            f"{round(atom_coords[idx][0] - offset_1, 2)} {bb_y}"
            graphic.attrib["id"] = str(next(object_id_sequence))
            graphic.attrib["GraphicType"] = "Symbol"
            graphic.attrib["SymbolType"] = "LonePair"
            represents = ET.SubElement(graphic, "represent")
            represents.attrib["attribute"] = "Radical"
            represents.attrib["object"] = str(object_id)
        elif radical_electrons == 3:
            # TODO: graphics for ChemDraw
            props["Radical"] = "Triplet"

        if atom.HasProp('_CIPCode'):
            props["AS"] = atom.GetProp('_CIPCode')
        elif atom.HasProp('_ChiralityPossible') and atom.GetProp('_ChiralityPossible') == 1:
            props["AS"] = 'U'
        elif atom.HasProp('_ringStereochemCand') and atom.GetProp('_ringStereochemCand') == 1:
            props["AS"] = 'u'
        else:
            props["AS"] = 'N'

        # Advanced Stereo
        if include_enhanced_stereo:
            atom_idx = atom.GetIdx()
            if atom_idx in adv_stereo_by_atom:
                props["EnhancedStereoType"] = adv_stereo_by_atom[atom_idx]["group_type"]
                props["EnhancedStereoGroupNum"] = str(adv_stereo_by_atom[atom_idx]["group_number"])

        formal_charge = atom.GetFormalCharge()
        if formal_charge != 0:
            props["Charge"] = str(formal_charge)

        if atom.GetIsotope() != 0:
            props["Isotope"] = str(atom.GetIsotope())

        atom_obj = ET.SubElement(fragment, "n")
        atom_obj.attrib['id'] = str(object_id)
        atom_obj.attrib.update(props)

        # text label for Heteroatoms or charged carbons
        if atom.GetAtomicNum() != 6 or formal_charge != 0 or radical_electrons > 0:
            total_hs = atom.GetTotalNumHs()
            atom_obj.attrib["NumHydrogens"] = str(total_hs)
            lbl = atom.GetSymbol()
            # Deuterium
            if lbl == "H" and atom.GetIsotope() == 2:
                lbl = "D"
            if total_hs > 0:
                lbl += "H"
                if total_hs > 1:
                    lbl += str(total_hs)

            if formal_charge > 0:
                if formal_charge == 1:
                    lbl += "+"
                else:
                    lbl += "+" + str(formal_charge)
            elif formal_charge < 0:
                if formal_charge == -1:
                    lbl += "-"
                else:
                    # charge already contains minus symbol no need to add
                    lbl += str(formal_charge)

            cdx_style = CDXFontStyle(int(root.attrib.get('LabelFont', DEFAULT_ATOM_LABEL_FONT_ID)),
                                     int(root.attrib.get('LabelFace', DEFAULT_ATOM_LABEL_FONT_FACE)),
                                     # Font Size in cdx is 1/20ths of a point
                                     int(float(root.attrib.get('LabelSize', DEFAULT_ATOM_LABEL_FONT_SIZE)) * 20),
                                     DEFAULT_ATOM_LABEL_FONT_COLOR)

            cdx_string = CDXString(lbl, style_starts=[0], styles=[cdx_style])

            atm_lbl = ET.SubElement(atom_obj, "t")
            atm_lbl.attrib['id'] = str(next(object_id_sequence))
            atm_lbl = cdx_string.to_element(atm_lbl)
            atom_obj.append(atm_lbl)

    bonds = {}
    for bond in mol.GetBonds():
        object_id = next(object_id_sequence)
        begin_atom_id = atom_idx_id[bond.GetBeginAtomIdx()]
        end_atom_id = atom_idx_id[bond.GetEndAtomIdx()]
        props = {"Z": str(20 + object_id), "B": str(begin_atom_id), "E": str(end_atom_id)}

        bond_type = bond.GetBondType()
        bond_stereo = bond.GetStereo()
        bond_direction = bond.GetBondDir()

        if bond_stereo == rdchem.BondStereo.STEREONONE:
            props["BS"] = "N"
        elif bond_stereo == rdchem.BondStereo.STEREOANY:
            if bond_type == rdchem.BondType.DOUBLE and crossed_bonds:
                # this means crossed double bond aka wavy bond which in chemdraw must be created as below
                props["BS"] = "N"
                props["Display"] = "Wavy"
            else:
                props["BS"] = "U"
        elif bond_stereo == rdchem.BondStereo.STEREOCIS:
            props["BS"] = "Z"
        elif bond_stereo == rdchem.BondStereo.STEREOZ:
            props["BS"] = "Z"
        elif bond_stereo == rdchem.BondStereo.STEREOTRANS:
            props["BS"] = "E"
        elif bond_stereo == rdchem.BondStereo.STEREOE:
            props["BS"] = "E"

        # if bond_type == rdchem.BondType.SINGLE:
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
            # TODO: other dative types
        elif bond_type == rdchem.BondType.UNSPECIFIED and bond.HasQuery():
            qry_smarts = bond.GetSmarts()
            if qry_smarts == "-,=":
                # single or double
                props["Order"] ="1 2"
            elif not qry_smarts:
                # single or aromatic
                props["Order"] = "1 1.5"
            elif qry_smarts == "=,:":
                # single or double
                props["Order"] ="2 1.5"
            elif qry_smarts == "~":
                # Any bond
                props["Order"] ="any"
            else:
                raise ValueError(f"Molecule contains unsupported bond query {qry_smarts}.")


        # Bond Display
        if bond_direction == rdchem.BondDir.BEGINDASH:
            props["Display"] = "WedgedHashBegin"
            #_set_end_wedge_display_style(bonds, bond, "WedgedHashEnd")
        elif bond_direction == rdchem.BondDir.BEGINWEDGE:
            props["Display"] = "WedgeBegin"
            #_set_end_wedge_display_style(bonds, bond, "WedgeEnd")

        if bond.HasProp("_CDXDisplay"):
            props["Display"] = bond.GetProp("_CDXDisplay")

        bond_obj = ET.SubElement(fragment, "b")
        bond_obj.attrib['id'] = str(object_id)
        bond_obj.attrib.update(props)
        bonds[bond.GetIdx()] = bond_obj

    return ChemDrawDocument(cdxml)


def _set_end_wedge_display_style(bonds: dict, wedge_bond: rdchem.Bond, display: str):
    """
    RDKit only defines start of wedge bond. In ChemDraw if the end of the wedge is connected to another bond said other
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
                bond_obj = bonds[b.GetIdx()]
                bond_obj.attrib["Display"] = display
            else:
                b.SetProp("_CDXDisplay", display)


def _get_default_page_properties():
    props = {"BoundingBox": "0 0 540 719.75",
             "HeaderPosition": "36",
             "FooterPosition": "36",
             "PrintTrimMarks": "yes",
             "HeightPages": "1",
             "WidthPages": "1"
             }
    return props


def _get_coordinates(mol: Chem.Mol, conformer: Chem.Conformer, bond_length: float, margin: float):
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
    mean_coords = np.mean(coords, axis=0)
    if mean_coords[2] != 0:
        # 3D coords. convert to 2D
        # AllChem.Compute2DCoords(mol, bondLength=1.5)
        # Use coordgen in case of macrocylces
        rdCoordGen.AddCoords(mol)
        mol.UpdatePropertyCache()
        conformer = mol.GetConformer()
    elif mean_coords[0] == 0 and mean_coords[1] == 0:
        # no coordinates assigned! generate them
        rdCoordGen.AddCoords(mol)
        mol.UpdatePropertyCache()
        conformer = mol.GetConformer()

    bonds = mol.GetBonds()

    if len(bonds) > 0:
        total = 0
        for bond in bonds:

            ai = bond.GetBeginAtomIdx()
            aj = bond.GetEndAtomIdx()
            bl = AllChem.GetBondLength(conformer, ai, aj)
            if not math.isnan(bl):
                total += bl

        avg_bl = (total / len(bonds))
    else:
        # Molecules like simple salt (NaCl) with zero bonds
        # Use a default bond length / scaling
        # Could be improved as distance between atom is not exactly the same with this vs opening mol file in ChemDraw
        avg_bl = DEFAULT_AVG_BOND_LENGTH

    if avg_bl > 0.0:
        # scale
        bl_ratio = bond_length / avg_bl
        coords = conformer.GetPositions()
        c_scaled = coords * bl_ratio
        # make 2 D
        c_scaled = np.delete(c_scaled, 2, 1)
        # flip vertically - coordinates form rdkit/molfile have negative y when going "down" in terms of the screen
        # In ChemDraw the further down, the higher the y coordinate with origin in top-left (only y coordinate flipped)
        c_scaled = c_scaled * [[1,-1]]
        # transform
        cmin = np.amin(c_scaled, axis=0)
        tx = margin * CM_TO_POINTS - cmin[0]
        ty = margin * CM_TO_POINTS - cmin[1]
        t = np.array([tx, ty])
        coords_trans = c_scaled + t
        return np.around(coords_trans, decimals=2)
    else:
        raise ValueError("Average Bond Length is 0 or negative.")
