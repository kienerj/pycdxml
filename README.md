## ChemDraw Converter

Converts between cdx and cdxml files. The goal of the project is to provide conversion for files containing small molecules and later reactions. "Biologics" are out of scope especially because these are rather new and missing from specification.

### ChemDraw Format Specification

#### Issues

The [official specification](https://www.cambridgesoft.com/services/documentation/sdk/chemdraw/cdx/General.htm) is very much outdated. It's contradicts itself in some places any many properties and objects are outright missing or seem to have changed their type. Some of this issues have been solved simply by changing the type or reverse-engineering the property if it is simple enough.

There is an [updated header file](http://forums.cambridgesoft.com/messageview.aspx?catid=12&threadid=3822) on old CambridgeSoft forums but it doesn't explain the type or usage of new object or properties so it's of limited value.

A much bigger issue are inconsistent data types. By creating trivial test files I found that properties `color(UNINT16) `and `BracketUsage (INT8)` can appear with wrong number of bytes in the cdx file (4 and 2). These additional bytes are 0 and it's unclear what they are for. Removing the 0-bytes from color leads to a file that looks exactly the same in ChemDraw UI. The code now keeps these bytes in mind and writes them out again to create a 100% identical cdx on binary level. On cdxml these additional bytes do not appear. Hence there reason to exist is unclear.



