#!/usr/bin/env python

"""Import data to Open Annotation store over RESTful interface.

Example usage:

    python import.py data/examples/craft/12925238.jsonld

(requires a running local RESTful Open Annotation server)
"""

__author__ = 'Sampo Pyysalo'
__license__ = 'MIT'

import os
import sys
import urllib2
import codecs
import json

from os import path

import requests

DEFAULT_URL='http://127.0.0.1:5000/annotations/'
DEFAULT_ENCODING='utf-8'

def argparser():
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument('source', metavar='FILE/DIR', nargs='+',
                        help='Source data to import')
    parser.add_argument('-v', '--verbose', default=False, action='store_true',
                        help='Verbose output')
    parser.add_argument('-u', '--url', default=DEFAULT_URL,
                        help='URL for store (default %s)' % DEFAULT_URL)
    parser.add_argument('-q', '--quiet', default=False, action='store_true',
                        help='No output')
    return parser

def pretty(doc):
    """Pretty-print JSON."""
    return json.dumps(doc, sort_keys=True, indent=2, separators=(',', ': '))

def read_file(source):
    with codecs.open(source, encoding=DEFAULT_ENCODING) as f:
        text = f.read()
    return json.loads(text)

def pretty_response_text(response):
    try:
        return pretty(response.json())
    except ValueError:
        return response.text

def process_response(document, response, options):
    """Report on response and return True on success, False on error."""
    try:
        response.raise_for_status()
        if options is not None and options.verbose:
            print response.status_code
            print pretty_response_text(response)
        return True
    except requests.exceptions.HTTPError as error:
        if options is None or not options.quiet:
            print error.message
            print pretty(document)
            print pretty_response_text(response)
        return False

def prepare_document_for_POST(document):
    """Make any modifications that may be necessary to POST document to a
    RESTful Open Annotation store."""
    # TODO: reconsider whether to allow @id in POSTed documents.
    if '@id' in document:
        del document['@id']
    return document

def select_files(directory):
    """Return list of file or directory names that can be imported."""
    assert path.isdir(directory)
    for filename in os.listdir(directory):
        pathname = path.join(directory, filename)
        if path.isdir(pathname) or pathname.endswith('.jsonld'):
            yield pathname

def import_from_dir(directory, options):
    """Import data from directory.

    Return tuple of (success, failure) counts.
    """
    success, failure = 0, 0
    for name in select_files(directory):
        subcount = import_from(name, options)
        success += subcount[0]
        failure += subcount[1]
    return (success, failure)

def import_from_file(source, options):
    """Import data from file.

    Return tuple of (success, failure) counts.
    """
    count = {
        True: 0,
        False: 0,
    }
    headers = {'Content-type': 'application/json'}
    data = read_file(source)
    for doc in data['@graph']:
        doc = prepare_document_for_POST(doc)
        rep = requests.post(options.url, data=json.dumps(doc), headers=headers)
        status = process_response(doc, rep, options)
        count[status] += 1
    return (count[True], count[False])

def import_from(source, options):
    """Import data from file or directory source.

    Return tuple of (success, failure) counts.
    """
    if path.isdir(source):
        return import_from_dir(source, options)
    else:
        return import_from_file(source, options)

def main(argv):
    args = argparser().parse_args(argv[1:])

    if args.verbose and args.quiet:
        argparser().print_help()
        print 'error: both --verbose and --quiet specified.'
        return 1

    for s in args.source:
        success, failure = import_from(s, args)
        if not args.quiet:
            print '%s: %d succeeded, %d failed' % (s, success, failure)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
