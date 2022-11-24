# CDXML Converter

## Scope

CDXML converter **converts between cdx** (binary) **and cdxml**(text/xml) files. As of commit 9507e48 all files in the ChemDraw Samples directory can be visually correctly converted from/to cdxml. This includes correct conversion of biological shapes and sequences, images and shapes.

 **Conversion from [RDKit](https://github.com/rdkit/rdkit) molecules to cdx/cdxml is also partially implemented**. The goal of the project is to provide conversion for files containing small molecules and later possibly reactions, at least the reaction scheme. The idea is to be able to convert such files coming or going into a database automatically on any OS and hence treating them as molecule file format. ChemDraw itself lacks such usable automation features, especially cross-platform. 

Newer feature like additions to biology drawing elements or 3D chemical features will possibly only get limited support because they are missing from the specification which requires a lot of trial and error to figure things out. The core issue for full support is that ChemDraw is essentially a drawing canvas and hence cdx and cdxml are drawing formats and not really chemical structure exchange formats.

Note that there is no chemical knowledge in this tool! It really is just a format converter.

## Status

The **status of the project is "beta"**. It has to be assumed that anything that isn't a basic small molecules can either fail or even worse lead to an invalid output without error. 

What its implemented:

- Conversion to/from cdx to/from cdxml working for all Sample files
- Conversion from simple RDKit Mols to cdx/cdxml including enhanced stereochemistry

## ChemDraw Format Specification

#### Issues

The [official specification](https://www.cambridgesoft.com/services/documentation/sdk/chemdraw/cdx/General.htm) is very much outdated. It's contradicts itself in some places any many properties and objects are outright missing or seem to have changed their type. Some of this issues have been solved simply by changing the type or by trial and error if it is simple enough.

There is an [updated header file](http://forums.cambridgesoft.com/messageview.aspx?catid=12&threadid=3822) on old CambridgeSoft forums but it doesn't explain the type or usage of new object or properties so it's of limited value.

A much bigger issue are inconsistent data types. By creating trivial test files I found that properties `color(UNINT16) `and `BracketUsage (INT8)` can appear with wrong number of bytes in the cdx file (4 and 2). These additional bytes are 0 and it's unclear what they are for. Removing the 0-bytes from color leads to a file that looks exactly the same in ChemDraw UI. Hence their reason to exist is unclear.

The biggest limitation is that very old cdx files (pre ChemDraw 8) do not adhere to the official cdx specification and can hence in many cases not be interpreted.

#### CDX vs CDXML

cdx format internal is a tree-structure just like xml is. However some objects are implemented differently. For example font- and colortables are attributes in cdx file while they are separate elements in cdxml. For text the text style is an attribute in cdx but in cdxml each style is a separate element. The point being that there is no simple 1:1 mapping possible. This leads to ugly "hacks" and conditionals needed at the right places.

Another such example is the bond order which in cdx is an INT16 (Enum) but the values it takes are not very logical outside of single (=1) and double bonds (=2). Triple bonds are then 4, Quadruple 8 and so forth. In CDXML the actual value is used, eg. 3 for triple bonds or 5.5 for FiveAndAHalf bonds. However in a python enum 5.5 or "5.5" are invalid as value name. Hence writing out the cdxml value requires a large if-block.

## Architecture / Code

Let's just say it's a big mess also driven by the format issues and there is a lot of room for improvement. I started the project by being able to import cdx and then write it out as 100% equal on byte level again. As a way to better learn working with binary data and files. Hence the internal representation was originally based on the cdx specifications and not the cdxml one. The code was then updated to get rid of the internal format and simply use cdxml representation (lxml ElementTree) as the internal format. This also lead to very siginficant performance increase (still slow, roughly 1.5ms per molecule).

#### High-level

The internal architecture consist of `ChemDrawDocument`class which wraps an `ElementTree`. This element tree is a `cdxml` document. Each element has attributes and a value where the values have types defined in the cdx specification. For reach type their is a class that knows how to represent itself either as `bytes`as in `cdx` or as string value in `cdxml`.

In `cdx` elements (tree nodes) are called objects and attributes are called properties.

#### Reading / Writing

Ignoring some exceptions, the types know how to read and write themselves. In `cdx` each object has a tag id of 2 bytes. `cdx_objects.yml` maps the tag to the object name and element tag in cdxml. Like objects, properties have a tag id of 2 bytes. `cdx_properties.yml` maps this tag id to the properties name and it's type. So if new objects and properties are found in the specification or by reverse-engineering,  they can be added to these files. If the property is of an already existing type, only the yml file must be updated and no code change is needed. So theoretically up to a certain degree a user can add new features himself.

Enum types of INT8, INT16 or INT32 are implemented as separate type and not as number. So for each enum a type exists.

When reading / writing a file, the two above mention config files are used to figure out what type to use and then a type instance is created which knows how to read/write itself.

`cdxml`is read as is. No input validation is performed if the file or molecules contained are valid. `cdx` upon reading is converted to internal cdxml representation. On writing cdxml, the `ElementTree` is simply converted to a string, on writing `cdx` the `cdxml` is converted to `cdx`. Reading and then writing `cdx` therefore means 2 conversions will happen.

The issues with this basic read/write mechanism is, that the reading and writing can all work without error but the resulting file might still not be readable by ChemDraw either due to a error in the code or an unknown object or property. Currently unknown elements simply get ignored (and logged).

It also means that every type has an `CDXType` implementation even INT8, INT16 etc. which is a bit ugly really but it "unifies" the design. Again there is room for improvement, simplification and better performance.

In terms of logging please be advised that the debug level should only ever be used in case of troubleshooting a specific file. It is very verbose which makes things slow and generates huge log files.