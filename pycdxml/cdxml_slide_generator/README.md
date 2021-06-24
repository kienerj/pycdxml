## CDXMLSlideGenerator

`cdxml_slide_generator` module does a similar thing as my [`molecule-slide-generator`](https://github.com/kienerj/molecule-slide-generator)package but with a `cdxml`file as output. In essence the passed-in molecules and their properties are put into a single `cdxml`file nicely aligned with the properties as text below them. Properties can be anything of your choice like an activity value or simply a name or compound id. Internally `cdxml_slide_generator` makes use of `cdxml_Styler` module to convert input molecules to the same style.

The generated `cdxml`files can then be used in presentations, reports or other documents with ChemDraws MS Office integration.

As additional note ChemDraw calls properties "Annotations".  The text below the molecules is just text and has no further meaning to ChemDraw. If you work inside ChemDraw and want properties to be exported into an sd-file, you need to annotate each molecule with the according values. However `cdxml_slide_generator` has you covered with this as well. All molecules are already annotated. If you save the `cdxml` file inside ChemDraw as sd-file, all the visible properties will also appear in the sd-file. 

I consider this very important from a knowledge management standpoint. if at any point in the future someone needs access to the data, it makes it relatively easy to get the ChemDraw file out of say a PowerPoint and export the molecules and properties to an sd-file which can then be used for further processing the data.

### Usage

```python
# docs => list of cdxml strings, props => list of lists of TextProperty
docs = [cdxml]
props1 = [TextProperty('Compound ID', 'ABC-0001', color='#3f6eba'), 
          TextProperty('Activity', 6.5, show_name=True)]
props = [props1]
sg = CDXMLSlideGenerator(style="ACS 1996", number_of_properties=2)
slide = sg.generate_slide(docs, props)
```

## Known Issues

A big caveat currently is, that this doesn't work with salts or any other "multi-fragment" chemical structure. A molecule inside ChemDraw is represented as a `fragment` object. So in a salt, there are at least 2 such `fragments`. If they are drawn by hand and not grouped, there is no way to know which fragments belong to each other. If you create a salt by Name2Structure, then it is grouped correctly. Note: Grouping is currently also not taken into account.

Currently `CDXMLSlideGenerator` just takes the first fragment in the file and adds that to the slide. Another option could be to take all fragments and if there are too many you will simply get a very tiny view of these molecules.

