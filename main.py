import os
import re
import urllib.request
import html

import dominate

from bs4 import BeautifulSoup

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

def kaafooter(doc, kaapath = '', editorLink = False ):
    with doc:
        with footer(cls="footer"):
            with div(cls="container"):
                with p(cls="text-muted"):
                    span("©2016 The ")
                    a("American Excavations at Kenchreai", href="http://www.kenchreai.org")
                    span(". Data and images available for non-commercial, personal use only. See ")
                    a("Github", href="https://github.com/kenchreai/kaa-ttl")
                    span(" for Turtle (TRIG) formatted source files.")
                
                    if editorLink:
                        a("🔗" , href="https://kenchreai-data-editor.herokuapp.com/#/detail/%s" % kaapath)
                    
                        
@app.route('/kaa/<path:kaapath>')
@app.route('/kaa')
def kaasparql(kaapath = 'kaa'):

    if kaapath == 'kaa':
        uri = 'http://kenchreai.org/kaa'
    else:
        uri = 'http://kenchreai.org/kaa/' + kaapath

    kaaquery =  """SELECT ?p ?o ?plabel ?olabel  WHERE
{ { <%s> ?p ?o .
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
 UNION { <%s> kaaont:observed ?s . ?s ?p ?o . } } ORDER BY ?s ?plabel""" % (uri,uri)
           
    endpoint.setQuery(kaaquery)
    endpoint.setReturnFormat(JSON)
    kaaresult = endpoint.query().convert()

    physicalquery = """SELECT  ?s ?p ?slabel ?sthumb WHERE
 { { <%s> <http://kenchreai.org/kaa/ontology/has-physical-part> ?s .
  OPTIONAL  { ?s <http://kenchreai.org/kaa/ontology/next> <%s> .
 ?s ?p <%s> }
 OPTIONAL  { ?s <http://www.w3.org/2000/01/rdf-schema#label> ?slabel . }
 OPTIONAL  { ?s <http://xmlns.com/foaf/0.1/name> ?slabel . }
 OPTIONAL { ?s kaaont:file|kaaont:pagescan|kaaont:photograph|kaaont:drawing ?sthumb . FILTER regex(?sthumb, 'png$')  }
 } } ORDER BY ?s""" % (uri,uri,uri)
    reasoner.setQuery(physicalquery)
    reasoner.setReturnFormat(JSON)
    physicalresult = reasoner.query().convert()


    conceptualquery = """SELECT  ?s ?p ?slabel ?sthumb WHERE
 { {  { <%s> <http://kenchreai.org/kaa/ontology/has-logical-part> ?s . }
 UNION  { ?s <http://kenchreai.org/kaa/ontology/same-as> <%s> .  }
 OPTIONAL  { ?s <http://kenchreai.org/kaa/ontology/next> <%s> . ?s ?p <%s> }
 OPTIONAL  { ?s <http://www.w3.org/2000/01/rdf-schema#label> ?slabel . }\
 OPTIONAL { ?s kaaont:file|kaaont:pagescan|kaaont:photograph|kaaont:drawing ?sthumb . FILTER regex(?sthumb, 'png$') } }\
 FILTER (!isBlank(?s))  } ORDER BY ?s""" % (uri,uri,uri,uri)
    reasoner.setQuery(conceptualquery)
    reasoner.setReturnFormat(JSON)
    conceptualresult = reasoner.query().convert()
    

    kaalabel = """SELECT ?slabel 
           WHERE {
              <%s> rdfs:label ?slabel
           }""" % (uri)
    endpoint.setQuery(kaalabel)
    endpoint.setReturnFormat(JSON)
    labelresult = endpoint.query().convert()

    label = ''
    for result in labelresult["results"]["bindings"]:
        label = result["slabel"]["value"]
    if label == '':
        label = 'kaa:' + kaapath

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
        
        with div(cls="container", about="/kaa/%s" % (kaapath), style="margin-top:.5em"):
            
            # declare the next variable
            next = None
            with dl(cls="dl-horizontal"):
                dt(" ")
                with dd(cls="large", __pretty=False):
                    strong(label)
                    span(' [')
                    a('permalink', href=uri)
                    span('] ')
                    span(id="next")

                for row in kaaresult["results"]["bindings"]:
                    if row["p"]["value"] == 'http://www.w3.org/2000/01/rdf-schema#label':
                        continue
                    elif row["p"]["value"] == 'http://kenchreai.org/kaa/ontology/next':
                        next = row["o"]["value"]
                        continue
                    elif "plabel" in row.keys():
                        dt(row["plabel"]["value"], style="white-space: normal")
                    else:
                        dt(i(row["p"]["value"]), style="white-space: normal")
                
                    with dd():
                        rkeys = row.keys()
                        if "olabel" in rkeys:
                            olabel = row["olabel"]["value"]
                        else:
                            olabel = row["o"]["value"]
                        
                        if re.search('(\.png|\.jpg)$', row["o"]["value"], flags= re.I):
                            img(style="max-width:250px",src="http://kenchreai-archaeological-archive-files.s3-website-us-west-2.amazonaws.com/%s" % row["o"]["value"])  
                        elif re.search('(\.pdf|\.tif|\.tiff)$', row["o"]["value"], flags= re.I):
                            iframe(src="http://docs.google.com/gview?url=http://kenchreai-archaeological-archive-files.s3-website-us-west-2.amazonaws.com/%s&embedded=true" % row["o"]["value"],style="width:600px; height:500px;",frameborder="0")
                        elif row["o"]["value"][0:4] == 'http':
                            a(olabel,href = row["o"]["value"].replace('http://kenchreai.org',''))
                        else:
                            span(olabel)
                                    
                          
                if len(physicalresult["results"]["bindings"]) > 0:
                    dt('Has physical parts')
                    curlabel = ''
                    first = 0
                    # compile all URIs into a single dd element
                    # issue: i'd like to be able to indicate how many resources are parts. It's not 
                    # len(physical["results"]["bindings"]) as that repeats ?s
                    with dd():
                        for row in physicalresult["results"]["bindings"]:
                            if "slabel" in row.keys():
                                label = row["slabel"]["value"]
                            else:
                                label = re.sub('http://kenchreai.org/kaa/','kaa:',row["s"]["value"])
                            
                            if curlabel != label:
                                curlabel = label
                                if first == 1:
                                    first = 0
                                    pstyle = ''
                                else:
                                    pstyle = 'border-top: thin dotted #aaa'   
                                                            
                                p(a(label, style=pstyle, rel="dcterms:hasPart", href = row["s"]["value"].replace('http://kenchreai.org','')))
      
                            if 'sthumb' in row.keys():
                                thumb = row["sthumb"]["value"]
                                thumb = re.sub(r"(/[^/]+$)",r"/thumbs\1",thumb)
                                img(style="margin-left:1em;margin-bottom:15px;max-width:150px;max-height:150px",src="http://kenchreai-archaeological-archive-files.s3-website-us-west-2.amazonaws.com/%s" % thumb)  


                if len(conceptualresult["results"]["bindings"]) > 0:
                    dt('Linked to')
                    curlabel = ''
                    first = 0
                    # compile all URIs into a single dd element
                    # issue: i'd like to be able to indicate how many resources are linked to. It's not 
                    # len(conceptualresult["results"]["bindings"]) as that repeats ?s
                    with dd():
                        for row in conceptualresult["results"]["bindings"]:
                            if 'slabel' in row.keys():
                                label = row["slabel"]["value"]
                            else:
                                label = re.sub('http://kenchreai.org/kaa/','kaa:',row["s"]["value"])
                                                    
                            if curlabel != label:
                                curlabel = label
                                if first == 1:
                                    first = 0
                                    pstyle = ''
                                else:
                                    pstyle = 'border-top: thin dotted #aaa;'
                                    
                                p(a(label, style=pstyle, rel="dcterms:hasPart", href = row["s"]["value"].replace('http://kenchreai.org','')))
                                
                            if 'sthumb' in row.keys():
                                thumb = row["sthumb"]["value"]
                                if '/' in thumb:
                                    thumb = re.sub(r"(/[^/]+$)",r"/thumbs\1",thumb)
                                else:
                                    thumb = 'thumbs/' + thumb
                                img(style="margin-left:1em;margin-bottom:15px;max-width:150px;max-height:150px",src="http://kenchreai-archaeological-archive-files.s3-website-us-west-2.amazonaws.com/%s" % thumb)  
                                
    kaafooter(kaadoc, kaapath, True)
    
    if next is not None:         
        soup =  BeautifulSoup(kaadoc.render(), "html.parser")
        asoup = BeautifulSoup('[<a href="%s">next</a>]' % next.replace('http://kenchreai.org',''), 'html.parser')
        tag = soup.find(id='next')
        tag.append(asoup)
        return str(soup)
    else:
        return kaadoc.render()

@app.route('/api/full-text-search')
def fulltextsearch():
    q = request.args.get('q')
    
    if q != '' and q is not None:
        qexists = True
    else:
        qexists = False

    if qexists == True:
        ftquery = """SELECT DISTINCT ?s ?slabel ?sthumb
                        WHERE {
                        (?l ?score) <tag:stardog:api:property:textMatch> '%s'.
                        ?s ?p ?l . 
                        ?s rdfs:label ?slabel .
                        OPTIONAL { ?s kaaont:drawing|kaaont:photograph ?sthumb . }
                        
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
                   with form(cls="navbar-form navbar-left", role="search"):
                       with div(cls="form-group"):
                           input(id="q", name="q", type="text",cls="form-control",placeholder="Search...")
                   with ul(cls="nav navbar-nav"):
                       with li(cls="dropdown"):
                           a("Example Searches", href="#",cls="dropdown-toggle", data_toggle="dropdown")
                           with ul(cls="dropdown-menu", role="menu"):
                               li(a('+ke +1221', href="/api/full-text-search?q=%2Bke%20%2B1221"))
                               li(a('+corinthian +lamp', href="/api/full-text-search?q=%2Bcorinthian%20%2Blamp"))
                               li(a('+gold -ring', href="/api/full-text-search?q=%2Bgold%20%2Dring"))
                               li(a('"ke 1221"', href="/api/full-text-search?q=%22ke%201221%22"))
                               li(a('fish*', href="/api/full-text-search?q=fish%2A"))
                               li(a('ΔΙΟΝΕΙΚΟΥ', href="/api/full-text-search?q=ΔΙΟΝΕΙΚΟΥ"))
        
        with dl(cls="dl-horizontal"):
            
            dt("Search")
            if qexists == True:
                dd(q)
            else:
                dd('<nothing entered>')
            
            dt("Results")
            with dd():
                first = 0
                curlabel = ''
                if qexists == True:
                    for row in ftresult["results"]["bindings"]:
                    
                        if 'slabel' in row.keys():
                            label = row["slabel"]["value"]
                        else:
                            label = re.sub('http://kenchreai.org/kaa/','kaa:',row["s"]["value"])

                        if curlabel != label:
                            curlabel = label
                            if first == 1:
                                first = 0
                                pstyle = ''
                            else:
                                pstyle = 'border-top: thin dotted #aaa;'
        
                            p(a(row["slabel"]["value"], style = pstyle, href=row["s"]["value"].replace('http://kenchreai.org','')))
                            
                        if 'sthumb' in row.keys():
                            thumb = row["sthumb"]["value"]
                            if '/' in thumb:
                                thumb = re.sub(r"(/[^/]+$)",r"/thumbs\1",thumb)
                            else:
                                thumb = 'thumbs/' + thumb
                            # if re.search(r'(.png|.jpg)',thumb, flags= re.I):
                                img(style="margin-left:1em;margin-bottom:15px;max-width:150px;max-height:150px",src="http://kenchreai-archaeological-archive-files.s3-website-us-west-2.amazonaws.com/%s" % thumb)  
         
    kaafooter(ftdoc)
    
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
