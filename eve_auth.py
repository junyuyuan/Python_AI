import base64
import hashlib
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse, urlencode

import requests


EVE_AUTH_URL = "https://login.eveonline.com/v2/oauth/authorize"
EVE_TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
EVE_VERIFY_URL = "https://esi.evetech.net/verify/"
DEFAULT_REDIRECT_PORT = 8080


class _CallbackHandler(BaseHTTPRequestHandler):
    auth_code = None
    auth_error = None

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if "code" in query:
            _CallbackHandler.auth_code = query["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>Login successful!</h1><p>You can close this window.</p>")
        elif "error" in query:
            _CallbackHandler.auth_error = query.get("error_description", [query["error"][0]])[0]
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"<h1>Login failed</h1><p>{_CallbackHandler.auth_error}</p>".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def _generate_pkce():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


def _start_callback_server(port, timeout_event):
    server = HTTPServer(("localhost", port), _CallbackHandler)
    server.timeout = 1
    while not timeout_event.is_set():
        server.handle_request()
    server.server_close()


def login(client_id, redirect_port=DEFAULT_REDIRECT_PORT, scopes=None):
    """Open browser for EVE Online SSO and return character info dict.

    Returns dict with keys: character_id, character_name, access_token,
    refresh_token, expires_on.

    Raises RuntimeError on timeout or denied authorization.
    """
    redirect_uri = f"http://localhost:{redirect_port}/callback"
    code_verifier, code_challenge = _generate_pkce()
    state = secrets.token_urlsafe(16)

    _CallbackHandler.auth_code = None
    _CallbackHandler.auth_error = None

    params = {
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "scope": " ".join(scopes) if scopes else "",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    auth_url = f"{EVE_AUTH_URL}?{urlencode(params)}"

    timeout_event = threading.Event()
    server_thread = threading.Thread(
        target=_start_callback_server, args=(redirect_port, timeout_event), daemon=True
    )
    server_thread.start()

    webbrowser.open(auth_url)

    # Wait for callback up to 5 minutes
    import time
    for _ in range(300):
        if _CallbackHandler.auth_code or _CallbackHandler.auth_error:
            break
        time.sleep(1)

    timeout_event.set()
    server_thread.join(timeout=5)

    if _CallbackHandler.auth_error:
        raise RuntimeError(f"Authorization denied: {_CallbackHandler.auth_error}")
    if not _CallbackHandler.auth_code:
        raise RuntimeError("Authorization timed out.")

    # Exchange code for token
    token_data = {
        "grant_type": "authorization_code",
        "code": _CallbackHandler.auth_code,
        "client_id": client_id,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
    }
    resp = requests.post(
        EVE_TOKEN_URL,
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    token_json = resp.json()

    access_token = token_json["access_token"]
    refresh_token = token_json.get("refresh_token")

    # Verify token and get character info
    verify_resp = requests.get(
        EVE_VERIFY_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    verify_resp.raise_for_status()
    char_info = verify_resp.json()

    return {
        "character_id": char_info.get("CharacterID"),
        "character_name": char_info.get("CharacterName"),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_on": char_info.get("ExpiresOn"),
    }


def refresh_access_token(client_id, refresh_token):
    """Use a refresh token to get a new access token."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }
    resp = requests.post(
        EVE_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()
