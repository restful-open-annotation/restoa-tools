#!/usr/bin/env python

"""Export data from Open Annotation store over RESTful interface."""

__author__ = 'Sampo Pyysalo'
__license__ = 'MIT'

import os
import sys
import json
import codecs
import urlparse
import cgi

import requests

DEFAULT_ENCODING = 'utf-8'

# Key for the list of collection items in RESTful OA collection
# response.
ITEMS_KEY = '@graph'

# JSON-LD @type values recognized as identifying an OA annotation.
ANNOTATION_TYPES = [
    'oa:Annotation',
    'http://www.w3.org/ns/oa#Annotation',
]

def argparser():
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument('source', metavar='URL(s)', nargs='+',
                        help='URL(s) to export data from')
    parser.add_argument('-o', '--output', metavar='DIR', default=None,
                        help='Output directory.')
    parser.add_argument('-v', '--verbose', default=False, action='store_true',
                        help='Verbose output')
    return parser

class FormatError(Exception):
    pass

def prettyprint_json(obj, ascii=False):
    ppargs = { 'sort_keys': True, 'indent': 2, 'separators': (',', ': ') }
    if ascii:
        # default, returns ASCII with escapes
        return json.dumps(obj, **ppargs)
    else:
        # Unicode
        return json.dumps(obj, ensure_ascii=False, **ppargs)

def target_urls(annotations, target_key='target'):
    """Return list of unique target URLs for Open Annotation objects."""
    uniques = set()
    for annotation in annotations:
        targets = annotation[target_key]
        if isinstance(targets, basestring):
            targets = [targets]
        for target in targets:
            url = urlparse.urldefrag(target)[0]
            uniques.add(url)
    return list(uniques)

def get_encoding(response):
    """Return encoding from the Content-Type of the given response, or None
    if no encoding is specified."""
    # Based on get_encoding_from_headers in Python Requests utils.py.
    # Note: by contrast to the Python Requests implementation, we do
    # *not* here follow RFC 2616 and fall back to ISO-8859-1 (Latin 1)
    # in the absence of a "charset" parameter for "text" content
    # types, but simply return None.
    content_type = response.headers.get('Content-Type')
    if content_type is None:
        return None
    value, parameters = cgi.parse_header(content_type)
    if 'charset' not in parameters:
        return None
    return parameters['charset'].strip("'\"")

def get_plain_text(url, encoding=None):
    """Return plain text from given URL."""
    headers = { 'Accept': 'text/plain' }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    # check that we got what we wanted
    mimetype = response.headers.get('Content-Type')
    if not 'text/plain' in mimetype:
        raise ValueError('requested text/plain, got %s' % mimetype)
    # Strict RFC 2616 compliance (default to Latin 1 when no "charset"
    # given for text) can lead to misalignment issues when servers
    # fail to specify the encoding. To avoid this, check for missing
    # encodings and fall back on the apparent (charted detected)
    # encoding instead.
    if encoding is not None:
        response.encoding = encoding
    elif (get_encoding(response) is None and
          response.encoding.upper() == 'ISO-8859-1' and
          response.apparent_encoding != response.encoding):
        print >> sys.stderr, ('Breaking RFC 2616: using detected encoding (%s)'
                              'instead of default (%s)' %
                              (response.apparent_encoding, response.encoding))
        response.encoding = response.apparent_encoding
    return response.text

def fix_url(url):
    """Fix potentially broken or incomplete client-provided URL."""
    url = url.strip()
    def has_scheme(u):
        return u.startswith('http://') or u.startswith('https://')
    if not has_scheme(url):
        url = 'http://' + url
    return url

def is_collection(document):
    """Return True if JSON-LD document is a collection, False otherwise."""
    # TODO: use '@type' instead
    return ITEMS_KEY in document

def is_annotation(document):
    """Return True if JSON-LD document is an annotation, False otherwise."""
    # TODO: resolve by expanding JSON-LD
    if '@type' not in document:
        return False
    # Allow for more than one type
    if isinstance(document['@type'], list):
        types = document['@type']
    else:
        types = [document['@type']]
    return any(t for t in ANNOTATION_TYPES if t in types)

def output_text(text, url, options=None):
    if options is None or not options.output:
        print text
    else:
        path = urlparse.urlparse(url).path
        base = os.path.basename(path)
        outfn = os.path.join(options.output, base)
        with codecs.open(outfn, 'wt', encoding=DEFAULT_ENCODING) as out:
            print >> out, text

def output_annotations(annotations, url, options=None):
    if options is None or not options.output:
        print annotations
    else:
        outfn = os.path.join(options.output, 'annotations.jsonld')
        with codecs.open(outfn, 'wt', encoding=DEFAULT_ENCODING) as out:
            print >> out, annotations

def retrieve_texts(obj, options=None):
    """Retrieve Open Annotation target texts."""
    if is_collection(obj):
        annotations = obj[ITEMS_KEY]
    elif is_annotation(obj):
        annotations = [obj]
    for url in target_urls(annotations):
        text = get_plain_text(url)
        output_text(text, url, options)
        
def export_from(url, options=None):
    url = fix_url(url)
    headers = { 'Accept': 'application/ld+json' }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    try:
        document = response.json()
    except Exception, e:
        raise FormatError('failed to parse JSON')
    # TODO: rewrite targets to relative form
    # (e.g. "http://example.org/doc.txt" to "doc.txt")
    annotations = prettyprint_json(document)
    output_annotations(annotations, url, options)
    retrieve_texts(document, options)
    
def main(argv):
    args = argparser().parse_args(argv[1:])

    for source in args.source:
        export_from(source, args)
    
if __name__ == '__main__':
    sys.exit(main(sys.argv))
