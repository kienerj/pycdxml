## CDXMLSlideGenerator

`cdxml_slide_generator` module does a similar thing as my [`molecule-slide-generator`](https://github.com/kienerj/molecule-slide-generator)package but with a `cdxml`file as output. In essence the passed-in molecules and their properties are put into a single `cdxml`file nicely aligned with the properties as text below them. Properties can be anything of your choice like an activity value or simply a name or compound id. Internally `cdxml_slide_generator` makes use of `cdxml_Styler` module to convert input molecules to the same style.

The generated `cdxml`files can then be used in presentations, reports or other documents with ChemDraws MS Office integration. The naming of the module might be misleading. Only a cdxml file is generated and the adding to MS Office must be done manually.

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

Only fragment objects of the input are used. If the input contains any additional drawing elements for example brackets, they will not be visible in the output.

`CDXMLSlideGenerator` takes all the fragments in the file, groups them and adds the group to the slide. If the document contains many molecules, they will become tiny to fit the assigned grid position. Taking all fragments is needed so that it works for salts but the convention is the input documents should contain single-molecules only.

