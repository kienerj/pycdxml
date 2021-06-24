# CDXMLStyler

## Introduction

CDXMLStyler is a module to programmatically adjust the style of all the molecules contained in a `cdxml` file to the desired ChemDraw style. The style changes are limited to what affects the display of small molecules like bond length or atom label font size.

`cdxml` is the xml-based format of ChemDraw. This style-conversion can be achieved with ChemDraw itself but not in an automated fashion. Therefore the main purpose of the tool is batch conversion of  multiple`cdxml` files to the same style either for normalization in a database or for usage in the same ChemDraw file (see also CDXML Slide Generator module).

## Usage

`CDXMLStyler`class can be instantiated either by an included named style ( currently limited to ACS 1996 or Wiley), a template `cdxml`file or from a `dict` containing the required style options.

Named Style:

```python
styler = CDXMLStyler(style_name="ACS 1996")
cdxml_normalized = self.styler.apply_style_to_string(cdxml)
```
Currently only ACS 1996 and Wiley styles are supported.

From `cdxml` template:

```python
styler = CDXMLStyler(style_source="path/to/style.cdxml")
cdxml_normalized = self.styler.apply_style_to_string(cdxml)
```

From a `dict`:

```python
styler = CDXMLStyler(style_dict=style_dict)
cdxml_normalized = self.styler.apply_style_to_string(cdxml)
```

The required style options for using a `dict`input are:

- `BondSpacing`
- `BondLength`
- `BoldWidth`
- `LineWidth`
- `MarginWidth`
- `HashSpacing`
- `CaptionSize`
- `LabelSize`
- `LabelFace`
- `LabelFont`
- `HideImplicitHydrogens`

Note that `LabelFont`is an index (integer) to the according font in the font table. So the actual font used will depend on the input documents font table<sup>1</sup>. `HideImplicitHydrogens`is relevant because some styles have it set to `yes` meaning that say an alcohol is displayed as `O` and not `OH`.  Therefore when this setting changes from old to new style, the atom label needs to be adjusted accordingly.



<sup>1</sup>Actually this should probably be improved so that a font name can be used and if not present it's added to the font table. Currently if style source is a `cdxml`file the `LabelFont` index is taken and applied to the source document. If the source has a different font at that index in the font table, then the output is wrong.