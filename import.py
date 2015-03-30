#!/usr/bin/env python

"""Import data to Open Annotation store over RESTful interface.

Example usage:

    python import.py data/examples/craft/12925238.jsonld

(requires a RESTful Open Annotation server)
"""

__author__ = 'Sampo Pyysalo'
__license__ = 'MIT'

import os
import sys
import logging
import urlparse
import codecs
import json

from os import path
from logging import warn, info

import requests

# logging.basicConfig(level=logging.INFO)

TARGET_KEY = 'target'
DEFAULT_ANN_URL='http://127.0.0.1:5005/annotations/'
DEFAULT_DOC_URL='http://127.0.0.1:5005/documents/'
DEFAULT_ENCODING='utf-8'

def argparser():
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument('source', metavar='FILE/DIR', nargs='+',
                        help='Source data to import')
    parser.add_argument('-v', '--verbose', default=False, action='store_true',
                        help='Verbose output')
    parser.add_argument('-u', '--url', default=DEFAULT_ANN_URL,
                        help='URL for annotation store (default %s)' %
                        DEFAULT_ANN_URL)
    parser.add_argument('-d', '--docurl', default=DEFAULT_DOC_URL,
                        help='URL for document store (default %s)' %
                        DEFAULT_DOC_URL)
    parser.add_argument('-q', '--quiet', default=False, action='store_true',
                        help='No output')
    return parser

def pretty(doc):
    """Pretty-print JSON."""
    return json.dumps(doc, sort_keys=True, indent=2, separators=(',', ': '))

def read_json_file(source):
    with codecs.open(source, encoding=DEFAULT_ENCODING) as f:
        text = f.read()
    return json.loads(text)

def read_text_file(filename, directory=None):
    if directory is not None:
        filename = path.join(directory, filename)
    try:
        with codecs.open(filename, encoding=DEFAULT_ENCODING) as f:
            return f.read()
    except Exception, e:
        warn('failed to read %s: %s' % (filename, str(e)))
    return None

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

def is_relative(url):
    return urlparse.urlparse(url).netloc == ''

def get_relative_target_urls(document):
    """Return unique relative target URLs in OA JSON-LD document."""
    # TODO: check for @base to differentiate true relative targets
    # from ones that just look relative without context.
    found = set()
    target = document.get(TARGET_KEY)
    if not target:
        warn('missing target')
    elif isinstance(target, basestring):
        if is_relative(target):
            found.add(urlparse.urldefrag(target)[0])
    elif isinstance(target, list):
        for t in target:
            if is_relative(t):
                found.add(urlparse.urldefrag(t)[0])
    else:
        raise NotImplementedError('structured target support')
    return found

def _map_relative(target, target_map):
    # Helper for rewrite_relative_target_urls
    assert isinstance(target, basestring)
    if not is_relative(target):
        return target
    base, frag = urlparse.urldefrag(target)
    mapped = target_map.get(base)
    if not mapped:
        return target
    else:
        return mapped + '#' + frag

def rewrite_relative_target_urls(document, target_map):
    """Replace relative target URLs with absolute equivalents."""
    target = document.get(TARGET_KEY)
    if not target:
        return
    elif isinstance(target, basestring):
        mapped = _map_relative(target, target_map)
    elif isinstance(target, list):
        mapped = [_map_relative(t, target_map) for t in target]
    else:
        raise NotImplementedError('structured target support')
    document[TARGET_KEY] = mapped

def remove_non_files(filenames, basedir):
    """Return given list without non-files."""
    filtered = set()
    for filename in filenames:
        pathname = path.join(basedir, filename)
        if not os.path.exists(pathname):
            warn('target not found: %s' % pathname)
        elif not os.path.isfile(pathname):
            warn('target not file: %s' % pathname)
        else:
            filtered.add(filename)
    return filtered

def remove_known_targets(targets, target_text, target_map, options):
    # TODO: use HEAD and ETag to avoid actual download
    filtered = set()
    headers = { 'Accept': 'text/plain' }
    for target in targets:
        url = urlparse.urljoin(options.docurl, target)
        response = requests.get(url, headers=headers)
        if response.status_code == 404:
            info('not found: %s' % url)
            filtered.add(target)
        elif response.status_code == 200:
            if response.text == target_text[target]:
                # Document exists with identical text; OK.
                info('document already in store: %s' % target)
                target_map[target] = url
            else:
                # Document exists with different text; warn and block mapping.
                warn('text mismatch for %s vs %s' % (target, url))
                target_map[target] = None
        else:
            response.raise_for_status()
    return filtered

def post_target(target, target_text, target_map, store):
    """Post given target document to store."""
    headers = {'Content-type': 'application/json'}
    content = target_text[target]
    if content is None:
        target_map[target] = None
        return False
    doc = {
        'name': target,
        'text': content
    }
    response = requests.post(store, data=json.dumps(doc), headers=headers)
    try:
        response.raise_for_status()
        target_map[target] = urlparse.urljoin(store, target)
        print 'POSTed %s to store %s' % (target, store)
        return True
    except Exception, e:
        warn('error posting %s: %s' % (target, str(e)))
        target_map[target] = None
        return False

def post_target_documents(targets, target_map, basedir, options):
    """Post new targets to document store."""
    # Filter out known and unavailable targets
    targets = set(t for t in targets if t not in target_map)
    targets = remove_non_files(targets, basedir)
    if not targets:
        return
    # Make sure we have a store to post to
    if not options.docurl:
        warn('no docurl given, cannot POST target(s): %s' % ' '.join(targets))
        return
    # Read target document texts
    target_text = {}
    for target in targets:
        target_text[target] = read_text_file(target, basedir)
    # Exclude documents already in the store
    targets = remove_known_targets(targets, target_text, target_map, options)
    if not targets:
        return
    # Post each target to the store
    for target in targets:
        post_target(target, target_text, target_map, options.docurl)

def resolve_target_references(document, basedir, options):
    """Resolve relative target URLs, uploading documents if required."""
    target_map = resolve_target_references.target_map
    relative = get_relative_target_urls(document)
    # POST any new targets to document store, updating map
    post_target_documents(relative, target_map, basedir, options)
    # rewrite relative URLs using the mapping
    rewrite_relative_target_urls(document, target_map)
resolve_target_references.target_map = {}

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
    try:
        data = read_json_file(source)
    except Exception, e:
        print 'Failed to load json from %s: %s' % (source, str(e))
        return (0, 1)
    dir = os.path.dirname(source)
    for doc in data['@graph']:
        resolve_target_references(doc, dir, options)
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

def fix_args(args):
    """Fix potentially problematic user-provided arguments."""
    # Note: urlparse gives unexpected results when given an
    # incomplete url with a port and a path but no scheme:
    # >>> urlparse.urlparse('example.org:80/foo').scheme
    # 'example.org'
    # We're avoiding this issue by prepending a default scheme
    # if there's no obvious one present.
    def has_scheme(u):
        return u.startswith('http://') or u.startswith('https://')
    # We're going to be urljoin:ing things to the docurl collection,
    # so docurl has to end in a slash.
    if args.docurl and not args.docurl.endswith('/'):
        warn('adding "/" to docurl %s' % args.docurl)
        args.docurl += '/'
    if not has_scheme(args.url):
        warn('adding "http://" to url %s' % args.url)
        args.url = 'http://' + args.url
    if not has_scheme(args.docurl):
        warn('adding "http://" to docurl %s' % args.docurl)
        args.docurl = 'http://' + args.docurl
    return args

def main(argv):
    args = fix_args(argparser().parse_args(argv[1:]))

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
