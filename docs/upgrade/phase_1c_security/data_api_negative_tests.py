"""Future read-only HTTP acceptance; no account creation, login, or row retrieval.

Run with a 0600 JSON file outside Git containing project_url, publishable_key,
authenticated_jwt and target_verified=true. Use a genuine existing Supabase Auth
fixture JWT in staging, never a FastAPI JWT or a service/secret key. No credentials
are printed. Run only after the owner verifies target and API settings.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import stat
import sys
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def claims(token):
    part = token.split('.')[1]
    return json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('credential_file', type=Path)
    args = parser.parse_args()
    info = args.credential_file.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.getuid():
        raise ValueError('Credentials must be an owned regular 0600 file outside Git')
    cfg = json.loads(args.credential_file.read_text())
    url = urlsplit(cfg['project_url'])
    if cfg.get('target_verified') is not True or url.scheme != 'https' or not url.hostname.endswith('.supabase.co') or url.path not in ('', '/') or url.username or url.password or url.query or url.fragment or url.port:
        raise ValueError('Independently verified HTTPS Supabase project origin required')
    key = cfg['publishable_key']
    if not key.startswith('sb_publishable_') and claims(key).get('role') != 'anon':
        raise ValueError('Use a publishable/anon key only')
    jwt = cfg['authenticated_jwt']
    if claims(jwt).get('role') != 'authenticated':
        raise ValueError('Existing Supabase authenticated fixture JWT required')
    # Local decoding only screens mistakes; server validation below is authoritative.
    opener = build_opener(NoRedirect())
    results = []
    for role, bearer in [('anon', None), ('authenticated', jwt)]:
        headers = {'apikey': key, 'Accept-Profile': 'public'}
        if bearer:
            headers['Authorization'] = 'Bearer ' + bearer

        def get(path):
            request = Request(url.geturl().rstrip('/') + path, headers=headers)
            try:
                with opener.open(request, timeout=10) as response:
                    return response.status, response.read(262144)
            except HTTPError as error:
                return error.code, error.read(16384)

        # OpenAPI contains metadata only. A failed control means no valid-role proof.
        status, _ = get('/rest/v1/')
        if status != 200:
            print(json.dumps({'role': role, 'result': 'INCONCLUSIVE', 'control_status': status}))
            return 2
        for table in ['users', 'user_sessions', 'refresh_tokens']:
            status, body = get('/rest/v1/' + table + '?select=id&limit=0')
            try:
                error_code = json.loads(body).get('code')
            except (ValueError, AttributeError):
                error_code = None
            # Permission denied or hidden relation after a valid-role control.
            passed = (status in (401, 403) and error_code == '42501') or (status == 404 and error_code == 'PGRST205')
            results.append({'role': role, 'table': table, 'status': status,
                            'code': error_code, 'passed': passed})
    print(json.dumps(results, indent=2))
    return 0 if all(result['passed'] for result in results) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        # Never print exception text, request headers, URLs, responses or tokens.
        print(json.dumps({'result': 'INCONCLUSIVE', 'error_type': type(error).__name__}))
        sys.exit(2)
