"""Local-only administration with per-device credentials and CSRF checks."""
import base64
import hmac
import os
import secrets
from pathlib import Path
from aiohttp import web


def ensure_admin_token(path=Path('/etc/kiosk/admin-token')):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'w') as output:
            output.write(secrets.token_urlsafe(32) + '\n')
    os.chmod(path, 0o600)
    token = path.read_text().strip()
    if len(token) < 32:
        raise RuntimeError('Admin token is invalid; refusing to serve administration.')
    return token


def admin_auth(token):
    @web.middleware
    async def protect(request, handler):
        try:
            scheme, encoded = request.headers.get('Authorization', '').split(' ', 1)
            username, supplied = base64.b64decode(encoded, validate=True).decode().split(':', 1)
            valid = scheme.lower() == 'basic' and username == 'admin' and hmac.compare_digest(supplied, token)
        except (ValueError, UnicodeError):
            valid = False
        if not valid:
            raise web.HTTPUnauthorized(headers={'WWW-Authenticate': 'Basic realm="WallThing", charset="UTF-8"'})
        # A browser on this device must not gain access through a cross-origin page.
        origin = request.headers.get('Origin')
        expected = f'{request.scheme}://{request.host}'
        if request.headers.get('Sec-Fetch-Site') == 'cross-site' or (origin and origin != expected):
            raise web.HTTPForbidden(text='Cross-origin administration is disabled.')
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and not origin and request.headers.get('X-WallThing-Action') != '1':
            raise web.HTTPForbidden(text='Use a same-origin form or X-WallThing-Action: 1.')
        response = await handler(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response
    return protect
