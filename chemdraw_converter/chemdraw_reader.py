import io
from .chemdraw_objects import *
import yaml
from pathlib import Path

class CDXReader(object):

    def __init__(self, cdx_file):
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
            self.cdx = io.BytesIO(cdx)

        if not self.cdx.read(8).decode("ascii") == 'VjCD0100':
            raise ValueError('File is not a valid cdx file')

        module_path = Path(__file__).parent
        cdx_objects_path = module_path / 'cdx_objects.yml'
        with open(cdx_objects_path, 'r') as stream:
            self.cdx_objects = yaml.safe_load(stream)


    def read(self):

        # check if valid file
        header = self.cdx.read(22)
        if header != ChemDrawDocument.HEADER:
            raise ValueError('File is not a valid cdx file. Invalid header found.')
        document_tag = self.cdx.read(2)
        if document_tag != b'\x00\x80':
            raise ValueError('File is not a valid cdx file. Document tag not found.')

        object_tag = int.from_bytes(self.cdx.read(2), "little")
        class_name = self.cdx_objects[object_tag]
        klass = globals()[class_name]
        obj = klass.from_bytes(self.cdx)

        return 0
