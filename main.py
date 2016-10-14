import os
import urllib.request

import dominate
from dominate.tags import *

from flask import Flask
from flask import render_template
from flask import request
from flask import redirect, url_for, after_this_request

from SPARQLWrapper import SPARQLWrapper, JSON



import rdflib

ns = {"dcterms" : "http://purl.org/dc/terms/" ,
      "owl"     : "http://www.w3.org/2002/07/owl#" ,
      "rdf"     : "http://www.w3.org/1999/02/22-rdf-syntax-ns#" ,
      "rdfs"    : "http://www.w3.org/2000/01/rdf-schema#" ,
      "kaa"     : "http://kenchreai.org/kaa/" ,
      "kaakcp"  : "http://kenchreai.org/kaa/kcp" ,
      "kaake"   : "http://kenchreai.org/kaa/ke/" ,
      "kaakth"  : "http://kenchreai.org/kaa/kth/" ,
      "kaaont"  : "http://kenchreai.org/kaa/ontology" ,
      "kaatyp"  : "http://kenchreai.org/kaa/typology/"}

app = Flask(__name__)

# g = rdflib.Graph()

# result = [] # g.parse("p-lod.nt", format="nt")

endpoint = SPARQLWrapper("http://kenchreai.org/endpoint/kenchreai/query")
reasoner = SPARQLWrapper("http://kenchreai.org/reasoner/kenchreai/query")

def kaaheader(doc, kaapath = ''):
    
    # doc['xmlns'] = "http://www.w3.org/1999/xhtml" # Dominate doesn't produce closed no-content tags
    doc.head += meta(charset="utf-8")
    doc.head += meta(http_equiv="X-UA-Compatible", content="IE=edge")
    doc.head += meta(name="viewport", content="width=device-width, initial-scale=1")
    doc.head += link(rel='stylesheet', href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css",integrity="sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u",crossorigin="anonymous")
    doc.head += link(rel="stylesheet", href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap-theme.min.css", integrity="sha384-rHyoN1iRsVXV4nD0JutlnGaslCJuC7uwjduW9SVrLvRYooPp2bWYgmgJQIXwl/Sp", crossorigin="anonymous")
    doc.head += script(src="http://code.jquery.com/jquery-3.1.1.min.js")
    doc.head += script(src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js",integrity="sha384-Tc5IQib027qvyjSMfHjOMaLkfuWVxZxUPnCJA7l2mCWNIpG9mGCD8wGNIcPD7Txa",crossorigin="anonymous")
    doc.head += style("body { padding-top: 60px; }")
    doc.head += meta(name="DC.title",lang="en",content="%s" % (kaapath) )
    doc.head += meta(name="DC.identifier", content="http://kenchreai.org/kaa/%s" % kaapath)
        

@app.route('/kaa/ontology/<path:ontpath>')
def vocabulary(ontpath):
    vresult = g.query(
        """SELECT ?p ?o ?plabel ?olabel
           WHERE {
              p-lod-v:%s ?p ?o .
              OPTIONAL { ?p rdfs:label ?plabel }
              OPTIONAL { ?o rdfs:label ?olabel }
           }""" % (vocab), initNs = ns)

    vlabel = g.query(
        """SELECT ?slabel 
           WHERE {
              p-lod-v:%s rdfs:label ?slabel
           }""" % (vocab), initNs = ns)
           
    vinstances = g.query(
        """SELECT ?instance ?label
           WHERE {
              ?instance rdf:type p-lod-v:%s .
              ?instance rdfs:label ?label .
           } ORDER BY ?instance""" % (vocab), initNs = ns)
           
    vsubclasses = g.query(
        """SELECT ?subclass ?label
           WHERE {
              ?subclass rdfs:subClassOf p-lod-v:%s .
              ?subclass rdfs:label ?label .
           } ORDER BY ?label""" % (vocab), initNs = ns)    

    vdoc = dominate.document(title="Pompeii LOD: %s" % (vocab))
    kaaheader(vdoc, vocab)

    with vdoc:

        with nav(cls="navbar navbar-default navbar-fixed-top"):
           with div(cls="container-fluid"):
               with div(cls="navbar-header"):
                   a("P-LOD Linked Open Data for Pompeii: Vocabulary", href="/p-lod/entities/pompeii",cls="navbar-brand")

        with div(cls="container"):
            with dl(cls="dl-horizontal"):
                dt()
                for row in vlabel:
                    dd(strong(str(row.slabel), cls="large"))

                for row in vresult:
                    if str(row.p) == 'http://www.w3.org/2000/01/rdf-schema#label':
                        continue
                    elif str(row.plabel) != 'None':
                        dt(str(row.plabel)+":")
                    else:
                        dt(i(str(row.p)), style = "margin-left:.25em")
                
                    with dd():
                        if str(row.olabel) != "None":
                            olabel = str(row.olabel)
                        else:
                            olabel = str(row.o)
                
                        if str(row.o)[0:4] == 'http':
                            a(olabel,href = str(row.o).replace('http://digitalhumanities.umass.edu',''))
                        else:
                            span(olabel)
        
                if len(vinstances) > 0:
                    dt('Entities')
                    with dd():
                        for instance in vinstances:
                            span(a(str(instance.label), href = str(instance.instance).replace('http://digitalhumanities.umass.edu','')))
                            br()
        
                if len(vsubclasses) > 0:
                    dt('Subclasses')
                    with dd():
                        for subclass in vsubclasses:
                            span(a(str(subclass.label), href = str(subclass.subclass).replace('http://digitalhumanities.umass.edu','')))
                            br()

            hr()
            with p():
                span("P-LOD is under construction and is overseen by Steven Ellis, Sebastian Heath and Eric Poehler. Data available on ")
                a("Github", href = "https://github.com/p-lod/p-lod")
                span(".")  
                 
    return vdoc.render()
    
@app.route('/kaa/<path:kaapath>')
def kaasparql(kaapath):
         
    kaaquery =  """SELECT ?p ?o ?plabel ?olabel  WHERE
{ { <http://kenchreai.org/kaa/%s> ?p ?o .
 MINUS {?s kaaont:location ?o }
 MINUS {?s kaaont:observed ?o }
 MINUS {?s kaaont:same-as ?o }
 MINUS {?s kaaont:kaa-note ?o }
 MINUS {?s ?p <http://www.w3.org/2000/01/rdf-schema#Resource> }
 OPTIONAL  { graph ?g {?p <http://www.w3.org/2000/01/rdf-schema#label> ?plabel . } }
 OPTIONAL  { graph ?g {?o <http://www.w3.org/2000/01/rdf-schema#label> ?olabel . } }
 OPTIONAL  { ?o <http://www.w3.org/2000/01/rdf-schema#label> ?olabel . }
 OPTIONAL  { ?p <http://www.w3.org/2000/01/rdf-schema#label> ?plabel . }
  }\
 UNION { <http://kenchreai.org/kaa/%s> kaaont:observed ?s . ?s ?p ?o . } } ORDER BY ?s """ % (kaapath,kaapath)
           
    endpoint.setQuery(kaaquery)
    endpoint.setReturnFormat(JSON)
    kaaresult = endpoint.query().convert()

    physicalquery = """SELECT  ?s ?p ?stitle ?sthumb WHERE
 { { <http://kenchreai.org/kaa/%s> <http://kenchreai.org/kaa/ontology/has-physical-part> ?s .
  OPTIONAL  { ?s <http://kenchreai.org/kaa/ontology/next> <http://kenchreai.org/kaa/%s> .
 ?s ?p <http://kenchreai.org/kaa/%s> }
 OPTIONAL  { ?s <http://www.w3.org/2000/01/rdf-schema#label> ?stitle . }
 OPTIONAL  { ?s <http://xmlns.com/foaf/0.1/name> ?stitle . }
 OPTIONAL { ?s kaaont:file|kaaont:pagescan|kaaont:photograph|kaaont:drawing ?sthumb . FILTER regex(?sthumb, 'png$')  }
 } } ORDER BY ?s""" % (kaapath,kaapath,kaapath)
    reasoner.setQuery(physicalquery)
    reasoner.setReturnFormat(JSON)
    physicalresult = reasoner.query().convert()


    conceptualquery = """SELECT  ?s ?p ?stitle ?sthumb WHERE
 { {  { <http://kenchreai.org/kaa/%s> <http://kenchreai.org/kaa/ontology/has-logical-part> ?s . }
 UNION  { ?s <http://kenchreai.org/kaa/ontology/same-as> <http://kenchreai.org/kaa/%s> .  }
 OPTIONAL  { ?s <http://kenchreai.org/kaa/ontology/next> <http://kenchreai.org/kaa/%s> . ?s ?p <http://kenchreai.org/kaa/%s> }
 OPTIONAL  { ?s <http://www.w3.org/2000/01/rdf-schema#label> ?stitle . }\
 OPTIONAL { ?s kaaont:file|kaaont:pagescan|kaaont:photograph|kaaont:drawing ?sthumb . FILTER regex(?sthumb, 'png$') } }\
 FILTER (!isBlank(?s))  } ORDER BY ?s""" % (kaapath,kaapath,kaapath,kaapath)
    reasoner.setQuery(conceptualquery)
    reasoner.setReturnFormat(JSON)
    conceptualresult = reasoner.query().convert()
    

    kaalabel = """SELECT ?slabel 
           WHERE {
              <http://kenchreai.org/kaa/%s> rdfs:label ?slabel
           }""" % (kaapath)
    endpoint.setQuery(kaalabel)
    endpoint.setReturnFormat(JSON)
    labelresult = endpoint.query().convert()

    for result in labelresult["results"]["bindings"]:
        label = result["slabel"]["value"]

    kaadoc = dominate.document(title="Kenchreai Archaeological Archive: %s" % (label))
    kaaheader(kaadoc, label)
    
    kaadoc.body['prefix'] = "bibo: http://purl.org/ontology/bibo/  cc: http://creativecommons.org/ns#  dcmitype: http://purl.org/dc/dcmitype/  dcterms: http://purl.org/dc/terms/  foaf: http://xmlns.com/foaf/0.1/  nm: http://nomisma.org/id/  owl:  http://www.w3.org/2002/07/owl#  rdfs: http://www.w3.org/2000/01/rdf-schema#   rdfa: http://www.w3.org/ns/rdfa#  rdf:  http://www.w3.org/1999/02/22-rdf-syntax-ns#  skos: http://www.w3.org/2004/02/skos/core#"
    with kaadoc:
        with nav(cls="navbar navbar-default navbar-fixed-top"):
           with div(cls="container-fluid"):
               with div(cls="navbar-header"):
                   a("Kenchreai Archaeological Archive", href="/kaa",cls="navbar-brand")
                   with form(cls="navbar-form navbar-right", role="search", action="/api/full-text-search"):
                       with div(cls="form-group"):
                           input(id="q", name="q", type="text",cls="form-control",placeholder="Search...")
        
        with dl(cls="dl-horizontal"):
                 dt()
                 dd(strong(label), cls="large")
        
        with div(cls="container", about="/kaa/%s" % (kaapath)):
            # p(str(kaaresult))
            with dl(cls="dl-horizontal"):
                for row in kaaresult["results"]["bindings"]:
                    if row["p"]["value"] == 'http://www.w3.org/2000/01/rdf-schema#label':
                        continue
                    elif row["plabel"]["value"] != 'None':
                        dt(row["plabel"]["value"], style="white-space: normal")
                    else:
                        dt(i(row["p"]["value"]), style="white-space: normal")
                
                    with dd():
                        rkeys = row.keys()
                        if "olabel" in rkeys:
                            olabel = row["olabel"]["value"]
                        else:
                            olabel = row["o"]["value"]
            
                        if row["o"]["value"][0:4] == 'http':
                            a(olabel,href = row["o"]["value"].replace('http://kenchreai.org',''))
                        else:
                            span(olabel)

                          
                if len(physicalresult["results"]["bindings"]) > 0:
                    dt('Has parts')
                    dd("Worked...")

                if len(conceptualresult["results"]["bindings"]) > 0:
                    dt('Linked to')
                    with dd():
                        for row in conceptualresult["results"]["bindings"]:
                            span(a(row["stitle"]["value"], rel="dcterms:hasPart", href = row["s"]["value"].replace('http://kenchreai.org','')))
                            br()



#                     with dd():
#                         for part in eparts:
#                             span(a(str(part.label), rel="dcterms:hasPart", href = str(part.part).replace('http://digitalhumanities.umass.edu','')))
#                             br()
#                 
#                 objlength = len(eobjects)
#                 if objlength > 0:
#                     lenstr = ''
#                     if objlength == 1000:
#                         lenstr = '(first 1000)'
#                     dt("Property of %s" % (lenstr))
#                     with dd():
#                          for s_p in eobjects:
#                             a(str(s_p.slabel), href= str(s_p.s).replace('http://digitalhumanities.umass.edu',''))
#                             span(" via ")
#                             span(str(s_p.plabel))
#                             br()

                
# with footer(cls="footer"):
# with div(cls="container"):
# with p(cls="text-muted"):
# span("KAA.")

                
    return kaadoc.render()

@app.route('/api/full-text-search')
def fulltextsearch():
    q = request.args.get('q')
    
    ftquery = """SELECT DISTINCT ?s ?slabel ?score
WHERE {
?s ?p ?l.
?s rdfs:label ?slabel .
(?l ?score) <tag:stardog:api:property:textMatch> '%s'.
}""" % (q)

    endpoint.setQuery(ftquery)
    endpoint.setReturnFormat(JSON)
    ftresult = endpoint.query().convert()

    ftdoc = dominate.document(title="Kenchreai Archaeological Archive: Full-Text Search")
    kaaheader(ftdoc, '')
    
    ftdoc.body['prefix'] = "bibo: http://purl.org/ontology/bibo/  cc: http://creativecommons.org/ns#  dcmitype: http://purl.org/dc/dcmitype/  dcterms: http://purl.org/dc/terms/  foaf: http://xmlns.com/foaf/0.1/  nm: http://nomisma.org/id/  owl:  http://www.w3.org/2002/07/owl#  rdfs: http://www.w3.org/2000/01/rdf-schema#   rdfa: http://www.w3.org/ns/rdfa#  rdf:  http://www.w3.org/1999/02/22-rdf-syntax-ns#  skos: http://www.w3.org/2004/02/skos/core#"
    with ftdoc:
        with nav(cls="navbar navbar-default navbar-fixed-top"):
           with div(cls="container-fluid"):
               with div(cls="navbar-header"):
                   a("KAA: Full-Text Search" , href="/kaa",cls="navbar-brand")
                   with form(cls="navbar-form navbar-right", role="search"):
                       with div(cls="form-group"):
                           input(id="q", name="q", type="text",cls="form-control",placeholder="Search...")
        
        with dl(cls="dl-horizontal"):
            dt("Results")
            with dd():
                for row in ftresult["results"]["bindings"]:
                    a(row["slabel"]["value"], href=row["s"]["value"].replace('http://kenchreai.org',''))
                    br()
                
    return ftdoc.render()
    

@app.route('/api/geojson/<path:kaapath>')
def geojson_entity(kaapath):
        geojsonr = g.query(
        """SELECT ?lat ?long ?geojson
           WHERE {
              OPTIONAL { p-lod-e:%s p-lod-v:latitude ?lat ;
                                    p-lod-v:longitude ?long .
                         }
              OPTIONAL { p-lod-e:%s p-lod-v:geojson ?geojson }
           }""" % (entity, entity), initNs = ns)
        
        if len(geojsonr) > 0:
            for row in geojsonr:
                pass
                    

@app.route('/')
def index():
    return redirect("http://www.kenchreai.org/", code=302)
    

    