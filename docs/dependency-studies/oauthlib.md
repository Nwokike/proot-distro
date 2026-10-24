# oauthlib — exhaustive API reference (installed 4.0.0)

Verified 2026-10-16 against `.venv/Lib/site-packages/oauthlib` (4.0.0) via live
introspection (`.venv/Scripts/python.exe -c` + `inspect.signature`) and source reads.
Context: `docs/roadmap.md`, `docs/reference/dep-flet-runtime-utils.md`,
`docs/reference/app-sherlock.md`, D-010 (`docs/decisions.md:33-34` — flet stays 1.0.4).
Anti-hallucination rule: every signature below was obtained by live
`inspect.signature` or a direct source read except where explicitly marked
**unverified**; file:line refs point at the installed source
(`.venv/Lib/site-packages/oauthlib/...`).

## 1. Identity

| Fact | Value (verified) |
|---|---|
| Version | **4.0.0** (`oauthlib-4.0.0.dist-info/METADATA` `Name:`/`Version:`; also `oauthlib/__init__.py:15` `__version__ = '4.0.0'`, `__author__ = 'The OAuthlib Community'` at `:14`) |
| License | **BSD-3-Clause** (METADATA `License:`; `LICENSE` shipped as `License-File`) |
| Summary | "A generic, spec-compliant, thorough implementation of the OAuth request-signing logic" (METADATA) |
| Requires-Python | `>=3.9` (METADATA); our runtime is the Flet-bundled Python 3.14 |
| Optional extras | `rsa` → `cryptography>=3.0.0`; `signedtoken` → `cryptography>=3.0.0` + `pyjwt<3,>=2.0.0`; `signals` → `blinker>=1.4.0` (all METADATA `Requires-Dist ... extra ==`) |
| Extras installed here | **None** — no `cryptography`, `jwt`/`pyjwt`, or `blinker` directory exists in `.venv/Lib/site-packages` (verified by listing). Consequence: RSA/JWT paths and blinker signals run on the noop fallback (see §7) |
| Size on disk | ~1,043,015 bytes, **75 `.py` files** (verified `du` + `find`) — the largest prunable leaf in the tree |
| Pure-Python | Yes — no compiled extensions; ships unmodified into the APK unless pruned |
| flet's floor | `Requires-Dist: oauthlib>=3.2.2; platform_system != "Emscripten"` (`flet-1.0.4.dist-info/METADATA:14`). Note the environment marker — on Emscripten, flet itself runs *without* oauthlib, which is upstream precedent that flet tolerates its absence (§4) |

Top-level layout (verified `find`): `__init__.py`, `common.py`, `signals.py`,
`uri_validate.py`, plus three spec packages — `oauth1/rfc5849/`, `oauth2/rfc6749/`,
`oauth2/rfc8628/`, `openid/connect/core/` — each with `clients/`, `endpoints/`,
`grant_types/`, `errors.py`, `request_validator.py` where the RFC needs them.

## 2. Complete API surface (inventory level + key signatures)

### 2.1 `oauthlib/__init__.py` — package root

No client/server names are re-exported at the root (verified `cat`: only logging
setup, `__author__`, `__version__`, `set_debug(:21)`, `get_debug(:29)`). Every
consumer imports from `oauthlib.oauth1`, `oauthlib.oauth2`, `oauthlib.openid`, or
`oauthlib.common` — including flet (§3).

### 2.2 `oauthlib/common.py` — shared primitives

All functions verified by live introspection; line refs from `grep "^def \|^class "`:

| Member | Signature (verified) | Line |
|---|---|---|
| `quote` | `(s, safe=b'/')` | `:43` |
| `unquote` | `(s)` | `:53` |
| `urlencode` | `(params)` | `:63` |
| `encode_params_utf8` | `(params)` | `:72` |
| `decode_params_utf8` | `(params)` | `:84` |
| `urldecode` | `(query)` | `:99` |
| `extract_params` | `(raw)` | `:132` |
| `generate_nonce` | `()` | `:161` |
| `generate_timestamp` | `()` | `:176` |
| `generate_token` | `(length=30, chars=UNICODE_ASCII_CHARACTER_SET)` | `:188` |
| `generate_signed_token` | `(private_pem, request)` | `:200` |
| `verify_signed_token` | `(public_pem, token)` | `:218` |
| `generate_client_id` | `(length=30, chars=CLIENT_ID_CHARACTER_SET)` | `:224` |
| `add_params_to_qs` | `(query, params)` | `:233` |
| `add_params_to_uri` | `(uri, params, fragment=False)` | `:242` |
| `safe_string_equals` | `(a, b)` | `:252` |
| `to_unicode` | `(data, encoding='UTF-8')` | `:270` |
| `get_debug` | `()` (re-exported here; defined in `__init__.py:29`) | introspected |
| `CaseInsensitiveDict` | `dict` subclass | `:295` |
| `Request` | `(uri, http_method='GET', body=None, headers=None, encoding='utf-8')` | `:331` |

`Request` instance state (verified source read, `:331-380`): `uri`, `http_method`,
`headers` (as `CaseInsensitiveDict`), `body`, `decoded_body` (via
`extract_params`), `oauth_params` (list), `validator_log` (dict), plus the `_params`
dict pre-seeded with keys `access_token, client, client_id, client_secret, code,
code_challenge, code_challenge_method, code_verifier, extra_credentials, grant_type,
redirect_uri, refresh_token, request_token, resource, response_type, scope, scopes,
state, token, user`. `Request` is the object every `RequestValidator` method receives.

### 2.3 `oauthlib/oauth1` — OAuth 1.0a (RFC 5849)

Re-exported at `oauthlib/oauth1/__init__.py`: signature constants, `Client`,
endpoint classes (`AccessTokenEndpoint, AuthorizationEndpoint,
RequestTokenEndpoint, ResourceEndpoint, SignatureOnlyEndpoint,
WebApplicationServer`), errors, `RequestValidator`.

Signature constants (`rfc5849/__init__.py:45-69`): `SIGNATURE_HMAC_SHA1`,
`SIGNATURE_HMAC_SHA256`, `SIGNATURE_HMAC_SHA512`, `SIGNATURE_HMAC` (deprecated alias
of SHA1), `SIGNATURE_RSA_SHA1`, `SIGNATURE_RSA_SHA256`, `SIGNATURE_RSA_SHA512`,
`SIGNATURE_RSA` (deprecated alias of RSA-SHA1), `SIGNATURE_PLAINTEXT`,
`SIGNATURE_METHODS` tuple (`:57`), `SIGNATURE_TYPE_AUTH_HEADER`,
`SIGNATURE_TYPE_QUERY`, `SIGNATURE_TYPE_BODY`, `CONTENT_TYPE_FORM_URLENCODED`
(`:71`).

Key class signature (verified introspection):

```text
Client(client_key, client_secret=None, resource_owner_key=None,
       resource_owner_secret=None, callback_uri=None,
       signature_method='HMAC-SHA1', signature_type='AUTH_HEADER',
       rsa_key=None, verifier=None, realm=None, encoding='utf-8',
       decoding=None, nonce=None, timestamp=None)   # rfc5849/__init__.py:74
  methods: get_oauth_params, get_oauth_signature, register_signature_method, sign
  class attr: SIGNATURE_METHODS
```

`signature.py` functions (verified lines): `signature_base_string(:55)`,
`base_string_uri(uri: str, host: str = None) -> str (:106)`,
`collect_parameters(:237)`, `normalize_parameters(params) -> str (:324)`,
`_sign_hmac(:366)`, `_verify_hmac(:431)`, `sign_hmac_sha1_with_client(:464)`,
`verify_hmac_sha1(:469)`, `sign_hmac_sha1(:473)`,
`sign_hmac_sha256_with_client(:500)`, `verify_hmac_sha256(:505)` (further
RSA/SHA-512 variants exist below — inventory level, lines **unverified** past 505).
`parameters.py`: `prepare_headers(:19)`, `_append_params(:88)`,
`prepare_form_encoded_body(:109)`, `prepare_request_uri_query(:121)`.
`utils.py` present (function inventory **unverified**).

ALL oauth1 errors (`rfc5849/errors.py`, verified lines): `OAuth1Error(:11)` base,
`InsecureTransportError(:62)` ("Only HTTPS connections are permitted."),
`InvalidSignatureMethodError(:67)`, `InvalidRequestError(:71)`,
`InvalidClientError(:75)`. (Five total — the complete set.)

Endpoints (`rfc5849/endpoints/`): `RequestTokenEndpoint(request_token.py:21)`,
`AuthorizationEndpoint(authorization.py:17)`, `AccessTokenEndpoint(access_token.py:21)`,
`ResourceEndpoint(resource.py:17)`, `SignatureOnlyEndpoint(signature_only.py:17)`,
`BaseEndpoint(base.py:21)`, `WebApplicationServer(pre_configured.py:7)` (multiple
inheritance over request-token + authorization + access-token endpoints).

`RequestValidator` (`rfc5849/request_validator.py`, verified `def` lines): config
properties `allowed_signature_methods(:114)`, `safe_characters(:118)`,
`client_key_length(:122)`, `request_token_length(:126)`,
`access_token_length(:130)`, `timestamp_lifetime(:134)`, `nonce_length(:138)`,
`verifier_length(:142)`, `realms(:146)`, `enforce_ssl(:150)`; checks
`check_client_key(:153)`, `check_request_token(:161)`, `check_access_token(:169)`,
`check_nonce(:177)`, `check_verifier(:185)`, `check_realms(:193)`; getters
`get_client_secret(:261)`, `get_request_token_secret(:297)`,
`get_access_token_secret(:330)`, `get_default_realms(:363)`, `get_realms(:380)`,
`get_redirect_uri(:395)`, `get_rsa_key(:413)`; validators
`validate_client_key(:464)`, `validate_request_token(:501)`,
`validate_access_token(:536)`, `validate_timestamp_and_nonce(:571)`,
`validate_redirect_uri(:622)`, `validate_requested_realms(:656)`,
`validate_realms(:675)`, `validate_verifier(:710)`, `verify_request_token(:742)`,
`verify_realms(:761)`; savers `save_access_token(:785)`, `save_request_token(:809)`,
`save_verifier(:830)`; dummies `dummy_client(:206)`, `dummy_request_token(:230)`,
`dummy_access_token(:246)`.

### 2.4 `oauthlib/oauth2` — OAuth 2.0 (RFC 6749 + RFC 8628 device flow)

Re-exported at `oauthlib/oauth2/__init__.py` (verified read): clients
(`BackendApplicationClient, Client, LegacyApplicationClient,
MobileApplicationClient, ServiceApplicationClient, WebApplicationClient`),
endpoints (`AuthorizationEndpoint, BackendApplicationServer, IntrospectEndpoint,
LegacyApplicationServer, MetadataEndpoint, MobileApplicationServer,
ResourceEndpoint, RevocationEndpoint, Server, TokenEndpoint,
WebApplicationServer`), 30 errors, grants (`AuthorizationCodeGrant,
ClientCredentialsGrant, ImplicitGrant, RefreshTokenGrant,
ResourceOwnerPasswordCredentialsGrant`), `RequestValidator`, `BearerToken,
OAuth2Token`, `is_secure_transport`, plus device-flow names (`DeviceClient`,
`DeviceApplicationServer`, `DeviceAuthorizationEndpoint`, `AccessDenied,
AuthorizationPendingError, ExpiredTokenError, SlowDownError`, `DeviceCodeGrant`).

#### Clients — key signatures (all verified introspection)

```text
Client(client_id, default_token_placement='auth_header', token_type='Bearer',
       access_token=None, refresh_token=None, mac_key=None, mac_algorithm=None,
       token=None, scope=None, state=None, redirect_url=None,
       state_generator=generate_token, code_verifier=None, code_challenge=None,
       code_challenge_method=None, **kwargs)          # clients/base.py
  methods: add_token, create_code_challenge, create_code_verifier,
           parse_request_body_response, parse_request_uri_response,
           populate_code_attributes, populate_token_attributes,
           prepare_authorization_request, prepare_refresh_body,
           prepare_refresh_token_request, prepare_request_body,
           prepare_request_uri, prepare_token_request,
           prepare_token_revocation_request

WebApplicationClient(client_id, code=None, **kwargs)          # web_application.py
MobileApplicationClient(client_id, <same Client kwargs>)      # mobile_application.py
LegacyApplicationClient(client_id, **kwargs)                  # legacy_application.py
BackendApplicationClient(client_id, <same Client kwargs>)     # backend_application.py
ServiceApplicationClient(client_id, private_key=None, subject=None,
                         issuer=None, audience=None, **kwargs) # service_application.py
DeviceClient(client_id, **kwargs)                             # rfc8628/clients/device.py:15
```

`WebApplicationClient` is the ONLY client flet touches (§3).

#### ALL oauth2 errors (`rfc6749/errors.py`, 35 classes, verified lines + status/code)

Base `OAuth2Error(:15)` (status 400). Complete set:

| Class | Line | HTTP | `error` code |
|---|---|---|---|
| `OAuth2Error` | `:15` | 400 | — |
| `TokenExpiredError` | `:117` | 400 | `token_expired` |
| `InsecureTransportError` | `:121` | 400 | `insecure_transport` ("OAuth 2 MUST utilize https.") |
| `MismatchingStateError` | `:126` | 400 | `mismatching_state` ("CSRF Warning! State not equal in request and response.") |
| `MissingCodeError` | `:131` | 400 | `missing_code` |
| `MissingTokenError` | `:135` | 400 | `missing_token` |
| `MissingTokenTypeError` | `:139` | 400 | `missing_token_type` |
| `FatalClientError` | `:143` | 400 | — |
| `InvalidRequestFatalError` | `:157` | 400 | `invalid_request` |
| `InvalidRedirectURIError` | `:166` | 400 | `invalid_request` ("Invalid redirect URI.") |
| `MissingRedirectURIError` | `:170` | 400 | `invalid_request` ("Missing redirect URI.") |
| `MismatchingRedirectURIError` | `:174` | 400 | `invalid_request` ("Mismatching redirect URI.") |
| `InvalidClientIdError` | `:178` | 400 | `invalid_request` ("Invalid client_id parameter value.") |
| `MissingClientIdError` | `:182` | 400 | `invalid_request` ("Missing client_id parameter.") |
| `InvalidRequestError` | `:186` | 400 | `invalid_request` |
| `MissingResponseTypeError` | `:195` | 400 | `invalid_request` ("Missing response_type parameter.") |
| `MissingCodeChallengeError` | `:199` | 400 | `invalid_request` ("Code challenge required.") |
| `MissingCodeVerifierError` | `:211` | 400 | `invalid_request` ("Code verifier required.") |
| `AccessDeniedError` | `:219` | 400 | `access_denied` |
| `UnsupportedResponseTypeError` | `:226` | 400 | `unsupported_response_type` |
| `UnsupportedCodeChallengeMethodError` | `:234` | 400 | `invalid_request` ("Transform algorithm not supported.") |
| `InvalidScopeError` | `:246` | 400 | `invalid_scope` |
| `ServerError` | `:256` | 400 | `server_error` |
| `TemporarilyUnavailableError` | `:266` | 400 | `temporarily_unavailable` |
| `InvalidClientError` | `:276` | **401** | `invalid_client` |
| `InvalidGrantError` | `:292` | 400 | `invalid_grant` |
| `UnauthorizedClientError` | `:305` | 400 | `unauthorized_client` |
| `UnsupportedGrantTypeError` | `:313` | 400 | `unsupported_grant_type` |
| `UnsupportedTokenTypeError` | `:321` | 400 | `unsupported_token_type` |
| `InvalidTokenError` | `:330` | **401** | `invalid_token` |
| `InsufficientScopeError` | `:344` | **403** | `insufficient_scope` |
| `ConsentRequired` | `:358` | 400 | `consent_required` |
| `LoginRequired` | `:369` | 400 | `login_required` |
| `CustomOAuth2Error` | `:380` | 400 | — |

Status codes and `error` strings above are live-introspected (`status_code` /
`error` attrs); descriptions are source `description` attrs (truncated where long).

#### Grant types + RequestValidator + endpoints + tokens

Grant types (`rfc6749/grant_types/`, verified class lines): `ValidatorsContainer
(base.py:18)`, `GrantTypeBase(base.py:75)` with `register_response_type`,
`register_code_modifier`, `register_token_modifier` (`:110-116`);
`AuthorizationCodeGrant(:66)`, `ClientCredentialsGrant`, `RefreshTokenGrant`,
`ImplicitGrant`, `ResourceOwnerPasswordCredentialsGrant`.

`RequestValidator` (`rfc6749/request_validator.py:10`) — 28 methods, ALL overridable
no-op/must-implement hooks for a provider server (verified `def` lines):
`client_authentication_required(:12)`, `authenticate_client(:41)`,
`authenticate_client_id(:83)`, `confirm_redirect_uri(:107)`,
`get_default_redirect_uri(:131)`, `get_default_scopes(:145)`,
`get_original_scopes(:161)`, `is_within_original_scope(:174)`,
`introspect_token(:196)`, `invalidate_authorization_code(:238)`,
`revoke_token(:251)`, `rotate_refresh_token(:264)`, `save_authorization_code(:280)`,
`save_token(:316)`, `save_bearer_token(:327)`, `validate_bearer_token(:377)`,
`validate_client_id(:429)`, `validate_code(:448)`, `validate_grant_type(:483)`,
`validate_redirect_uri(:501)`, `validate_refresh_token(:519)`,
`validate_response_type(:538)`, `validate_scopes(:554)`, `validate_user(:572)`,
`is_pkce_required(:592)`, `get_code_challenge(:618)`,
`get_code_challenge_method(:647)`, `is_origin_allowed(:667)`.
(Flet implements NONE of these — it is a pure OAuth *client*.)

Endpoints (`rfc6749/endpoints/`, verified class + key `def` lines):
`BaseEndpoint(base.py:21)` with `valid_request_methods` / `available` /
`catch_errors` properties and `_raise_on_*` guards (`:53-82`);
`AuthorizationEndpoint(authorization.py:18)`,
`TokenEndpoint(token.py:18)` with `create_token_response(:86)` and
`validate_token_request(:117)`, `ResourceEndpoint(resource.py:17)`,
`RevocationEndpoint(revocation.py:19)`, `IntrospectEndpoint(introspect.py:20)`,
`MetadataEndpoint(metadata.py:23)`; pre-configured all-in-one servers
(`pre_configured.py`): `Server(:25)`, `WebApplicationServer(:96)`,
`MobileApplicationServer(:149)`, `LegacyApplicationServer(:196)`,
`BackendApplicationServer(:243)`.

`tokens.py` (verified `def`/`class` lines): `OAuth2Token(dict) (:22)`,
`prepare_mac_header(:67)`, `prepare_bearer_uri(:173)`,
`prepare_bearer_headers(:187)`, `prepare_bearer_body(:203)`,
`random_token_generator(:216)`, `signed_token_generator(:225)`,
`get_token_from_header(:236)`, `TokenBase(:256)`, `BearerToken(:277)`.
`parameters.py`: `prepare_grant_uri(:25)`, `prepare_token_request(:93)`,
`prepare_token_revocation_request(:174)`, `parse_authorization_code_response(:231)`,
`parse_implicit_response(:287)`, `parse_token_response(:359)`,
`validate_token_parameters(:447)`, `parse_expires(:474)`.
`utils.py`: `list_to_scope(:14)`, `scope_to_list(:24)`, `params_from_uri(:34)`,
`host_from_uri(:41)`, `escape(:60)`, `generate_age(:71)`,
`is_secure_transport(:79)`.

#### RFC 8628 device flow (`oauth2/rfc8628/`)

`DeviceClient` (above); `DeviceCodeGrant(grant_types/device_code.py:12)`;
`DeviceAuthorizationEndpoint(endpoints/device_authorization.py:22)`;
`DeviceApplicationServer(endpoints/pre_configured.py:9)` (extends the device
endpoint); `RequestValidator(request_validator.py:4)` — subclasses the OAuth2
validator adding exactly one override, `client_authentication_required`
returning `True` (verified full 24-line file read); errors (`errors.py`):
`AuthorizationPendingError(:12)`, `SlowDownError(:29)`, `ExpiredTokenError(:39)`,
`AccessDenied(:50)` (codes `authorization_pending`, `slow_down`,
`expired_token`, `access_denied` — live-introspected).

### 2.5 `oauthlib/openid` — OpenID Connect core

14 exception classes (`connect/core/exceptions.py`, verified lines):
`FatalOpenIDClientError(:14)`, `OpenIDClientError(:18)`,
`InteractionRequired(:22)`, `LoginRequired(:34)`, `AccountSelectionRequired(:46)`,
`ConsentRequired(:60)`, `InvalidRequestURI(:72)`, `InvalidRequestObject(:82)`,
`RequestNotSupported(:90)`, `RequestURINotSupported(:98)`,
`RegistrationNotSupported(:106)`, `InvalidTokenError(:114)`,
`InsufficientScopeError(:128)` (+ `OAuth2Error`/`FatalClientError` re-exports).

Grant types (`connect/core/grant_types/`): `Dispatcher(:6)`,
`AuthorizationCodeGrantDispatcher(:11)`, `ImplicitTokenGrantDispatcher(:40)`,
`AuthorizationTokenGrantDispatcher(:69)` (all `dispatchers.py`);
`GrantTypeBase(base.py:14)`, `AuthorizationCodeGrant(:16)`, `ImplicitGrant(:17)`,
`HybridGrant(hybrid.py:18)`, `RefreshTokenGrant(refresh_token.py:16)`.
`RequestValidator(request_validator.py:14)` (extends the OAuth2 validator).
`JWTToken(tokens.py:12)` (extends `TokenBase`; JWT signing needs the
`signedtoken` extra — NOT installed here).
`UserInfoEndpoint(endpoints/userinfo.py:20)`; all-in-one
`Server(endpoints/pre_configured.py:40)` mixing authorization + token + resource
+ revocation + userinfo endpoints, whose `__init__` (verified read, `:55-70`)
is `(request_validator, token_expires_in=None, token_generator=None,
refresh_token_generator=None, *args, **kwargs)` and wires `auth_grant`,
`implicit_grant`, `password_grant`, `credentials_grant`, `refresh_grant`, and
`openid_connect_auth` grant handlers.

### 2.6 `oauthlib/signals.py` + `oauthlib/uri_validate.py`

`signals.py` (verified read): `signals_available = False (:6)`, tries
`from blinker import Namespace` and falls back to a noop `_FakeSignal` whose
`send()` returns `None`; exposes exactly one core signal,
`scope_changed = _signals.signal('scope-changed') (:41)`. Blinker is NOT
installed here, so the noop path is live — nothing in flet connects signals
anyway (§3).

`uri_validate.py` (verified lines): `is_uri(:180)`, `is_uri_reference(:184)`,
`is_absolute_uri(:188)` — RFC 3986 regex predicates.

## 3. How flet uses it exactly (quote sites)

oauthlib has **exactly three import sites in all of flet**, every one a
function-local import of the same client class inside
`flet/auth/authorization_service.py` (verified `grep -rn "oauthlib" flet/` —
no other file imports it, not even the provider modules):

```text
flet/auth/authorization_service.py:93:        from oauthlib.oauth2 import WebApplicationClient
flet/auth/authorization_service.py:120:        from oauthlib.oauth2 import WebApplicationClient
flet/auth/authorization_service.py:208:        from oauthlib.oauth2 import WebApplicationClient
```

Call-site roles (verified surrounding reads):

1. `get_authorization_data(:86)` — `client = WebApplicationClient(self.provider.client_id)` (`:96`),
   then `client.prepare_request_uri(...)` (`:97`) to build the authorization URL + `state`
   (`self.state = secrets.token_urlsafe(16)` at `:95`).
2. `request_token(:108)` — `WebApplicationClient(self.provider.client_id)` (`:122`),
   `client.prepare_request_body(code=code, ...)` (`:123`), sent via httpx (`import httpx` at `:119`).
3. `__refresh_token(:188)` — `WebApplicationClient(self.provider.client_id)` (`:211`),
   `client.prepare_refresh_body(...)` (`:212`), via httpx (`:207`); token mapping
   normalized in `__convert_token(:168)` whose docstring names oauthlib twice
   (`:170`: "Convert oauthlib token mapping…", `:173`: "Token dictionary returned
   by oauthlib client parsing.").

Entry point is `Page.login()` (`flet/controls/page.py:1193`):

```text
async def login(
    self,
    provider: "OAuthProvider",
    fetch_user: bool = True,
    fetch_groups: bool = False,
    scope: Optional[list[str]] = None,
    saved_token: Optional[str] = None,
    on_open_authorization_url: Optional[
        Callable[[str], Coroutine[Any, Any, None]]
    ] = None,
    complete_page_html: Optional[str] = None,
    redirect_to_page: Optional[bool] = False,
    authorization: "Optional[type[AT]]" = None,
) -> "AT": ...
```

The default authorization impl is itself deferred (`page.py:69-79`):

```text
def _default_authorization_impl() -> "type[Authorization]":
    # docstring: "Deferring these imports keeps the auth subsystem out of the
    # cold-start import graph for apps that never call `Page.login`."
        from flet.auth.authorization_service import AuthorizationService
```

Verified consequences: `import flet` does NOT load oauthlib (eager-import test:
`'oauthlib' in sys.modules` → `False` after `import flet`). The four bundled
providers (`GitHubOAuthProvider`, `GoogleOAuthProvider`, `AzureOAuthProvider`,
`Auth0OAuthProvider` in `flet/auth/providers/`, verified class lines) only carry
endpoint URLs — zero oauthlib imports. Reachability chain is exactly:
`Page.login()` → `AuthorizationService` → `oauthlib.oauth2.WebApplicationClient`.
Nothing else in flet touches the other ~74 oauthlib modules (no server, grant,
endpoint, or validator class is ever imported).

## 4. Pruning analysis — what breaks when `oauthlib/**` is removed

**Exactly one thing breaks: `Page.login()` / OAuth provider sign-in.**
Verified from flet source: the only runtime importer is
`authorization_service.py`, itself reachable only via `Page.login()` (deferred
import, §3). Our app has NO login flow (roadmap: no auth screens through M3), and
the repo contains zero oauthlib references — verified `grep -rn
"oauthlib\|Page.login\|OAuthProvider" src/ tests/` returns nothing.
Removing the directory therefore removes only dead code on our path. Failure mode
if login were ever called without the package: `ModuleNotFoundError: No module
named 'oauthlib'` inside `get_authorization_data` — loud, immediate, and confined
to the login call (no silent misbehavior, no import-time breakage of the app,
since page.py's import is deferred and `import flet` never loads oauthlib).

Cleanup-key mechanics for our project (verified `flet_cli/commands/build_base.py`):
CLI flags `--cleanup-package-files` (`:642-643`, `dest="cleanup_package_files"`)
are fed from pyproject via `self.get_platform_setting("cleanup.package_files")`
(`:2770-2772`), which resolves with precedence `tool.flet.<platform>.` then
`tool.flet.` (`get_platform_setting`, `:2925-2938`); each glob is appended as
`--cleanup-package-files <glob>` (`:2778-2783`) and enables `--cleanup-packages`.
So the D-010-era key from the brief is the table

```toml
[tool.flet.cleanup]
package_files = ["oauthlib/**"]
```

(optionally per-platform under `[tool.flet.android.cleanup]`). This mirrors the
Sherlock precedent verbatim: `app-sherlock.md:31` records
`cleanup.package_files` "audited globs incl. `oauthlib/**`", and `:34` notes the
transferable shape for us is "near-zero — only `oauthlib/**`". Our pyproject
currently has NO `[tool.flet]` table at all (verified read), so this is a
packaging-milestone addition, not a change to anything existing. Two further
safety facts: (a) flet's own METADATA carries the Emscripten-exclusion marker on
oauthlib, i.e. upstream already ships configurations where flet runs without it;
(b) ~1 MB saved per APK split for a package nothing on our path imports.

Re-adding later is one line removed from `package_files` plus a version bump —
no code changes, since the pruning is purely a packaging glob, not a source edit
(no-patching rule unaffected).

## 5. How oauthlib makes our app significantly better than Termux's proot-distro

Honest baseline first: Termux's proot-distro has no OAuth story at all — it is a
CLI/Bash installer with no identity layer — so ANY OAuth capability we keep is
strictly additive. But today that capability is **entirely optional**: our M0–M3
scope (install/list/login/remove containers, terminal UI, ads) needs zero
identity, which is why §4 recommends pruning. The concrete leverage, if we ever
choose it, is all client-side (flet never uses oauthlib's server/validator
halves — those ~40 modules are dead weight on-device under every scenario):

- **Private container images.** Docker Hub and `ghcr.io` gate pulls behind
  registry tokens. A future "sign in with GitHub to pull your private images"
  flow is exactly `GitHubOAuthProvider` + `Page.login()` + the `:93-97`
  authorization-URL path — no new dependency, no native code, works inside the
  existing Flet auth cookie plumbing. (Speculative-but-labeled: no registry-auth
  work is scoped before M5; Docker Hub personal-access-tokens today don't even
  need OAuth.)
- **Device flow fit.** RFC 8628 (`DeviceClient`, `DeviceCodeGrant`) is designed
  for input-constrained devices — philosophically adjacent to a phone app, though
  a phone browser completes standard flows fine, so this is a nice-to-have, not a
  driver.
- **What it can never do for us:** act as an OAuth *provider* (the endpoint /
  grant / `RequestValidator` machinery serves tokens to others — meaningless
  inside an Android client app), or replace registry credential helpers
  (`docker login` token storage is out of oauthlib's scope).

Net: oauthlib is a free option on future login flows, bought with ~1 MB and zero
integration cost while kept, and cleanly prunable while unused. The recommended
posture is **prune at packaging (`oauthlib/**`), keep the knowledge in this file**
— re-adding is a one-line un-glob the day a login flow is scoped.

## 6. Verification refs

- Installed tree: `.venv/Lib/site-packages/oauthlib/` (75 `.py` files, ~1,043,015
  bytes); versions/licenses/extras from `oauthlib-4.0.0.dist-info/METADATA`;
  `__version__` at `oauthlib/__init__.py:15`.
- Signatures: live `inspect.signature` on `oauthlib.common.*`,
  `oauthlib.oauth1.Client`, `oauthlib.oauth2.*Client` (incl. `DeviceClient`),
  `Request`, openid `Server`; error `status_code`/`error`/descriptions
  live-read; class:line tables via `grep "^class "` per errors file.
- flet sites: `grep -rn "oauthlib" .venv/Lib/site-packages/flet/` (3 code imports
  + 2 docstring mentions, all `authorization_service.py`); `page.py:69-79,1193`;
  `flet/__init__` provider re-exports; `flet-1.0.4.dist-info/METADATA:14-18`.
- Cleanup: `flet_cli/commands/build_base.py:642-643,2770-2783,2925-2938`;
  Sherlock precedent `docs/reference/app-sherlock.md:31,34`; repo-zero-usage
  grep over `src/ tests/`; eager-import test
  (`import flet` → `oauthlib` absent from `sys.modules`).
- **Unverified** (explicitly): function inventory of `oauth1/rfc5849/utils.py`;
  RSA/SHA-512 `signature.py` helpers past line 505; per-method behavior of
  endpoint `create_*_response` bodies beyond the cited signatures (inventory-level
  coverage only, per brief).
