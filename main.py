import os
import urllib.request

import dominate
from dominate.tags import *

from flask import Flask
from flask import render_template
from flask import request
from flask import redirect, url_for, after_this_request



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

g = rdflib.Graph()

result = [] # g.parse("p-lod.nt", format="nt")

def plodheader(doc, kaaresource = ''):
    
    # doc['xmlns'] = "http://www.w3.org/1999/xhtml" # Dominate doesn't produce closed no-content tags
    doc.head += meta(charset="utf-8")
    doc.head += meta(http_equiv="X-UA-Compatible", content="IE=edge")
    doc.head += meta(name="viewport", content="width=device-width, initial-scale=1")
    doc.head += link(rel='stylesheet', href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css",integrity="sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u",crossorigin="anonymous")
    doc.head += link(rel="stylesheet", href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap-theme.min.css", integrity="sha384-rHyoN1iRsVXV4nD0JutlnGaslCJuC7uwjduW9SVrLvRYooPp2bWYgmgJQIXwl/Sp", crossorigin="anonymous")
    doc.head += script(src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js",integrity="sha384-Tc5IQib027qvyjSMfHjOMaLkfuWVxZxUPnCJA7l2mCWNIpG9mGCD8wGNIcPD7Txa",crossorigin="anonymous")
    doc.head += style("body { padding-top: 60px; }")
    doc.head += meta(name="DC.title",lang="en",content="%s" % (plod) )
    doc.head += meta(name="DC.identifier", content="http://kenchreai.org/kaa/%s" % kaaresource)

@app.route('/kaa/ontology/<path:resource>')
def vocabulary(kaapath):
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
    plodheader(vdoc, vocab)

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
    
@app.route('/kaa/<path:kaapath')
def entities(resource):
         
    eresult = g.query(
        """SELECT ?p ?o ?plabel ?olabel
           WHERE {
              p-lod-e:%s ?p ?o .
              OPTIONAL { ?p rdfs:label ?plabel }
              OPTIONAL { ?o rdfs:label ?olabel }
           } ORDER BY ?plabel""" % (entity), initNs = ns)

    elabel = g.query(
        """SELECT ?slabel 
           WHERE {
              p-lod-e:%s rdfs:label ?slabel
           }""" % (entity), initNs = ns)
           
    eparts = g.query(
        """SELECT ?part ?label
           WHERE {
              ?part dcterms:isPartOf p-lod-e:%s .
              ?part rdfs:label ?label .
           } ORDER BY ?part""" % (entity), initNs = ns)
           
    esameas = g.query(
        """SELECT ?url ?label
           WHERE {
              ?url owl:sameAs p-lod-e:%s .
              ?url rdfs:label ?label .
           }""" % (entity), initNs = ns)
           
    eobjects = g.query(
        """SELECT ?s ?p ?slabel ?plabel 
           WHERE {
              ?s  ?p p-lod-e:%s .
              OPTIONAL { ?s rdfs:label ?slabel }
              OPTIONAL { ?p rdfs:label ?plabel }
              FILTER ( ?p != p-lod-v:next )
              FILTER ( ?p != dcterms:isPartOf )
              FILTER ( ?p != owl:sameAs )
           }  ORDER BY ?s LIMIT 1000""" % (entity), initNs = ns)

    edoc = dominate.document(title="Kenchreai Archaeological Archive: %s" % (entity))
    plodheader(edoc, entity)
    
    edoc.body['prefix'] = "bibo: http://purl.org/ontology/bibo/  cc: http://creativecommons.org/ns#  dcmitype: http://purl.org/dc/dcmitype/  dcterms: http://purl.org/dc/terms/  foaf: http://xmlns.com/foaf/0.1/  nm: http://nomisma.org/id/  owl:  http://www.w3.org/2002/07/owl#  rdfs: http://www.w3.org/2000/01/rdf-schema#   rdfa: http://www.w3.org/ns/rdfa#  rdf:  http://www.w3.org/1999/02/22-rdf-syntax-ns#  skos: http://www.w3.org/2004/02/skos/core#"
    with edoc:
        with nav(cls="navbar navbar-default navbar-fixed-top"):
           with div(cls="container-fluid"):
               with div(cls="navbar-header"):
                   a("P-LOD Linked Open Data for Pompeii: Entity", href="/p-lod/entities/pompeii",cls="navbar-brand")
    
        with div(cls="container", about="/p-lod/%s" % (entity)):
        
            with dl(cls="dl-horizontal"):
                dt()
                for row in elabel:
                    dd(strong(str(row.slabel), cls="large"))
                    
                for row in eresult:
                    if str(row.p) == 'http://www.w3.org/2000/01/rdf-schema#label':
                        continue
                    elif str(row.plabel) != 'None':
                        dt(str(row.plabel))
                    else:
                        dt(i(str(row.p)))
                
                    with dd():
                        if str(row.olabel) != "None":
                            olabel = str(row.olabel)
                        else:
                            olabel = str(row.o)
                
                        if str(row.o)[0:4] == 'http':
                            a(olabel,href = str(row.o).replace('http://digitalhumanities.umass.edu',''))
                        else:
                            span(olabel)
                
        
                if len(esameas) > 0:
                    for row in esameas:
                        dt("Alternate identifier")
                        dd(str(row.url))

        
                dt("Future permalink")
                dd("http://digitalhumanities.umass.edu/p-lod/entities/%s" % (entity) )

        
                if len(eparts) > 0:
                    dt('Has parts')
                    with dd():
                        for part in eparts:
                            span(a(str(part.label), rel="dcterms:hasPart", href = str(part.part).replace('http://digitalhumanities.umass.edu','')))
                            br()
                
                objlength = len(eobjects)
                if objlength > 0:
                    lenstr = ''
                    if objlength == 1000:
                        lenstr = '(first 1000)'
                    dt("Property of %s" % (lenstr))
                    with dd():
                         for s_p in eobjects:
                            a(str(s_p.slabel), href= str(s_p.s).replace('http://digitalhumanities.umass.edu',''))
                            span(" via ")
                            span(str(s_p.plabel))
                            br()

                
        with footer(cls="footer"):
            with div(cls="container"):
                with p(cls="text-muted"):
                    span("P-LOD is under construction and is overseen by Steven Ellis, Sebastian Heath and Eric Poehler. Data available on ")
                    a("Github", href = "https://github.com/p-lod/p-lod")
                    span(". Parse ")
                    a('RDFa', href="http://www.w3.org/2012/pyRdfa/extract?uri=http://p-lod.herokuapp.com/p-lod/entities/%s" % (entity))
                    span(".")

                
    return edoc.render()


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
    

    