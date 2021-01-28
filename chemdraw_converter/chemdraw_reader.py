import io
from .chemdraw_objects import *
from base64 import b64decode


class CDXReader(object):

    def read(self, cdx_file):
        """

        :param cdx_file: a file-like object or path (str) to a cdx file
        """
        if isinstance(cdx_file, str):
            with open(cdx_file, mode='rb') as file:
                cdx = file.read()
            self.cdx = io.BytesIO(cdx)
        elif isinstance(cdx_file, io.BytesIO):
            self.cdx = cdx_file
        else:
            # assume opened file-handle
            cdx = cdx_file.read()
            cdx = io.BytesIO(cdx)

        document = ChemDrawDocument.from_bytes(cdx)
        return document


class B64CDXReader(object):

    def read(self, base64_cdx):

        cdx = io.BytesIO(b64decode(base64_cdx))
        document = ChemDrawDocument.from_bytes(cdx)

        return document


class CDXMLReader(object):

    def read(self, cdxml_file):
        """

        :param cdxml_file: a file object, a path (str) to a cdxml file or a string containing the xml
        """
        if isinstance(cdxml_file, str):
            if cdxml_file.startswith("<?xml"):
                cdxml = cdxml_file
            else:
                with open(cdxml_file, mode='r') as file:
                    cdxml = file.read()
        else:
            # assume opened file-handle
            cdxml = cdxml_file.read()

        document = ChemDrawDocument.from_cdxml(cdxml)
        return document