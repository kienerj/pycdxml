import os
import unittest
from pycdxml import cdxml_converter
import rdkit
from rdkit import Chem
import filecmp
from pathlib import Path
import logging

logger = logging.getLogger('pycdxml.chemdraw_objects')
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


class CdxmlConverterTest(unittest.TestCase):
    """
    Test if conversions match expected outcome
    """

    def test_cdx_to_cdx(self):
        """
        Test if reading in a cdx file and writing it out again leads to an equal file on binary level
        """
        doc = cdxml_converter.read_cdx(self.standard_in_cdx)
        self.assertIsNotNone(doc, "Document was unexpectedly 'None'.")
        cdxml_converter.write_cdx_file(doc, self.standard_out_cdx)
        self.assertTrue(filecmp.cmp(self.standard_in_cdx, self.standard_out_cdx, shallow=False),
                        "Generated cdx file does not match input.")

    # def test_cdxml_to_cdx(self):
    #     """
    #     Test if reading in a cdxml file and writing it out again leads to the expected result
    #     """
    #     doc = cdxml_converter.read_cdxml(self.standard_in_cdxml)
    #     self.assertIsNotNone(doc, "Document was unexpectedly 'None'.")
    #     cdxml_converter.write_cdx_file(doc, self.standard_out_cdx)
    #     self.assertTrue(filecmp.cmp('files/result_cdxml_to_cdx.cdx', self.standard_out_cdx, shallow=False),
    #                     "Generated cdx file does not match expected output.")

    def test_cdx_to_cdxml(self):
        """
        Test if reading in a cdxml file and writing it out again leads to the expected result
        """
        doc = cdxml_converter.read_cdx(self.standard_in_cdx)
        self.assertIsNotNone(doc, "Document was unexpectedly 'None'.")
        cdxml_converter.write_cdxml_file(doc, self.standard_out_cdxml)
        self.assertTrue(filecmp.cmp('tests/files/result_cdx_to_cdxml.cdxml', self.standard_out_cdxml, shallow=False),
                        "Generated cdxml file does not match expected output.")

    def test_cdxml_to_b64(self):
        """
        Test conversion from cdxml to base64-encoded cdx string
        """

        doc = cdxml_converter.read_cdxml(self.standard_in_cdxml)
        self.assertIsNotNone(doc, "Document was unexpectedly 'None'.")
        b64 = cdxml_converter.to_b64_cdx(doc)
        with open('tests/files/standard_b64.txt') as f:
            b64_reference = f.readline()
        self.assertEqual(b64_reference, b64, "Generated base64 string does not match expected output.")

    def test_salt_conversions(self):
        """
        Test conversion of a salt (magnesium citrate) from/to cdx and cdxml
        """

        doc = cdxml_converter.read_cdx(self.salt_in_cdx)
        self.assertIsNotNone(doc, "Document was unexpectedly 'None'.")
        cdxml_converter.write_cdx_file(doc, self.salt_out_cdx)
        self.assertTrue(filecmp.cmp(self.salt_in_cdx, self.salt_out_cdx, shallow=False),
                        "Generated cdx file for salt does not match input.")
        cdxml_converter.write_cdxml_file(doc, self.salt_out_cdxml)
        self.assertTrue(filecmp.cmp('tests/files/salt_reference.cdxml', self.salt_out_cdxml, shallow=False),
                        "Generated cdxml file for salt does not match expected output.")

        doc = cdxml_converter.read_cdxml(self.salt_in_cdxml)
        self.assertIsNotNone(doc, "Document was unexpectedly 'None'.")
        cdxml_converter.write_cdx_file(doc, self.salt_out_cdx)
        self.assertTrue(filecmp.cmp('tests/files/salt_reference.cdx', self.salt_out_cdx, shallow=False),
                        "Generated cdx file for salt does not match input.")

    def test_embedded_image(self):
        """
        test conversion of a compressed embedded image
        """
        doc = cdxml_converter.read_cdx(self.embedded_cdx)
        self.assertIsNotNone(doc, "Document was unexpectedly 'None'.")
        cdxml_converter.write_cdxml_file(doc, self.embedded_out)
        self.assertTrue(filecmp.cmp(self.embedded_out, 'tests/files/embedded_reference.cdxml', shallow=False),
                        "Generated cdxml file for embedded image test does not match expected output.")

    def test_represents_to_cdx(self):
        """
        test conversion of a file containing a salt causing an exception prior to fix
        """
        doc = cdxml_converter.read_cdxml('tests/files/represents.cdxml')
        self.assertIsNotNone(doc, "Document was unexpectedly 'None'.")
        b64cdx = cdxml_converter.to_b64_cdx(doc)
        with open('tests/files/represents_b64cdx.txt') as f:
            b64ref = f.read()
            self.assertEqual(b64cdx, b64ref, "Generated b64cdx file for represents test does not match expected output.")

    def setUp(self):
        self.standard_in_cdx = 'tests/files/standard_test.cdx'
        self.standard_out_cdx = 'tests/files/standard_test_out.cdx'
        self.standard_in_cdxml = 'tests/files/standard_test.cdxml'
        self.standard_out_cdxml = 'tests/files/standard_test_out.cdxml'
        self.salt_in_cdx = 'tests/files/magnesium_citrate.cdx'
        self.salt_in_cdxml = 'tests/files/magnesium_citrate.cdxml'
        self.salt_out_cdx = 'tests/files/magnesium_citrate_out.cdx'
        self.salt_out_cdxml = 'tests/files/magnesium_citrate_out.cdxml'
        self.embedded_cdx = 'tests/files/embedded_image_test.cdx'
        self.embedded_out = 'tests/files/embedded_out.cdxml'

    def tearDown(self):
        # Delete all files generated by tests
        for p in Path("files").glob("*_out.*"):
            p.unlink()


class CdxmlConverterRoundTripTests(unittest.TestCase):
    def roundtrip(self, fname):
        """
        Roundtrip from rdkit back to rdkit via MOL to CDXML to CANSMI
        - Assert that the CANSMI from the CDXML is equal to that from the MOL
        """
        mol = Chem.MolFromMolFile(fname)
        cansmi = Chem.MolToSmiles(mol)
        doc = cdxml_converter.mol_to_document(mol, crossed_bonds=True)
        cdxml = doc.to_cdxml()
        nmols = Chem.MolsFromCDXML(cdxml)
        self.assertEqual(1, len(nmols))
        nmol = nmols[0]
        ncansmi = Chem.MolToSmiles(nmol)
        self.assertEqual(ncansmi, cansmi)

    def test_implicit_Hs(self):
        """
        Test that implicit Hs on heteroatoms can be roundtripped  
        """
        fname = os.path.join("tests/files", "CHEMBL6509.impl_H_on_heteroatom.mol")
        self.roundtrip(fname)

    def test_isotope(self):
        """
        Test that an isotopically labelled MOL file can be roundtripped
        """
        fname = os.path.join('tests/files', 'CHEMBL595085.isotope_test.mol')
        self.roundtrip(fname)

    def test_dbl_bond_unknown_stereo(self):
        """
        Test that a dbl bond marked in MOL file as unknown stereo ('3') can be roundtripped
        Note: I assume that https://github.com/rdkit/rdkit/issues/5752 is fixed in the next
              release of RDKit.
        """
        fname = os.path.join('tests/files', 'CHEMBL4303146.dbl_bond_unknown_stereo.mol')
        if rdkit.__version__ > "2022.09.1":
            self.roundtrip(fname)

    def test_molecule_without_bonds(self):
        """
        Test that a molecule without bonds (salt) can be roundtripped
        """
        fname = os.path.join('tests/files', 'CHEMBL69710.no_bonds.mol')
        self.roundtrip(fname)

    def test_radical(self):
        """
        Test that a molecule without bonds (salt) can be roundtripped
        """
        fname = os.path.join('tests/files', 'Aminopropyl_radical.mol')
        self.roundtrip(fname)

    def test_lone_pair(self):
        """
        Test that a molecule without bonds (salt) can be roundtripped
        """
        fname = os.path.join('tests/files', 'Aminopropyl_LonePair.mol')
        self.roundtrip(fname)

    def test_3d_coords(self):
        """
        Test that a molecule that has z-coordintes set to -0.0000 (eg. with the minus) do not trigger a 2D coordinates
        generation.
        """
        fname = os.path.join('tests/files', 'CHEMBL4889297_coords.mol')
        self.roundtrip(fname)


if __name__ == '__main__':
    unittest.main()
