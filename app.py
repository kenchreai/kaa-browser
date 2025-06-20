# This code needs more comments, no doubt about that.
# Distributed "AS IS"

import json
import logging
import os
import re
import urllib.parse
import urllib.request

import dominate

from bs4 import BeautifulSoup

from dominate.tags import *
from dominate.util import raw

from flask import Flask, make_response, request, Response, send_from_directory

from string import Template

import markdown

import pandas as pd

# from SPARQLWrapper import SPARQLWrapper, JSON

from time import *

import rdflib as rdf
from rdflib.plugins.stores import sparqlstore

# Don't show "More links" for these URIs. For the time being...
suppressmore = ['http://kenchreai.org/kaa',
                'http://kenchreai.org/kaa/eastern-mediterranean',
                'http://kenchreai.org/kaa/geographic-entities',
                'http://kenchreai.org/kaa/greece']

app = Flask(__name__, static_url_path='')
app.logger.setLevel(logging.DEBUG)

# 'endpoint' does not have reasoning enabled. 'reasoner' does.

endpoint_store = rdf.plugins.stores.sparqlstore.SPARQLStore(query_endpoint=os.environ.get('DB_KAA_ENDPOINT'),
                                                            context_aware=False,
                                                            returnFormat='json')

reasoner_store = rdf.plugins.stores.sparqlstore.SPARQLStore(query_endpoint=os.environ.get('DB_KAA_REASONER_ENDPOINT'),
                                                            context_aware=False,
                                                            returnFormat='json')

endpoint = rdf.Graph(endpoint_store)
reasoner = rdf.Graph(reasoner_store)


def format_citations(unformatted):
    p = r'\[@([^, ]+)((, ?[^\]]*)\]|\])'
    s = r'<a href="/kaa/zotero/\1">\1</a>\3'
    citation_html = re.sub(p, s, unformatted, flags=re.S)

    return citation_html


def kaaheader(doc, kaapath=''):

    doc.head += meta(charset="utf-8")
    doc.head += meta(http_equiv="X-UA-Compatible", content="IE=edge")
    doc.head += meta(name="viewport",
                     content="width=device-width, initial-scale=1")
    doc.head += link(rel='stylesheet', href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css",
                     integrity="sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u", crossorigin="anonymous")
    doc.head += link(rel="stylesheet", href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap-theme.min.css",
                     integrity="sha384-rHyoN1iRsVXV4nD0JutlnGaslCJuC7uwjduW9SVrLvRYooPp2bWYgmgJQIXwl/Sp", crossorigin="anonymous")
    doc.head += script(src="https://code.jquery.com/jquery-3.1.1.min.js")
    doc.head += script(src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js",
                       integrity="sha384-Tc5IQib027qvyjSMfHjOMaLkfuWVxZxUPnCJA7l2mCWNIpG9mGCD8wGNIcPD7Txa", crossorigin="anonymous")
    doc.head += style("""
@media print
{    
    .noprint *
    {
        display: none !important;
    }
    a[href]:after {
    content: none !important;
  }
}

.thumbnail-image {
    height: 13.5rem;
    width: auto;
}

.thumbnail-container {
}

.dl-horizontal dd {
    margin-bottom: .5em;
}

@media (min-width: 768px) {
    .dl-horizontal dd {
        margin-left: 19em;
    }
}

body { padding-top: 60px; }""")
    doc.head += meta(name="DC.title", lang="en", content="%s" % (kaapath))
    doc.head += meta(name="DC.identifier",
                     content="https://kenchreai.org/kaa/%s" % kaapath)


def kaafooter(doc, kaapath='', editorLink=False):
    with doc:
        with footer(cls="footer noprint"):
            with div(cls="container"):
                with p(cls="text-muted"):
                    span("©2017-2023 The ")
                    a("American Excavations at Kenchreai",
                      href="https://kenchreai.org")
                    span(
                        ". Data and images available for non-commercial, personal use only. See ")
                    a("Github", href="https://github.com/kenchreai/kaa-ttl")
                    span(" for Turtle (TRIG) formatted source files.")

                    if editorLink:
                        a("🔗", href="https://kenchreai-data-editor.herokuapp.com/detail/%s" % kaapath)


@app.route('/kaa/<path:kaapath>')
@app.route('/kaa')
def kaasparql(kaapath='kaa'):
    more = True

    if kaapath == 'kaa':
        uri = 'http://kenchreai.org/kaa'
    else:
        uri = 'http://kenchreai.org/kaa/' + kaapath

    # this query goes to the non-reasoning endpoint
    kaaquery = """PREFIX kaaont: <http://kenchreai.org/kaa/ontology/>

SELECT ?p ?o ?plabel ?pcomment ?pxorder ?olabel  WHERE
{ { <%s> ?p ?o .
 MINUS {?s kaaont:location ?o }
 MINUS {?s kaaont:observed ?o }
 MINUS {?s kaaont:same-as ?o }
 MINUS {?s kaaont:kaa-note ?o }
 MINUS {?s ?p <http://www.w3.org/2000/01/rdf-schema#Resource> }
 OPTIONAL  { ?p <http://www.w3.org/2000/01/rdf-schema#label> ?plabel .  }
 OPTIONAL  { ?p <http://www.w3.org/2000/01/rdf-schema#comment> ?pcomment .  }
 OPTIONAL  { ?p kaaont:x-sort-order ?pxorder .  }
 OPTIONAL  { ?o <http://www.w3.org/2000/01/rdf-schema#label> ?olabel . }
 OPTIONAL  { ?o <http://www.w3.org/2000/01/rdf-schema#label> ?olabel . }
 OPTIONAL  { ?p <http://www.w3.org/2000/01/rdf-schema#label> ?plabel . }
  }\
 UNION { <%s> kaaont:observed ?s . ?s ?p ?o . } } ORDER BY ?pxorder ?p ?plabel ?olabel ?o""" % (uri, uri)

    # endpoint.setQuery(kaaquery)
    # endpoint.setReturnFormat(JSON)
    kaaresult = endpoint.query(kaaquery).json

    if more == False:
        # This query should be passed to reasoner
        physicalquery = """PREFIX kaaont: <http://kenchreai.org/kaa/ontology/>
    SELECT  ?s ?p ?slabel ?sthumb WHERE
     { { <%s> <http://kenchreai.org/kaa/ontology/has-physical-part> ?s .
      OPTIONAL  { ?s <http://kenchreai.org/kaa/ontology/next> <%s> .
     ?s ?p <%s> }
     OPTIONAL  { ?s <http://www.w3.org/2000/01/rdf-schema#label> ?slabel . }
     OPTIONAL  { ?s <http://xmlns.com/foaf/0.1/name> ?slabel . }
     OPTIONAL { ?s kaaont:file|kaaont:pagescan|kaaont:photograph|kaaont:reverse-photograph|kaaont:obverse-photograph|kaaont:drawing ?sthumb . FILTER regex(?sthumb, '(jpg|png)$')  }
     } } ORDER BY ?s ?slabel""" % (uri, uri, uri)
        # reasoner.setQuery(physicalquery)
        # reasoner.setReturnFormat(JSON)
        physicalresult = reasoner.query(physicalquery).json

        # This query should be passed to reasoner
        conceptualquery = """PREFIX kaaont: <http://kenchreai.org/kaa/ontology/>

    SELECT  ?s ?p ?slabel ?sthumb WHERE
     { {  { ?s kaaont:is-logical-part-of <%s> . }
     UNION  { ?s kaaont:same-as <%s> .  }
     OPTIONAL  { ?s kaaont:next <%s> . ?s ?p <%s> }
     OPTIONAL  { ?s <http://www.w3.org/2000/01/rdf-schema#label> ?slabel . }\
     OPTIONAL { ?s kaaont:file|kaaont:pagescan|kaaont:photograph|kaaont:reverse-photograph|kaaont:obverse-photograph|kaaont:drawing ?sthumb . FILTER regex(?sthumb, '(jpg|png)$') } }
     FILTER (!isBlank(?s))  } ORDER BY ?slabel""" % (uri, uri, uri, uri)
        # reasoner.setQuery(conceptualquery)
        # reasoner.setReturnFormat(JSON)
        conceptualresult = reasoner.query(conceptualquery).json

    # This query should be passed to reasoner
    if more == True:
        morequery = """PREFIX kaaont: <http://kenchreai.org/kaa/ontology/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>


  SELECT DISTINCT ?s ?olabel ?othumb WHERE {
  ?s ?p <%s> .
  ?s rdfs:label ?olabel .
  ?s rdf:type ?otype .
   OPTIONAL { ?s kaaont:typological-identification ?otypology }
   OPTIONAL { ?s kaaont:file|kaaont:pagescan|kaaont:photograph|kaaont:reverse-photograph|kaaont:obverse-photograph|kaaont:drawing ?othumb . FILTER regex(?othumb, '(jpg|png)$') } 
   FILTER isIRI(?s)
   } ORDER BY ?otype ?s  LIMIT 12000""" % (uri)
        # reasoner.setQuery(morequery)
        # reasoner.setReturnFormat(JSON)
        moreresult = reasoner.query(morequery).json

    kaalabel = """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?slabel ?stype
           WHERE {
              <%s> rdfs:label ?slabel .
              OPTIONAL { <%s>  rdf:type/rdfs:label      ?stype . }
           }""" % (uri, uri)
    # endpoint.setQuery(kaalabel)
    # endpoint.setReturnFormat(JSON)
    labelresult = endpoint.query(kaalabel).json

    pagelabel = ''
    for result in labelresult["results"]["bindings"]:
        pagelabel = result["slabel"]["value"]
    if pagelabel == '':
        pagelabel = 'kaa:' + kaapath

    pagetype = ''
    for result in labelresult["results"]["bindings"]:
        if 'stype' in result.keys():
            pagetype = result["stype"]["value"]

    kaadoc = dominate.document(
        title="Kenchreai Archaeological Archive: %s" % (pagelabel))
    kaaheader(kaadoc, pagelabel)

    kaadoc.body['prefix'] = "bibo: http://purl.org/ontology/bibo/  cc: http://creativecommons.org/ns#  dcmitype: http://purl.org/dc/dcmitype/  dcterms: http://purl.org/dc/terms/  foaf: http://xmlns.com/foaf/0.1/  nm: http://nomisma.org/id/  owl:  http://www.w3.org/2002/07/owl#  rdfs: http://www.w3.org/2000/01/rdf-schema#   rdfa: http://www.w3.org/ns/rdfa#  rdf:  http://www.w3.org/1999/02/22-rdf-syntax-ns#  skos: http://www.w3.org/2004/02/skos/core#"
    with kaadoc:
        with nav(cls="navbar navbar-default navbar-fixed-top"):
            with div(cls="container-fluid"):
                with div(cls="navbar-header"):
                    a("Kenchreai Archaeological Archive",
                      href="/kaa", cls="navbar-brand")
                    # span(" [Note: kaa is temporarily 'under construction' so some functions may be unstable or unavailable.]")
                    with form(cls="navbar-form navbar-right", role="search", action="/api/full-text-search"):
                        with div(cls="form-group"):
                            input_(id="q", name="q", type="text",
                                   cls="form-control", placeholder="Search...")

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

                if pagetype != '':
                    dt("Type", style="white-space: nowrap; width:18em; margin-right:1em;")
                    dd(pagetype)

                for row in kaaresult["results"]["bindings"]:

                    if 'pcomment' in row.keys():
                        pcomment = "%s [%s]" % (row["pcomment"]["value"], row["p"]["value"].replace(
                            'http://kenchreai.org/kaa/ontology/', 'kaaont:'))
                    else:
                        pcomment = row["p"]["value"].replace(
                            'http://kenchreai.org/kaa/ontology/', 'kaaont:')

                    if row["p"]["value"] == 'http://www.w3.org/2000/01/rdf-schema#label':
                        continue
                    elif row["p"]["value"] == 'http://kenchreai.org/kaa/ontology/next':
                        next = row["o"]["value"]
                        continue
                    elif "plabel" in row.keys():
                        dt(row["plabel"]["value"],
                           style="white-space: nowrap; width:18em; margin-right:1em;", title=pcomment)
                    else:
                        dt(i(row["p"]["value"]),
                           style="white-space: normal; width:18em; margin-right:1em;")

                    with dd():
                        rkeys = row.keys()
                        if "olabel" in rkeys:
                            olabel = row["olabel"]["value"]
                        else:
                            olabel = row["o"]["value"]

                        if re.search('(\.png|\.jpg)$', row["o"]["value"], flags=re.I):
                            a(img(style="max-width:600px;max-height:350px", src="https://kaa-images.s3.us-east-2.amazonaws.com/%s" %
                              row["o"]["value"]), href="/api/display-image-file?q=%s" % row["o"]["value"])
                        elif re.search('(\.pdf|\.tif|\.tiff)$', row["o"]["value"], flags=re.I):
                            iframe(src="https://docs.google.com/gview?url=https://kaa-images.s3.us-east-2.amazonaws.com/%s&embedded=true" %
                                   row["o"]["value"], style="width:600px; height:500px;", frameborder="0")
                        elif row["o"]["value"][0:4] == 'http':
                            a(olabel, href=row["o"]["value"].replace(
                                'http://kenchreai.org', ''))
                        else:
                            span(olabel)

                if more == True:
                    if len(moreresult["results"]["bindings"]) > 0:
                        dt('Linked to', style="margin-top:.75em",
                           title="All linked resources", cls="noprint")
                        curlabel = ''
                        first = True
                        with dd(style="margin-top:1em", cls="noprint"):
                            linked_items = {}

                            for result in moreresult["results"]["bindings"]:
                                subject = result['s']['value']
                                item = {'thumbs': []}
                                try:
                                    item = linked_items[subject]
                                except KeyError:
                                    linked_items[subject] = item

                                if result.get('olabel'):
                                    item['label'] = result['olabel']['value']

                                if result.get('othumb'):
                                    item['thumbs'].append(
                                        result['othumb']['value'])

                            for subject, statements in linked_items.items():
                                label = statements.get('label')

                                if not label:
                                    label = re.sub(
                                        'http://kenchreai.org/kaa/', 'kaa:', row["o"]["value"])
                                thumbs = []

                                for url in statements['thumbs']:
                                    # if 'thumbs' in url and not 'thumbs' in url.split('/')[0]:
                                    if '/' in url and 'drawings' not in url:
                                        thumb = re.sub(
                                            r"(/[^/]+$)", r"/thumbs\1", url)
                                    else:
                                        thumb = 'thumbs/' + url
                                    thumbs.append(
                                        a(
                                            img(
                                                src='https://kaa-images.s3.us-east-2.amazonaws.com/%s' % thumb,
                                                cls='thumbnail-image'
                                            ),
                                            href=subject.replace(
                                                'http://kenchreai.org', ''),
                                            cls="noprint",
                                            style='display:contents;'
                                        )
                                    )

                                div(
                                    p(
                                        a(
                                            label,
                                            rel="dcterms:hasPart",
                                            href=subject.replace(
                                                'http://kenchreai.org', '')
                                        ),
                                        cls="noprint"
                                    ),
                                    div(thumbs, cls='thumbnail-container') if thumbs else '',
                                    style='margin-bottom: 4rem;'
                                )

                if more == False:

                    if len(physicalresult["results"]["bindings"]) > 0:
                        dt('Has physical parts', style="margin-top:.75em",
                           title="A list of resources that are best understood as being a physical part of this resource. Includes such relationships as Excavation Trench within an Area or Notebook page in a notebook.")
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
                                    label = re.sub(
                                        'http://kenchreai.org/kaa/', 'kaa:', row["s"]["value"])

                                if curlabel != label:
                                    curlabel = label
                                    if first == 1:
                                        first = 0
                                        pstyle = ''
                                    else:
                                        pstyle = 'border-top: thin dotted #aaa'

                                    p(a(label, style=pstyle, rel="dcterms:hasPart", href=row["s"]["value"].replace(
                                        'http://kenchreai.org', '')))

                                if 'sthumb' in row.keys():
                                    thumb = row["sthumb"]["value"]
                                    if '/' in thumb:
                                        thumb = re.sub(
                                            r"(/[^/]+$)", r"/thumbs\1", thumb)
                                    else:
                                        thumb = 'thumbs/' + thumb
                                    a(img(style="margin-left:1em;margin-bottom:15px;max-width:150px;max-height:150px",
                                      src="https://kaa-images.s3.us-east-2.amazonaws.com/%s" % thumb), href=row["s"]["value"].replace('http://kenchreai.org', ''))

                    if len(conceptualresult["results"]["bindings"]) > 0:
                        dt('Linked to', style="margin-top:.75em", title="A list of resource that link back to the current resource. Used to display such relationships as Excavation Notebooks being documentation of Areas, Typological Identification of a particular object, Narrower terms in the archaeological typology, or assocaition with a Chronological period or modern year.", cls="noprint")
                        curlabel = ''
                        first = 0
                        # compile all URIs for "logically part of" resources into a single dd element
                        # issue: i'd like to be able to indicate how many resources are linked to. It's not
                        # len(conceptualresult["results"]["bindings"]) as that repeats ?s
                        with dd(style="margin-top:1em", cls="noprint"):
                            for row in conceptualresult["results"]["bindings"]:
                                if 'slabel' in row.keys():
                                    label = row["slabel"]["value"]
                                else:
                                    label = re.sub(
                                        'http://kenchreai.org/kaa/', 'kaa:', row["s"]["value"])

                                if curlabel != label:
                                    curlabel = label
                                    if first == 1:
                                        first = 0
                                        pstyle = ''
                                    else:
                                        pstyle = 'border-top: thin dotted #aaa;'

                                    p(a(label, style=pstyle, rel="dcterms:hasPart", href=row["s"]["value"].replace(
                                        'http://kenchreai.org', '')))

                                if 'sthumb' in row.keys():
                                    thumb = row["sthumb"]["value"]
                                    if '/' in thumb:
                                        thumb = re.sub(
                                            r"(/[^/]+$)", r"/thumbs\1", thumb)
                                    else:
                                        thumb = 'thumbs/' + thumb
                                    a(img(style="margin-left:1em;margin-bottom:15px;max-width:150px;max-height:150px",
                                      src="https://kaa-images.s3.us-east-2.amazonaws.com/%s" % thumb), href=row["s"]["value"].replace('http://kenchreai.org', ''))

                    dt('Suggested citation', style="margin-top:.5em", cls="noprint")
                    # dd(raw("The American Excavations at Kenchreai. “{}.” <i>The Kenchreai Archaeological Archive</i>. {}. &lt;http://kenchreai.org/{}&gt;".format(pagelabel, strftime('%d %b. %Y'),kaapath)), style="margin-top:.5em")
                    if kaapath == 'kaa':
                        with dd(cls="noprint"):
                            div(raw("J.L. Rife and S. Heath, eds. (2013-{}). <i>Kenchreai Archaeological Archive</i>. The American Excavations at Kenchreai. &lt;https://kenchreai.org/kaa&gt;".format(
                                strftime('%Y'))), style="margin-top:.5em;margin-left:1.25em;text-indent:-1.25em")
                    else:
                        with dd():
                            div(raw("“{}.” In <i>Kenchreai Archaeological Archive</i>, edited by J.L. Rife and S. Heath. The American Excavations at Kenchreai, 2013-{}. &lt;https://kenchreai.org/{}&gt;".format(
                                pagelabel.rstrip(), strftime('%Y'), kaapath)), style="margin-top:.5em;margin-left:1.25em;text-indent:-1.25em")

    kaafooter(kaadoc, kaapath, True)

    if next is not None:
        soup = BeautifulSoup(kaadoc.render(), "html.parser")
        asoup = BeautifulSoup('[<a href="%s">next</a>]' %
                              next.replace('http://kenchreai.org', ''), 'html.parser')
        tag = soup.find(id='next')
        tag.append(asoup)

        pre_citation = str(soup)

        citation_html = format_citations(pre_citation)

        return citation_html
    else:

        pre_citation = kaadoc.render()

        citation_html = format_citations(pre_citation)

        return citation_html


@app.route('/api/full-text-search')
def fulltextsearch():
    q = request.args.get('q')

    if q != '' and q is not None:
        qexists = True
    else:
        qexists = False

    if qexists == True:

        q = q.lower().replace(' and ', ' AND ')

        ftquery = """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX text: <http://jena.apache.org/text#>
PREFIX kaaont: <http://kenchreai.org/kaa/ontology/>


SELECT ?s ?slabel
WHERE { 
    ?s text:query (rdfs:label '%s') ;
       rdfs:label ?slabel .
} ORDER BY ?s""" % (q)
        # endpoint.setQuery(ftquery)
        # endpoint.setReturnFormat(JSON)
        ftresult = endpoint.query(ftquery).json

    ftdoc = dominate.document(
        title="Kenchreai Archaeological Archive: Full-Text Search")
    kaaheader(ftdoc, '')

    ftdoc.body['prefix'] = "bibo: http://purl.org/ontology/bibo/  cc: http://creativecommons.org/ns#  dcmitype: http://purl.org/dc/dcmitype/  dcterms: http://purl.org/dc/terms/  foaf: http://xmlns.com/foaf/0.1/  nm: http://nomisma.org/id/  owl:  http://www.w3.org/2002/07/owl#  rdfs: http://www.w3.org/2000/01/rdf-schema#   rdfa: http://www.w3.org/ns/rdfa#  rdf:  http://www.w3.org/1999/02/22-rdf-syntax-ns#  skos: http://www.w3.org/2004/02/skos/core#"
    with ftdoc:
        with nav(cls="navbar navbar-default navbar-fixed-top"):
            with div(cls="container-fluid"):
                with div(cls="navbar-header"):
                    a("KAA: Full-Text Search", href="/kaa", cls="navbar-brand")
                    with form(cls="navbar-form navbar-left", role="search"):
                        with div(cls="form-group"):
                            input_(id="q", name="q", type="text",
                                   cls="form-control", placeholder="Search...")
                    # with ul(cls="nav navbar-nav"):
                    #   with li(cls="dropdown"):
                      #      a("Example Searches", href="#",cls="dropdown-toggle", data_toggle="dropdown")
                       #     with ul(cls="dropdown-menu", role="menu"):
                        #        li(a('+ke +1221', href="/api/full-text-search?q=%2Bke%20%2B1221"))
                        #        li(a('+corinthian +lamp', href="/api/full-text-search?q=%2Bcorinthian%20%2Blamp"))
                        #       li(a('+gold -ring', href="/api/full-text-search?q=%2Bgold%20%2Dring"))
                        #       li(a('"ke 1221"', href="/api/full-text-search?q=%22ke%201221%22"))
                        #       li(a('fish*', href="/api/full-text-search?q=fish%2A"))
                        #       li(a('ΔΙΟΝΕΙΚΟΥ', href="/api/full-text-search?q=ΔΙΟΝΕΙΚΟΥ"))
                          #      li(a('"Asia Minor"', href="/api/full-text-search?q=%22Asia%20Minor%22"))

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
                            label = re.sub(
                                'http://kenchreai.org/kaa/', 'kaa:', row["s"]["value"])

                        if curlabel != label:
                            curlabel = label
                            if first == 1:
                                first = 0
                                pstyle = ''
                            else:
                                pstyle = 'border-top: thin dotted #aaa;'

                            p(a(row["slabel"]["value"], style=pstyle, href=row["s"]["value"].replace(
                                'http://kenchreai.org', '')))

                        if 'sthumb' in row.keys():
                            thumb = row["sthumb"]["value"]
                            if '/' in thumb:
                                thumb = re.sub(
                                    r"(/[^/]+$)", r"/thumbs\1", thumb)
                            else:
                                thumb = 'thumbs/' + thumb
                            a(img(style="margin-left:1em;margin-bottom:15px;max-width:150px;max-height:150px",
                              src="https://kaa-images.s3.us-east-2.amazonaws.com/%s" % thumb), href=row["s"]["value"].replace('http://kenchreai.org', ''))

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

        imgquery = """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?s ?slabel ?file ?p
               WHERE {
                   ?s ?p '%s' .
                   OPTIONAL { ?s rdfs:label ?slabel . }
                   BIND ("%s" as ?file) 
               } ORDER BY ?s ?slabel ?p""" % (q, q)

        # endpoint.setQuery(imgquery)
        # endpoint.setReturnFormat(JSON)
        imgresult = endpoint.query(imgquery).json

        imgdoc = dominate.document(
            title="Kenchreai Archaeological Archive: Image")
        kaaheader(imgdoc, '')

        imgdoc.body['prefix'] = "bibo: http://purl.org/ontology/bibo/  cc: http://creativecommons.org/ns#  dcmitype: http://purl.org/dc/dcmitype/  dcterms: http://purl.org/dc/terms/  foaf: http://xmlns.com/foaf/0.1/  nm: http://nomisma.org/id/  owl:  http://www.w3.org/2002/07/owl#  rdfs: http://www.w3.org/2000/01/rdf-schema#   rdfa: http://www.w3.org/ns/rdfa#  rdf:  http://www.w3.org/1999/02/22-rdf-syntax-ns#  skos: http://www.w3.org/2004/02/skos/core#"
        with imgdoc:
            comment(q)
            comment(imgquery)
            with nav(cls="navbar navbar-default navbar-fixed-top"):
                with div(cls="container-fluid"):
                    with div(cls="navbar-header"):
                        a("KAA: Image", href="/kaa", cls="navbar-brand")
                        with form(cls="navbar-form navbar-left", role="search", action="/api/full-text-search"):
                            with div(cls="form-group"):
                                input_(id="q", name="q", type="text",
                                       cls="form-control", placeholder="Search...")
                        with ul(cls="nav navbar-nav"):
                            with li(cls="dropdown"):
                                a("Example Searches", href="#",
                                  cls="dropdown-toggle", data_toggle="dropdown")
                                with ul(cls="dropdown-menu", role="menu"):
                                    li(a(
                                        '+ke +1221', href="/api/full-text-search?q=%2Bke%20%2B1221"))
                                    li(a(
                                        '+corinthian +lamp', href="/api/full-text-search?q=%2Bcorinthian%20%2Blamp"))
                                    li(a(
                                        '+gold -ring', href="/api/full-text-search?q=%2Bgold%20%2Dring"))
                                    li(a(
                                        '"ke 1221"', href="/api/full-text-search?q=%22ke%201221%22"))
                                    li(a('fish*', href="/api/full-text-search?q=fish%2A"))
                                    li(a(
                                        'ΔΙΟΝΕΙΚΟΥ', href="/api/full-text-search?q=ΔΙΟΝΕΙΚΟΥ"))
                                    li(a(
                                        '"Asia Minor"', href="/api/full-text-search?q=%22Asia%20Minor%22"))

            with dl(cls="dl-horizontal"):

                if len(imgresult["results"]["bindings"]) > 0:

                    dt("Image of")
                    with dd():
                        for row in imgresult["results"]["bindings"]:
                            if 'slabel' in row.keys():
                                p(a(row["slabel"]["value"], href=row["s"]["value"].replace(
                                    "http://kenchreai.org", "")))
                            else:
                                p(row["s"]["value"])
                            imgsrc = row["file"]["value"]

                    # show the image itself
                    dt('')
                    dd(img(src="https://kaa-images.s3.us-east-2.amazonaws.com/%s" %
                       imgsrc, style="width:100%"))

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
           }""" % (entity, entity), initNs=ns)

    if len(geojsonr) > 0:
        for row in geojsonr:
            pass


def format_kaa_reference(match):
    endpoint_store = rdf.plugins.stores.sparqlstore.SPARQLStore(
        query_endpoint=os.environ.get('DB_KAA_ENDPOINT'),
        context_aware=False)
    # returnFormat = 'json')
    g = rdf.Graph(endpoint_store)

    groups = match.groups()

    describe_query = f"DESCRIBE <http://kenchreai.org/kaa/{groups[0]}>"
    results = g.query(describe_query)

    [[str(x[1]), str(x[2])] for x in results]

    link = f'<a href="/kaa/{groups[0]}">{groups[0]}</a>'

    txt = f'''{link}
    
    '''

    # + json.dumps([[str(x[1]),str(x[2])] for x in results])

    return txt


@app.route('/catalogs/<path:catalog_id>')
def kaacatalog(catalog_id):
    catalog_text_url = f'http://kenchreai.github.io/kaa-catalogs/{catalog_id}.md'
    with urllib.request.urlopen(catalog_text_url) as response:
        unformatted_txt = response.read().decode('utf-8')

    pattern = r'\[urn:kaa:([^ \]]+?) (([^\]]+?)]|\])'

    occurrence_tuples = re.findall(pattern, unformatted_txt)
    occurences = [x[0] for x in occurrence_tuples]

    identifiers = '> <http://kenchreai.org/kaa/'.join(
        [x[0] for x in occurrence_tuples])
    identifiers = f'<http://kenchreai.org/kaa/{identifiers}>'

    store = rdf.plugins.stores.sparqlstore.SPARQLStore(query_endpoint=os.environ.get('DB_KAA_ENDPOINT'),
                                                       context_aware=False,
                                                       returnFormat='json')
    g = rdf.Graph(store)
    qt = Template("""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT *  WHERE {
    VALUES ?s { $identifiers }
    ?s ?p ?o .
    ?s rdfs:label ?slabel .
    OPTIONAL { ?o rdfs:label ?olabel }
    OPTIONAL { ?p rdfs:label ?plabel }
    }
""")

    results = g.query(qt.substitute(identifiers=identifiers))
    ids_df = pd.DataFrame(results, columns=results.json['head']['vars'])
    ids_df = ids_df.applymap(str)
    ids_df.set_index('s', inplace=True)

    urn_html_dict = {}
    for o in occurrence_tuples:
        urn_html_dict[f'http://kenchreai.org/kaa/{o[0]}'] = format_kaa_reference_from_df(
            ids_df.loc[f'http://kenchreai.org/kaa/{o[0]}'], o[2])

    pre_md = re.sub(r'\[urn:kaa:([^ \]]+?)( ([^\]]+?)]|])',
                    lambda match: urn_html_dict[f'http://kenchreai.org/kaa/{match.groups()[0]}'], unformatted_txt)
    as_md = markdown.markdown(pre_md)

    cat_doc = dominate.document(title="Catalog")
    cat_doc.head += link(rel='stylesheet',
                         href="http://jasonm23.github.io/markdown-css-themes/markdown.css")
    with cat_doc:
        with body():
            raw(as_md)

    return cat_doc.render()


def format_kaa_reference_from_df(df, label):
    # get subject
    url = df.index[0]

    # since subject all the same, predicate is the useful index
    df.set_index('p', inplace=True)

    est_rim_diam = ''
    if 'http://kenchreai.org/kaa/ontology/rim-diameter-estimated' in df.index:
        est_rim_diam = df.loc['http://kenchreai.org/kaa/ontology/rim-diameter-estimated']['o']
        if isinstance(est_rim_diam, pd.Series):
            est_rim_diam = " ".join(est_rim_diam.to_list())
        est_rim_diam = f'Est. rim diam. {est_rim_diam}.'

    rim_diam = ''
    if 'http://kenchreai.org/kaa/ontology/rim-diameter' in df.index:
        rim_diam = df.loc['http://kenchreai.org/kaa/ontology/rim-diameter']['o']
        if isinstance(rim_diam, pd.Series):
            rim_diam = " ".join(rim_diam.to_list())
        rim_diam = f'Rim diam. {rim_diam}.'

    measurements = f"{' '.join([est_rim_diam, rim_diam])}"

    description = ''
    if 'http://kenchreai.org/kaa/ontology/description' in df.index:
        description = df.loc['http://kenchreai.org/kaa/ontology/description']['o']
        if isinstance(description, pd.Series):
            description = " ".join(description.to_list())

    fabric = ''
    if 'http://kenchreai.org/kaa/ontology/fabric-description' in df.index:
        fabric = df.loc['http://kenchreai.org/kaa/ontology/fabric-description']['o']
        if isinstance(fabric, pd.Series):
            fabric = " ".join(fabric.to_list())

    preservation = ''
    if 'http://kenchreai.org/kaa/ontology/preservation-comment' in df.index:
        preservation = df.loc['http://kenchreai.org/kaa/ontology/preservation-comment']['o']
        if isinstance(preservation, pd.Series):
            preservation = " ".join(preservation.to_list())

    published_as = ''
    if 'http://kenchreai.org/kaa/ontology/published-as' in df.index:
        published_as = df.loc['http://kenchreai.org/kaa/ontology/published-as']['o']
        if isinstance(published_as, pd.Series):
            published_as = " ".join(published_as.to_list())
        published_as = f'<div style="margin-top:.5em"><i>Published as:</i> {format_citations(published_as)}</div>'

    comparanda = ''
    if 'http://kenchreai.org/kaa/ontology/comparanda' in df.index:
        comparanda = df.loc['http://kenchreai.org/kaa/ontology/comparanda']['o']
        if isinstance(comparanda, pd.Series):
            comparanda = " ".join(comparanda.to_list())
        comparanda = f'<div><i>Comparanda:</i> {format_citations(comparanda)}</div>'

    bibliography = ''
    if 'http://kenchreai.org/kaa/ontology/bibliography' in df.index:
        bibliography = df.loc['http://kenchreai.org/kaa/ontology/bibliography']['o']
        if isinstance(bibliography, pd.Series):
            bibliography = " ".join(bibliography.to_list())
        bibliography = f'<div style="margin-top:.5em"><i>Bibliography:</i> {format_citations(bibliography)}</div>'

    drawings = ''
    if 'http://kenchreai.org/kaa/ontology/drawing' in df.index:
        drawings = df.loc['http://kenchreai.org/kaa/ontology/drawing']['o']
        if isinstance(drawings, pd.Series):
            drawings = " ".join(
                [f'<img src="https://kaa-images.s3.us-east-2.amazonaws.com/thumbs/{i}">' for i in drawings.to_list()])
        else:
            if '/' in drawings:
                drawings = re.sub(r"(/[^/]+$)", r"/thumbs\1", drawings)
            else:
                drawings = 'thumbs/' + drawings
            drawings = f'<img src="https://kaa-images.s3.us-east-2.amazonaws.com/{drawings}">'

    photographs = ''
    if 'http://kenchreai.org/kaa/ontology/photograph' in df.index:
        photographs = df.loc['http://kenchreai.org/kaa/ontology/photograph']['o']
        if isinstance(photographs, pd.Series):
            photographs = " ".join(
                [f'<img src="https://kaa-images.s3.us-east-2.amazonaws.com/thumbs/{i}">' for i in photographs.to_list()])
        else:
            if '/' in photographs:
                photographs = re.sub(r"(/[^/]+$)", r"/thumbs\1", photographs)
            else:
                photographs = 'thumbs/' + photographs
            photographs = f'<img src="https://kaa-images.s3.us-east-2.amazonaws.com/{photographs}">'

    descriptive_fields = [description, fabric, preservation]

    return f'''
    <div class="kaa_entry" style="margin-top:.75em">
        <div><a href="{url}">{label}</a>: {measurements}</div>
        <div>{" ".join(descriptive_fields)}</div>
        {published_as}
        {comparanda}
        {bibliography}
        <div class="kaa_illustrations" style="margin-top:.5em">{drawings} {photographs}</div>
    </div>'''.replace('\n', '')  # markdown wants this all on one line. and resonably so.


def kaacatalog_old(catalog_id):

    endpoint_store = rdf.plugins.stores.sparqlstore.SPARQLStore(query_endpoint="http://kenchreai.org:3030/kaa_endpoint/sparql",
                                                                context_aware=False,
                                                                returnFormat='json')

    catalog_text_url = f'http://kenchreai.github.io/kaa-catalogs/{catalog_id}.md'

    with urllib.request.urlopen(catalog_text_url) as response:
        unformatted_txt = response.read().decode('utf-8')

    pre_md = re.sub(r'\[urn:kaa:([^ \]]+?)( ([^\]]+?)]|])',
                    format_kaa_reference, unformatted_txt)
    as_md = markdown.markdown(pre_md)

    cat_doc = dominate.document(title="Catalog")
    cat_doc.head += link(rel='stylesheet',
                         href="http://jasonm23.github.io/markdown-css-themes/markdown.css")
    with cat_doc:
        body(raw(as_md))

    return cat_doc.render()


def kthcatalog():
    endpoint_store = rdf.plugins.stores.sparqlstore.SPARQLStore(query_endpoint=os.environ.get('DB_KAA_ENDPOINT'),
                                                                context_aware=False,
                                                                returnFormat='json')
    with urllib.request.urlopen('http://kenchreai.github.io/kaa-catalogs/kth-catalog.md') as response:
        txt = response.read().decode('utf-8')

    kthcatquery = '''PREFIX kaaont: <http://kenchreai.org/kaa/ontology/>
    SELECT ?s ?p ?o  WHERE {
  ?s kaaont:comment "KTHPUBCAT" .
  ?s ?p ?o }'''

    endpoint.setQuery(kthcatquery)
    endpoint.setReturnFormat(JSON)
    result = endpoint.query().convert()

    df = pd.DataFrame(result['results']['bindings'])
    df = df.applymap(lambda x: x['value'])

    html = """
<html>
<head>
<style>
body {
 margin:auto;
 width:70%;
 }
 
 p {
  text-indent:0;
  padding:0;
  margin: 0;
  line-height:1.2em;
  text-align: justify;
  font-size:11pt;
  font-family: Cambria
}

a {
  border-bottom:thin dotted gray;
  color:black;
  text-decoration:none;
}

h1 {
  font-size:1.5em;
  text-align:center
}

h2 {
  margin-top:1em;
  margin-bottom:.2em;
  font-size:1em;
  font-weight:bold;
  text-align:left;
  padding:0;
}

h3,h4 {
  margin-top:1em;
  margin-bottom:0;
  font-size:1em;
  font-weight:normal;
  font-style:italic;
  text-align:left;
  padding:0;
}

</style>
</head>
<body>"""
    entry_counter = 0
    for l in txt.splitlines():
        if l[0:3] == 'kth':
            entry_counter += 1
            id = l.split(" ", 1)
            html += f'<p><i>{entry_counter}</i>. {id[1]} (<a style="plain" href="{kth}{id[0]}" target="_new">{id[0]}</a>)</p>'

            dims = ""
            try:
                tmp = df.query(
                    f'(s == "{kth}{id[0]}") & (p == "http://kenchreai.org/kaa/ontology/rim-diameter-estimated")').o
                tmp = list(tmp)[0]
                dims += f'Est. D. {tmp}'
            except Exception:
                pass

            if len(dims) > 0:
                html += f'<p>{dims}</p>'

            # preservation
            try:
                tmp = df.query(
                    f'(s == "{kth}{id[0]}") & (p == "http://kenchreai.org/kaa/ontology/preservation-comment")').o
                tmp = list(tmp)[0]
                html += f'<p>{tmp}</p>'
            except Exception:
                pass

            # description
            try:
                tmp = df.query(
                    f'(s == "{kth}{id[0]}") & (p == "http://kenchreai.org/kaa/ontology/description")').o
                tmp = list(tmp)[0]
                html += f'<p>{tmp}</p>'
            except Exception:
                pass

            # fabric
            try:
                tmp = df.query(
                    f'(s == "{kth}{id[0]}") & (p == "http://kenchreai.org/kaa/ontology/fabric-description")').o
                tmp = list(tmp)[0]
                html += f'<p>{tmp}</p>'
            except Exception:
                pass

            # drawing
            try:
                thumb = df.query(
                    f'(s == "{kth}{id[0]}") & (p == "http://kenchreai.org/kaa/ontology/drawing")').o
                thumb = list(thumb)[0]

                if '/' in thumb:
                    thumb = re.sub(r"(/[^/]+$)", r"/thumbs\1", thumb)
                else:
                    thumb = 'thumbs/' + thumb

                html += f'<img src="https://kaa-images.s3.us-east-2.amazonaws.com/{thumb}"/>'
            except Exception:
                pass

            # photograph
            try:
                thumb = df.query(
                    f'(s == "{kth}{id[0]}") & (p == "http://kenchreai.org/kaa/ontology/photograph")').o
                thumb = list(thumb)[0]

                if '/' in thumb:
                    thumb = re.sub(r"(/[^/]+$)", r"/thumbs\1", thumb)
                else:
                    thumb = 'thumbs/' + thumb

                html += f'<img src="https://kaa-images.s3.us-east-2.amazonaws.com/{thumb}"/>'
            except Exception:
                pass
            finally:
                html += '<br/>'

            html += '<br/>'
        else:
            html += f'{l}'

    pre_citation_html += "</body></html>"

    p = r'\[@([^, ]+)((, ?[^\]]*)\]|\])'
    s = r'<a href="/zotero/\1">\1</a>\3'
    html = re.sub(p, s, pre_citation_html, flags=re.S)

    return html


@app.route('/api/dbproxy/<path:endpoint>', methods=['GET', 'POST'])
def db_proxy(endpoint):
    if (request.method != 'GET' and
       request.headers.get('X-Front-Door-Key') != os.environ.get('FRONT_DOOR_KEY')):
        return Response('Endpoint is public GET only', 401)

    if request.method == 'GET':
        url = os.environ.get('DB_KAA_ENDPOINT') + \
            '?query=' + urllib.parse.quote(request.args.get('query'))
        req = urllib.request.Request(url)
        if request.headers.get('Accept'):
            req.add_header('Accept', request.headers.get('Accept'))

        response = urllib.request.urlopen(req)
        body = response.read().decode('utf-8')
        res = make_response(body, 200)

        if 'sparql-results+json' in response.headers.get('Content-Type'):
            res.headers['Content-Type'] = 'application/sparql-results+json'
        return res

    if request.method == 'POST' and endpoint == 'update':
        data = urllib.parse.urlencode(
            {'update': request.form.get('update')}).encode('utf-8')
        req = urllib.request.Request(
            os.environ.get('DB_KAA_UPDATE_ENDPOINT'), data=data, method='POST')
        req.add_header('Accept', 'application/json')
        req.add_header('Authorization', request.headers.get('Authorization'))
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        response = urllib.request.urlopen(req).read()
        return response
    return '{}'


@app.route('/')
def index():
    return send_from_directory('static', 'index.html')
