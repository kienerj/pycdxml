# PyCDXML

`pycdxml` package contains several modules to support working with `cdxml`and `cdx`file formats used by ChemDraw in an automated, platform-independent way. Eg. the package works without needing to have ChemDraw installed and also on non-windows systems (untested but no reason it should not work, pure python).

Initially conceived as 3 separate projects / packages they were converted to a single project / git repository to simplify their management and because they partially depend on each other anyway. 

For example a hypothetical usage scenario is to convert an RDKit molecules to `cdxml`, apply the desired ChemDraw Style to all of them and generate a `cdxml`file contain them all nicely aligned. If needed this `cdxml`file can then be converted to a binary `cdx`file or base64-encoded `cdx` string. The `cdxml`or `cdx` file would then be a normal ChemDraw document that could then be opened in ChemDraw and adjusted by the end-user (chemist) to their needs.

## Project Status

The overall status of the project can be described best as **alpha**. It somewhat depends on the specific module used and how you use it. Within the limited scope of basic small molecules, the code will mostly work. Of course I'm sure there are some unknown bugs and edge-cases not present in my set of test molecules but staying in that scope, any you will probably be fine.

Where you might run into issues is with more complex salts, reactions and for sure organometallics or anything that contains non-chemical related drawings.

It's best to limit usage to "single-molecule" documents essentially treating the ChemDraw files like mol files. `cdxml`and `cdx` are more like a drawing file format with molecules as first class citizens and not a pure chemical format. Using any of these "drawing features" can lead to errors or worse silent issues. **You have been warned!**

## CDXML Converter

`cdxml_converter`module allows you to convert between `cdxml`and `cdx` files. Reading in a cdx into the internal representation and writing it out again will lead to a 100% identical file on binary level (if only supported features are used). 

There is also experimental support to convert [RDKit](https://github.com/rdkit/rdkit) molecules to `cdxml` or `cdx` files.

The conversions are based on PerkinElmers (formerly CambridgeSofts) official but very much outdated format specification available [here](https://www.cambridgesoft.com/services/documentation/sdk/chemdraw/cdx/IntroCDX.htm). Some features required some "reverse engineering" as they are either new or different from the specification. For more details see the README.md in the modules directory.

## CDXMLStyler

`cdxml_styler` module converts the style of the molecules contained in the `cdxml`document. The style options are limited to options that directly affect the display of the molecule like bond length, atom label size and so forth. The core usage scenario here is to convert a bunch of `cdxml`documents containing just molecule drawings to a standardized style.

If you have `cdx`files, convert them to `cdxml`with the `cdxml_converter`module, apply the style and convert back to `cdx`. That is in general the basic idea of this package. Do all manipulation in `cdxml`because due to it being `xml`it's relatively easy to do such manipulations in contrast to the binary `cdx`format.

## CDXML Slide Generator

`cdxml_slide_generator` module does a similar thing as my [`molecule-slide-generator`](https://github.com/kienerj/molecule-slide-generator)package but with a `cdxml`file as output. In essence the passed-in molecules and their properties are put into a single `cdxml`file nicely aligned with the properties as text below them. Properties can be anything of your choice like an activity value or simply a name or compound id. Internally `cdxml_slide_generator` makes use of `cdxml_Styler` module to convert input molecules to the same style.

As additional note ChemDraw calls properties "Annotations".  The text below the molecules is just text and has no further meaning to ChemDraw. If you work inside ChemDraw and want properties to be exported into an sd-file, you need to annotate each molecule with the according values. However `cdxml_slide_generator` has you covered with this as well. All molecules are already annotated. If you save the `cdxml` file inside ChemDraw as sd-file, all the visible properties will also appear in the sd-file.

## Contribute

Please absolutely do. Just reporting issues will already help and in that case please include the affected file(s). 

### Add Tests

An important help would also be adding more and better tests. Ultimately the different modules generate new files which must somehow be validated. Currently I'm just comparing to a reference file which itself was created by these modules but visually inspected to be correct. Issues is small changes can lead to test failures and the need to regenerate and inspect the reference files. The hence testing is not very automatic at all.

## Miscellaneous

### License

I've used the GPLv3 because this project should be a pre-competitive community effort to make certain internal workflows easier to handle. The GPLv3 entirely permits you to create an internal or personal tool without needing to share your source code. What you can't do is add it you your commercial software, sell it and not share the full source code.

### Chemical Intelligence

Note that this packages doesn't really contain much if any "Chemical Intelligence". Changes happen on "file level" according to file specifications and not "chemical intelligence". So there is no error detection of faulty molecules or such things.