# ChemDraw Tools

`chemdraw-tools` package contains several modules to support working with `cdxml`and `cdx`file formats used by ChemDraw in an automated, platform-independent way. Eg. the package works without needing to have ChemDraw installed and also on non-windows systems (untested but no reason it should not work, pure python).

All modules have to be asumed to be at best in a beta-stage and they only work with a subset of the ChemDraw features. In fact it's best to limit usage to "single-molecule" documents essentially treating the ChemDraw files like mol files. `cdxml`and `cdx` are more like a drawing file format with molecules as first class citizens and not a pure chemical format. Using any of these "advanced features" can lead to errors or worse silent issues. You have been warned!

## ChemDraw Converter

`chemdraw_converter`module allows you to convert between `cdxml`and `cdx` files. Reading in a cdx and writing it out again will lead to a 100% identical file on binary level (if onyl supported features are used). 

There is also experimental support to convert [RDKit](https://github.com/rdkit/rdkit) molecules to ChemDraw files.

The conversion are based on PerkinElmers (formerly CambridgeSofts) official but very much outdated format specification available [here](https://www.cambridgesoft.com/services/documentation/sdk/chemdraw/cdx/IntroCDX.htm). Some features required some "reverse engineering". For more details see the README.md in the modules directory.

## CDXMLStyler

`cdxml_styler` module converts the style of the molecules contained in the `cdxml`document. The style options are limited to options that directly affect the display of the molecule like bond length, atom label size and so forth. The core usage scenario here is to convert a bunch of `cdxml`documents containing just molecule drawings to a standarized style.

If you have `cdx`files, convert them to `cdxml`with the `chemdraw_converter`module, apply the style and convert back to `cdx`. That is in general the basic idea of this package. Do all manipulation in `cdxml`because due to it being `xml`it's relativley easy to do such manipulations in contrast to the binary `cdx`format.

For more details see the README.md in the modules directory.

## CDXML Slide Generator

`cdxml_slide_generator` module does a similar thing as my [`molecule-slide-generator`](https://github.com/kienerj/molecule-slide-generator)package but with a `cdxml`file as output. In essence the passed-in molecules and their properties are put into a single `cdxml`file nicley aligned with the properties as text below them. Properties can be anything of your choice like an activity value or simply a name or compound id.

For more details see the README.md in the modules directory.