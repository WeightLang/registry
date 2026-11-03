#!/usr/bin/env python3
"""Validate index records without executing model or publisher code."""
import argparse
import hashlib
import json
import re
import subprocess
import urllib.request

FIELDS = {'format_version', 'name', 'module', 'version', 'source_commit', 'index_sha256', 'license', 'edition', 'yanked'}

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

def download(url, limit, expected=None):
    request = urllib.request.Request(url, headers={'User-Agent': 'weightlang-registry'})
    digest = hashlib.sha256()
    size = 0
    chunks = [] if expected is None else None
    with urllib.request.urlopen(request, timeout=60) as response:
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            assert size <= limit, f'oversize download: {url}'
            digest.update(chunk)
            if chunks is not None:
                chunks.append(chunk)
    if expected is not None:
        assert size == limit and digest.hexdigest() == expected, f'asset hash/size mismatch: {url}'
        return None
    return b''.join(chunks)

def validate(path, record):
    assert set(record) == FIELDS, 'unexpected or missing record fields'
    assert type(record['format_version']) is int and record['format_version'] == 1
    assert isinstance(record['name'], str) and re.fullmatch(r'[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9-]*', record['name'])
    assert isinstance(record['module'], str) and re.fullmatch(r'github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', record['module'])
    parts = record['module'].split('/')
    assert all(part not in ('.', '..') for part in parts)
    assert record['name'].split('/')[0] == parts[1].lower(), 'namespace ownership mismatch'
    assert re.fullmatch(r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', record['version'])
    assert path == f"packages/{record['name']}/{record['version']}.json", 'record path mismatch'
    assert re.fullmatch(r'[0-9a-f]{40}', record['source_commit'])
    assert re.fullmatch(r'[0-9a-f]{64}', record['index_sha256'])
    assert isinstance(record['license'], str) and 0 < len(record['license']) <= 200
    assert not any(ord(c) < 32 or ord(c) == 127 for c in record['license'])
    assert record['edition'] in ('0.1', '0.2', '0.3') and type(record['yanked']) is bool

def verify(record):
    parts = record['module'].split('/')
    repo = '/'.join(parts[1:3])
    subdir = '/'.join(parts[3:])
    tag = f"{subdir}/{record['version']}" if subdir else record['version']
    refs = dict(line.split('\t')[::-1] for line in git('ls-remote', '--tags', f'https://github.com/{repo}', f'refs/tags/{tag}', f'refs/tags/{tag}^{{}}').splitlines())
    assert refs.get(f'refs/tags/{tag}^{{}}', refs.get(f'refs/tags/{tag}')) == record['source_commit'], 'tag moved'
    base = f'https://github.com/{repo}/releases/download/{tag}'
    raw = download(f'{base}/wgt.index.json', 16 * 1024**2)
    assert hashlib.sha256(raw).hexdigest() == record['index_sha256'], 'index changed'
    index = json.loads(raw)
    assert index['format'] == 'weightlang.package-index' and index['format_version'] == 1
    assert (index['module'], index['version'], index['commit'], index['tag']) == (record['module'], record['version'], record['source_commit'], tag)
    assert index['artifacts'], 'empty package'
    for name, artifact in index['artifacts'].items():
        assert re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name)
        for filename in ('manifest.json', 'source.wgt', 'weights.safetensors'):
            meta = artifact['files'][filename]
            assert re.fullmatch(r'[A-Za-z0-9_.-]+', meta['asset']) and meta['asset'] not in ('.', '..')
            assert type(meta['size']) is int and 0 <= meta['size'] <= 2 * 1024**3
            assert re.fullmatch(r'[0-9a-f]{64}', meta['sha256'])
            download(f"{base}/{meta['asset']}", meta['size'], meta['sha256'])
        source = artifact['source_path']
        assert all(re.fullmatch(r'[A-Za-z0-9_.-]+', p) and p not in ('.', '..') for p in source.split('/'))
        raw_path = '/'.join(p for p in (subdir, source) if p)
        raw = download(f"https://raw.githubusercontent.com/{repo}/{record['source_commit']}/{raw_path}", 16 * 1024**2)
        assert hashlib.sha256(raw).hexdigest() == artifact['files']['source.wgt']['sha256'], 'source mismatch'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base')
    parser.add_argument('--head', default='HEAD')
    parser.add_argument('--verify-assets', action='store_true')
    args = parser.parse_args()
    records = {}
    modules = {}
    for path in git('ls-tree', '-r', '--name-only', args.head, '--', 'packages/').splitlines():
        record = json.loads(git('show', f'{args.head}:{path}'))
        validate(path, record)
        assert modules.setdefault(record['name'], record['module']) == record['module'], 'canonical module changed'
        records[path] = record
    if args.base:
        for path in git('ls-tree', '-r', '--name-only', args.base, '--', 'packages/').splitlines():
            assert path in records, 'cannot delete published records'
            old = json.loads(git('show', f'{args.base}:{path}'))
            new = records[path]
            assert old == new or (not old['yanked'] and new == {**old, 'yanked': True}), 'published record changed'
        changed = set(git('diff', '--name-only', args.base, args.head, '--', 'packages/').splitlines())
    else:
        changed = set(records)
    for path in sorted(changed):
        if args.verify_assets:
            verify(records[path])
        print(f'validated {path}')
    print(f'{len(records)} records; {len(changed)} changed')

if __name__ == '__main__':
    main()
