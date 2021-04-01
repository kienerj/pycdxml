<<<<<<< HEAD
# ChemDraw Tools

`chemdraw-tools` package contains several modules to support working with `cdxml`and `cdx`file formats used by ChemDraw in an automated, platform-independent way. Eg. the package works without needing to have ChemDraw installed and also on non-windows systems (untested but no reason it should not work, pure python).

All modules have to be asumed to be at best in a beta-stage and they only work with a subset of the ChemDraw features. In fact it's best to limit usage to "single-molecule" documents essentially treating the ChemDraw files like mol files. `cdxml`and `cdx` are more like a drawing file format with molecules as first class citizens and not a pure chemical format. Using any of these "advanced features" can lead to errors or worse silent issues. You have been warned!

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
=======
# ChemDraw Converter

## Scope

ChemDraw converter **converts between cdx** (binary) **and cdxml**(text/xml) files containing **small molecules**. **Conversion from/to [RDKit](https://github.com/rdkit/rdkit) molecules is also planned**. The goal of the project is to provide conversion for files containing small molecules and later possibly reactions, at least the reaction scheme. The idea is to be able to convert such files coming or going into a database automatically on any OS and hence treating them as molecule file format. ChemDraw itself lacks such usable automation features, especially cross-platform.

Biologics are out of scope especially because these are rather new and missing from specification. Out-of-scope are also many other drawing-related things one can to in ChemDraw. The core issue is that ChemDraw is essentially a drawing canvas and hence cdx and cdxml are drawing formats and not chemical structure exchange formats.

Note that there is no chemical knowledge in this tool! It really is just a format converter.

## Status

The **status of the project is at best "alpha"** simply due to the limited scope of tested molecules for now. It has to be assumed that anything that isn't a basic small molecules will probably either fail or more likely lead to an invalid output. (Please don't look at the code, it's honestly a mess. More on that later)

What its implemented:

- Conversion to/from cdx to/from cdxml for small molecules and simple reactions
- Conversion from RDKit Mol to cdx/cdxml

Reading in a cdx file and converting back to cdx leads to a 100% identical file on binary level (for files tested ;))

For cdxml this round-triping doesn't work as it would require the xml output to have the attributes order like ChemDraw does and more importantly format the xml (text file) in exactly the same way. However the content leads to the same visual display inside ChemDraw.

One can also convert simple and small RDKit Mol instances into the internal representation which can then either be converted to cdx or cdxml.

## ChemDraw Format Specification

#### Issues

The [official specification](https://www.cambridgesoft.com/services/documentation/sdk/chemdraw/cdx/General.htm) is very much outdated. It's contradicts itself in some places any many properties and objects are outright missing or seem to have changed their type. Some of this issues have been solved simply by changing the type or reverse-engineering the property if it is simple enough.

There is an [updated header file](http://forums.cambridgesoft.com/messageview.aspx?catid=12&threadid=3822) on old CambridgeSoft forums but it doesn't explain the type or usage of new object or properties so it's of limited value.

A much bigger issue are inconsistent data types. By creating trivial test files I found that properties `color(UNINT16) `and `BracketUsage (INT8)` can appear with wrong number of bytes in the cdx file (4 and 2). These additional bytes are 0 and it's unclear what they are for. Removing the 0-bytes from color leads to a file that looks exactly the same in ChemDraw UI. The code now keeps these bytes in mind and writes them out again to create a 100% identical cdx on binary level. On cdxml these additional bytes do not appear. Hence their reason to exist is unclear.

#### CDX vs CDXML

cdx format internal is a tree-structure just like xml is. However some objects are implemented differently. For example font- and colortables are properties in cdx file they are separate objects in cdxml. For text the text style is a property in cdx but in cdxml each style is a separate object. The point being that there is no simple 1:1 mapping possible. This leads to ugly "hacks" and conditionals needed at the right places.

Another such example is the bond order which in cdx is an INT16 (Enum) but the values it takes are not very logical outside of single (=1) and double bonds (=2). Triple bonds are then 4, Quadruple 8 and so forth. In CDXML the actual value is used, eg. 3 for triple bonds or 5.5 for FiveAndAHalf bonds. However in a python enum 5.5 or "5.5" are invalid as value name. Hence writng out the cdxml value requires a large if-block.

## Architecture / Code

Let's just say it's a big mess also driven by the format isses and there is a lot of room for improvement. I started the project by being able to import cdx and then write it out as 100% equal on byte level again. Hence the internal representation is based on the cdx specifications and not the cdxml one. Therefor when reading cdxml, a conversion to internal format must happen and same when writing cdxml.

#### High-level

The high-level architecture is the same as in the cdx specification. A file consists of objects. Objects have properties (or attributes in cdxml) and every attribute is of a certain type. A type can be complex or just a standard numeric type like int16. 

`CDXObject` -> `CDXProperty` -> `CDXType`

The internal tree-structure is built using `anytree` library. 

#### Reading / Writing

Ignoring some exceptions, the types know how to read and write themselves. In cdx each object has it's tag id of 2 bytes. `cdx_objects.yml` maps the tag to the object name and element tag in cdxml. The object then reads all it's properties. Like objects, properties have a tag id of 2 bytes. `cdx_properties.yml` maps this tag id to the properties name and it's type. So if new objects and properties are found in the specification or by reverse-engineering,  they can be added to these files.

Enum types of INT8, INT16 or INT32 are implemented as separate type and not as number. So for each enum a type exists.

The property then determines it's type and the type object then reads in the data from the file or when writing generates the output data either by appending to a byte stream or by adding attributes to an lxml element object. 

The issues with this basic read/write mechanism is, that the reading and writing can all work without error but the resulting file might still not be readable by ChemDraw either due to a error in the code or an unknown object or property. Currently unknown elements simply get ignored (and logged).

It also means that every type has an `CDXType` implemention even INT8, INT16 etc which is a bit ugly really but it "unifies" the design. Again there is room for improvement and simplification.
>>>>>>> chemdraw_converter/master
