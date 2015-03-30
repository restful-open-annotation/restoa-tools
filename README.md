# restoa-tools
Tools for working with RESTful Open Annotations

## tagtog

[tagtog.net](http://tagtog.net) is a document visualization and annotation web tool. Example support for OA:

* visualize document: https://www.tagtog.net/-demo?docid=a7zefU6irg815RNNu7e__WF8vUHO-PMC165443&output=visualize
* get document annotations in OA / JSON-LD: https://www.tagtog.net/-demo?docid=a7zefU6irg815RNNu7e__WF8vUHO-PMC165443&output=json-ld
* visualize document provided by url: https://www.tagtog.net/-demo?url=http%3A%2F%2Fbeta.evexdb.org%2Foa%2Fdocument%2Fpubmed%2F17685393%2Fannotations%2F

Other accepted `output` formats (uri parameter) are: `{text, html, xml, ann.json}`

**Known issues**:
* Fragment identifiers do not follow the standard since they refer to text positions within html/xml documents and not to plain text. A fix is under way. Example: `/-demo?docid=a7zefU6irg815RNNu7e__WF8vUHO-PMC165443&output=html&partid=s2s1p1#char=87,90`

### Interoperability with other tools

#### EVEX DB OA Store

Example: https://www.tagtog.net/-demo?url=http%3A%2F%2Fbeta.evexdb.org%2Foa%2Fdocument%2Fpubmed%2F17685393%2Fannotations%2F

**Known issues**:
* Offsets can be unaligned for PubMedCentral documents
* Newlines are not respected (that is, all paragraphs are concatenated into one)
* Relations annotations are not supported yet

