import unittest
from pycdxml import cdxml_converter
from rdkit import Chem
import filecmp
import os


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

    def test_cdxml_to_cdx(self):
        """
        Test if reading in a cdxml file and writing it out again leads to the expected result
        """
        doc = cdxml_converter.read_cdxml(self.standard_in_cdxml)
        self.assertIsNotNone(doc, "Document was unexpectedly 'None'.")
        cdxml_converter.write_cdx_file(doc, self.standard_out_cdx)
        self.assertTrue(filecmp.cmp('files/result_cdxml_to_cdx.cdx', self.standard_out_cdx, shallow=False),
                        "Generated cdx file does not match input.")

    def setUp(self):
        self.standard_in_cdx = 'files/standard_test.cdx'
        self.standard_out_cdx = 'files/standard_test_out.cdx'
        self.standard_in_cdxml = 'files/standard_test.cdxml'

    def tearDown(self):
        try:
            os.remove(self.standard_out_cdx)
        except FileNotFoundError:
            pass

if __name__ == '__main__':
    unittest.main()
