import os
import re
import urllib.parse
import urllib.request

import dominate

from bs4 import BeautifulSoup

from dominate.tags import *
from dominate.util import raw

from flask import Flask
from flask import render_template
from flask import request
from flask import redirect, url_for, after_this_request

from SPARQLWrapper import SPARQLWrapper, JSON

from time import *

import rdflib

# SPARQL PREFIXES
# BUT THESE ARE NO LONGER USED WITH SPARQLWrapper so here for historical reasons only

suppressmore = ['http://kenchreai.org/kaa' ,
                'http://kenchreai.org/kaa/eastern-mediterranean' , 
                'http://kenchreai.org/kaa/geographic-entities' , 
                'http://kenchreai.org/kaa/greece' ]

ns = {"dcterms" : "http://purl.org/dc/terms/" ,
      "owl"     : "http://www.w3.org/2002/07/owl#" ,
      "rdf"     : "http://www.w3.org/1999/02/22-rdf-syntax-ns#" ,
      "rdfs"    : "http://www.w3.org/2000/01/rdf-schema#" ,
      "kaa"     : "http://kenchreai.org/kaa/" ,
      "kaakcp"  : "http://kenchreai.org/kaa/kcp" ,
      "kaake"   : "http://kenchreai.org/kaa/ke/" ,
      "kaakth"  : "http://kenchreai.org/kaa/kth/" ,
      "kaaont"  : "http://kenchreai.org/kaa/ontology" ,
      "kaatyp"  : "http://kenchreai.org/kaa/typology/" }

app = Flask(__name__)

# 'endpoint' does not have reasoning enabled. 'reasoner' does.
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
                    span("©2017 The ")
                    a("American Excavations at Kenchreai", href="http://www.kenchreai.org")
                    span(". Data and images available for non-commercial, personal use only. See ")
                    a("Github", href="https://github.com/kenchreai/kaa-ttl")
                    span(" for Turtle (TRIG) formatted source files.")
                
                    if editorLink:
                        a("🔗" , href="https://kenchreai-data-editor.herokuapp.com/detail/%s" % kaapath)
                    
                        
@app.route('/kaa/<path:kaapath>')
@app.route('/kaa')
def kaasparql(kaapath = 'kaa'):

    more = request.args.get('more')

    if more == 'true':
        more = True
    else:
        more = False

    if kaapath == 'kaa':
        uri = 'http://kenchreai.org/kaa'
    else:
        uri = 'http://kenchreai.org/kaa/' + kaapath

    # this query goes to the non-reasoning endpoint
    kaaquery = """SELECT ?p ?o ?plabel ?pcomment ?pxorder ?olabel  WHERE
{ { <%s> ?p ?o .
 MINUS {?s kaaont:location ?o }
 MINUS {?s kaaont:observed ?o }
 MINUS {?s kaaont:same-as ?o }
 MINUS {?s kaaont:kaa-note ?o }
 MINUS {?s ?p <http://www.w3.org/2000/01/rdf-schema#Resource> }
 OPTIONAL  { graph ?g {?p <http://www.w3.org/2000/01/rdf-schema#label> ?plabel . } }
 OPTIONAL  { graph ?g {?p <http://www.w3.org/2000/01/rdf-schema#comment> ?pcomment . } }
 OPTIONAL  { graph ?g {?p kaaont:x-sort-order ?pxorder . } }
 OPTIONAL  { graph ?g {?o <http://www.w3.org/2000/01/rdf-schema#label> ?olabel . } }
 OPTIONAL  { ?o <http://www.w3.org/2000/01/rdf-schema#label> ?olabel . }
 OPTIONAL  { ?p <http://www.w3.org/2000/01/rdf-schema#label> ?plabel . }
  }\
 UNION { <%s> kaaont:observed ?s . ?s ?p ?o . } } ORDER BY ?pxorder ?p ?plabel ?olabel ?o""" % (uri,uri)
           
    endpoint.setQuery(kaaquery)
    endpoint.setReturnFormat(JSON)
    kaaresult = endpoint.query().convert()

    if more == False:
        # This query should be passed to reasoner
        physicalquery = """SELECT  ?s ?p ?slabel ?sthumb WHERE
     { { <%s> <http://kenchreai.org/kaa/ontology/has-physical-part> ?s .
      OPTIONAL  { ?s <http://kenchreai.org/kaa/ontology/next> <%s> .
     ?s ?p <%s> }
     OPTIONAL  { ?s <http://www.w3.org/2000/01/rdf-schema#label> ?slabel . }
     OPTIONAL  { ?s <http://xmlns.com/foaf/0.1/name> ?slabel . }
     OPTIONAL { ?s kaaont:file|kaaont:pagescan|kaaont:photograph|kaaont:drawing ?sthumb . FILTER regex(?sthumb, '(jpg|png)$')  }
     } } ORDER BY ?s ?slabel""" % (uri,uri,uri)
        reasoner.setQuery(physicalquery)
        reasoner.setReturnFormat(JSON)
        physicalresult = reasoner.query().convert()

        # This query should be passed to reasoner
        conceptualquery = """SELECT  ?s ?p ?slabel ?sthumb WHERE
     { {  { <%s> <http://kenchreai.org/kaa/ontology/has-logical-part> ?s . }
     UNION  { ?s <http://kenchreai.org/kaa/ontology/same-as> <%s> .  }
     OPTIONAL  { ?s <http://kenchreai.org/kaa/ontology/next> <%s> . ?s ?p <%s> }
     OPTIONAL  { ?s <http://www.w3.org/2000/01/rdf-schema#label> ?slabel . }\
     OPTIONAL { ?s kaaont:file|kaaont:pagescan|kaaont:photograph|kaaont:drawing ?sthumb . FILTER regex(?sthumb, '(jpg|png)$') } }
     FILTER (!isBlank(?s))  } ORDER BY ?s ?slabel""" % (uri,uri,uri,uri)
        reasoner.setQuery(conceptualquery)
        reasoner.setReturnFormat(JSON)
        conceptualresult = reasoner.query().convert()
    
    # This query should be passed to reasoner
    if more == True:
        morequery = """SELECT DISTINCT ?o ?olabel ?othumb WHERE {
  <%s> ^kaaont:is-part-of+ ?o .
  ?o rdfs:label ?olabel .
  ?o rdf:type ?otype
   OPTIONAL { ?o kaaont:file|kaaont:pagescan|kaaont:photograph|kaaont:drawing ?othumb . FILTER regex(?othumb, '(jpg|png)$') } 
   FILTER isIRI(?o)
   } ORDER BY ?o LIMIT 4000""" % (uri)
        reasoner.setQuery(morequery)
        reasoner.setReturnFormat(JSON)
        moreresult = reasoner.query().convert()


    kaalabel = """SELECT ?slabel 
           WHERE {
              <%s> rdfs:label ?slabel
           }""" % (uri)
    endpoint.setQuery(kaalabel)
    endpoint.setReturnFormat(JSON)
    labelresult = endpoint.query().convert()

    pagelabel = ''
    for result in labelresult["results"]["bindings"]:
        pagelabel = result["slabel"]["value"]
    if pagelabel == '':
        pagelabel = 'kaa:' + kaapath

    kaadoc = dominate.document(title="Kenchreai Archaeological Archive: %s" % (pagelabel))
    kaaheader(kaadoc, pagelabel)
    
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
                dt(" ", style="margin-bottom: .5em; margin-top: 1em; white-space: nowrap")
                with dd(cls="large", style="margin-bottom: .5em; margin-top: 1em", __pretty=False):
                    strong(pagelabel)
                    span(' [')
                    a('permalink', href=uri)
                    span('] ')
                    span(id="next")
                    if (more == False) and (uri not in suppressmore):
                        span(' [')
                        a('show more links', href='/kaa/'+kaapath+'?more=true',title='Clicking here will cause the database to search for linked resources more aggresively. Can take a long time!')
                        span('] ')
                    if (more == True):
                        span(' [')
                        a('show fewer links', href='/kaa/'+kaapath,title='Clicking here will cause the database to show only directly lined resources')
                        span('] ')


                for row in kaaresult["results"]["bindings"]:
                    
                    if 'pcomment' in row.keys():
                        pcomment = "%s [%s]" % (row["pcomment"]["value"],row["p"]["value"].replace('http://kenchreai.org/kaa/ontology/','kaaont:'))
                    else:
                        pcomment = row["p"]["value"].replace('http://kenchreai.org/kaa/ontology/','kaaont:')
                
                    if row["p"]["value"] == 'http://www.w3.org/2000/01/rdf-schema#label':
                        continue
                    elif row["p"]["value"] == 'http://kenchreai.org/kaa/ontology/next':
                        next = row["o"]["value"]
                        continue
                    elif "plabel" in row.keys():
                        dt(row["plabel"]["value"], style="white-space: nowrap; width:12em", title = pcomment)
                    else:
                        dt(i(row["p"]["value"]), style="white-space: normal; width:12em")
                
                    with dd():
                        rkeys = row.keys()
                        if "olabel" in rkeys:
                            olabel = row["olabel"]["value"]
                        else:
                            olabel = row["o"]["value"]
                        
                        if re.search('(\.png|\.jpg)$', row["o"]["value"], flags= re.I):
                            a(img(style="max-width:600px;max-height:350px",src="http://kenchreai-archaeological-archive-files.s3-website-us-west-2.amazonaws.com/%s" % row["o"]["value"]), href="/api/display-image-file?q=%s" % row["o"]["value"])
                        elif re.search('(\.pdf|\.tif|\.tiff)$', row["o"]["value"], flags= re.I):
                            iframe(src="http://docs.google.com/gview?url=http://kenchreai-archaeological-archive-files.s3-website-us-west-2.amazonaws.com/%s&embedded=true" % row["o"]["value"],style="width:600px; height:500px;",frameborder="0")
                        elif row["o"]["value"][0:4] == 'http':
                            a(olabel,href = row["o"]["value"].replace('http://kenchreai.org',''))
                        else:
                            span(olabel)
                
                if more == True:
                    if len(moreresult["results"]["bindings"]) > 0:
                        dt('Linked to', style="margin-top:.75em", title="All linked resources"  )
                        curlabel = ''
                        first = 0
                        with dd(style="margin-top:1em"):
                            for row in moreresult["results"]["bindings"]:
                                if "olabel" in row.keys():
                                    label = row["olabel"]["value"]
                                else:
                                    label = re.sub('http://kenchreai.org/kaa/','kaa:',row["o"]["value"])
                            
                                if curlabel != label:
                                    curlabel = label
                                    if first == 1:
                                        first = 0
                                        pstyle = ''
                                    else:
                                        pstyle = 'border-top: thin dotted #aaa'   
                                                            
                                    p(a(label, style=pstyle, rel="dcterms:hasPart", href = row["o"]["value"].replace('http://kenchreai.org','')))
      
                                if 'othumb' in row.keys():
                                    thumb = row["othumb"]["value"]
                                    if '/' in thumb:
                                        thumb = re.sub(r"(/[^/]+$)",r"/thumbs\1",thumb)
                                    else:
                                        thumb = 'thumbs/' + thumb
                                    a(img(style="margin-left:1em;margin-bottom:15px;max-width:150px;max-height:150px",src="http://kenchreai-archaeological-archive-files.s3-website-us-west-2.amazonaws.com/%s" % thumb), href = row["o"]["value"].replace('http://kenchreai.org',''))

                if more == False:
                                    
                    if len(physicalresult["results"]["bindings"]) > 0:
                        dt('Has physical parts', style="margin-top:.75em", title="A list of resources that are best understood as being a physical part of this resource. Includes such relationships as Excavation Trench within an Area or Notebook page in a notebook."  )
                        curlabel = ''
                        first = 0
                        # compile all URIs for "physically part of" resources into a single dd element
                        # issue: i'd like to be able to indicate how many resources are parts. It's not 
                        # len(physical["results"]["bindings"]) as that repeats ?s
                        with dd(style="margin-top:1em"):
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
                                    if '/' in thumb:
                                        thumb = re.sub(r"(/[^/]+$)",r"/thumbs\1",thumb)
                                    else:
                                        thumb = 'thumbs/' + thumb
                                    a(img(style="margin-left:1em;margin-bottom:15px;max-width:150px;max-height:150px",src="http://kenchreai-archaeological-archive-files.s3-website-us-west-2.amazonaws.com/%s" % thumb), href = row["s"]["value"].replace('http://kenchreai.org',''))


                    if len(conceptualresult["results"]["bindings"]) > 0:
                        dt('Linked to', style="margin-top:.75em", title = "A list of resource that link back to the current resource. Used to display such relationships as Excavation Notebooks being documentation of Areas, Typological Identification of a particular object, Narrower terms in the archaeological typology, or assocaition with a Chronological period or modern year.")
                        curlabel = ''
                        first = 0
                        # compile all URIs for "logically part of" resources into a single dd element
                        # issue: i'd like to be able to indicate how many resources are linked to. It's not 
                        # len(conceptualresult["results"]["bindings"]) as that repeats ?s
                        with dd(style="margin-top:1em"):
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
                                    a(img(style="margin-left:1em;margin-bottom:15px;max-width:150px;max-height:150px",src="http://kenchreai-archaeological-archive-files.s3-website-us-west-2.amazonaws.com/%s" % thumb), href = row["s"]["value"].replace('http://kenchreai.org',''))
                                
    
                    dt('Suggested citation', style="margin-top:.5em")
                    # dd(raw("The American Excavations at Kenchreai. “{}.” <i>The Kenchreai Archaeological Archive</i>. {}. &lt;http://kenchreai.org/{}&gt;".format(pagelabel, strftime('%d %b. %Y'),kaapath)), style="margin-top:.5em")
                    if kaapath == 'kaa':
                      dd(raw("J.L. Rife and S. Heath (Eds.). (2013-{}). <i>The Kenchreai Archaeological Archive</i>. The American Excavations at Kenchreai. Retrieved from &lt;http://kenchreai.org/kaa&gt;".format(strftime('%Y'))), style="margin-top:.5em")
                    else:
                        dd(raw("“{}.” In <i>The Kenchreai Archaeological Archive</i>, edited by J.L. Rife and S. Heath. The American Excavations at Kenchreai, 2013-{}. &lt;http://kenchreai.org/{}&gt;".format(pagelabel.rstrip(), strftime('%Y'),kaapath)), style="margin-top:.5em")

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
                    (?l ?score) <tag:stardog:api:property:textMatch> ( '%s' 2000).
                    ?s ?p ?l . 
                    ?s rdfs:label ?slabel .
                    OPTIONAL { ?s kaaont:drawing|kaaont:photograph ?sthumb . FILTER regex(?sthumb, '(jpg|png)$') }
                    } ORDER BY ?s ?slabel""" % (q)

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
                               li(a('"Asia Minor"', href="/api/full-text-search?q=%22Asia%20Minor%22"))

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
                            a(img(style="margin-left:1em;margin-bottom:15px;max-width:150px;max-height:150px",src="http://kenchreai-archaeological-archive-files.s3-website-us-west-2.amazonaws.com/%s" % thumb),href=row["s"]["value"].replace('http://kenchreai.org',''))

    kaafooter(ftdoc)

    return ftdoc.render()


@app.route('/api/display-image-file')
def display_image_file():

    q = request.args.get('q')
    
    if q != '' and q is not None:
        qexists = True
    else:
        qexists = False

    if qexists == True:

        # q = q.replace(' ','%20')

        imgquery = """SELECT ?s ?slabel ?file ?p
               WHERE {
                   ?s ?p '%s' .
                   ?s rdfs:label ?slabel .
                   BIND ("%s" as ?file) 
               } ORDER BY ?s ?slabel ?p""" % (q,q)

        endpoint.setQuery(imgquery)
        endpoint.setReturnFormat(JSON)
        imgresult = endpoint.query().convert()

        imgdoc = dominate.document(title="Kenchreai Archaeological Archive: Image")
        kaaheader(imgdoc, '')

        imgdoc.body['prefix'] = "bibo: http://purl.org/ontology/bibo/  cc: http://creativecommons.org/ns#  dcmitype: http://purl.org/dc/dcmitype/  dcterms: http://purl.org/dc/terms/  foaf: http://xmlns.com/foaf/0.1/  nm: http://nomisma.org/id/  owl:  http://www.w3.org/2002/07/owl#  rdfs: http://www.w3.org/2000/01/rdf-schema#   rdfa: http://www.w3.org/ns/rdfa#  rdf:  http://www.w3.org/1999/02/22-rdf-syntax-ns#  skos: http://www.w3.org/2004/02/skos/core#"
        with imgdoc:
            comment(q)
            comment(imgquery)
            with nav(cls="navbar navbar-default navbar-fixed-top"):
               with div(cls="container-fluid"):
                   with div(cls="navbar-header"):
                       a("KAA: Image" , href="/kaa",cls="navbar-brand")
                       with form(cls="navbar-form navbar-left", role="search", action="/api/full-text-search"):
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
                                   li(a('"Asia Minor"', href="/api/full-text-search?q=%22Asia%20Minor%22"))

            with dl(cls="dl-horizontal"):

                if len(imgresult["results"]["bindings"]) > 0:

                    dt("Image of")
                    with dd():
                        for row in imgresult["results"]["bindings"]:
                            if 'slabel' in row.keys():
                                p(a(row["slabel"]["value"],href=row["s"]["value"].replace("http://kenchreai.org","")))
                            else:
                                p(row["s"]["value"])
                            imgsrc = row["file"]["value"]

                   #show the image itself
                    dt('')
                    dd(img(src="http://kenchreai-archaeological-archive-files.s3-website-us-west-2.amazonaws.com/%s" % imgsrc , style="width:100%"))
                    
                    # show the file name
                    dt('Filename', style="color:gray")
                    dd(imgsrc, style="color:gray")
                    
                else:
                    dt('Result')
                    dd('No image available for "%s"' % q)

        kaafooter(imgdoc)

        return imgdoc.render()
    
    else:
        return "Invalid query"

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
