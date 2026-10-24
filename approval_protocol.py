"""Bounded JSON-only protocol for one live permission request per local pipe."""
import hashlib
import json
import math
from pathlib import Path
import re

MAX_FRAME = 65536
MAX_PENDING = 20
REQUEST_TTL = 120


def endpoint_name():
    digest = hashlib.sha256(str(Path.home()).casefold().encode()).hexdigest()[:24]
    return 'daisy-approvals-' + digest


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def decode_frame(data):
    if not isinstance(data, bytes) or len(data) > MAX_FRAME:
        raise ValueError('Request is too large')
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=_unique_pairs,
                           parse_float=_finite_float,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid number')))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('Invalid JSON') from exc
    if not isinstance(value, dict):
        raise ValueError('Object required')
    return value


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('Invalid number')
    return value


def encode_frame(value):
    try:
        data = (json.dumps(value, ensure_ascii=True, allow_nan=False,
                           separators=(',', ':')) + '\n').encode('ascii')
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError('Invalid JSON value') from exc
    if len(data) > MAX_FRAME:
        raise ValueError('Request is too large')
    return data


def validate_request(value):
    fields = {'version', 'provider', 'nonce', 'session_id', 'cwd', 'tool_name', 'tool_input'}
    if set(value) != fields or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Unsupported request')
    if value['provider'] not in ('codex', 'claude'):
        raise ValueError('Unsupported provider')
    if not isinstance(value['nonce'], str) or not re.fullmatch(r'[0-9a-f]{32}', value['nonce']):
        raise ValueError('Invalid request nonce')
    for key, limit in (('session_id', 512), ('cwd', 8192), ('tool_name', 256)):
        if not isinstance(value[key], str) or not value[key] or len(value[key]) > limit:
            raise ValueError('Invalid request field')
    if not isinstance(value['tool_input'], dict):
        raise ValueError('Invalid tool input')
    encode_frame(value)
    return value
