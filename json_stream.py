# SPDX-License-Identifier: MIT
"""A tiny streaming parser for a top-level JSON array of flat objects.

The VEX Events API's world skills rankings endpoint returns a single,
unpaginated JSON array that can run several megabytes for a busy
season/grade combination -- far more than comfortably fits as a fully
decoded list of dicts in memory on a microcontroller. ``vex_data`` streams
that response through here and decodes/filters one object at a time
instead of holding the whole array (see ``vex_data._fetch_world_skills_group``).

This only has to handle the shape the API actually returns -- a top-level
``[ {...}, {...}, ... ]`` array of non-nested-array flat objects -- not
arbitrary JSON. It scans raw bytes rather than decoded text: '{', '}',
'"', '\\', '[' and ']' are always single ASCII bytes in UTF-8 even when
they delimit multi-byte characters, so byte-level scanning is safe
without ever needing to decode text that may be split mid-character
across two network chunks.
"""

_OPEN_BRACKET = 0x5B  # '['
_CLOSE_BRACKET = 0x5D  # ']'
_OPEN_BRACE = 0x7B  # '{'
_CLOSE_BRACE = 0x7D  # '}'
_QUOTE = 0x22  # '"'
_BACKSLASH = 0x5C  # '\\'


def iter_json_array_objects(chunks):
    """Yield each top-level object's raw bytes from a byte-chunk iterable
    containing a single JSON array of objects, e.g. ``[{...}, {...}]``.

    ``chunks`` is any iterable of byte strings (as produced by
    ``adafruit_requests.Response.iter_content()``) -- chunk boundaries may
    fall anywhere, including mid-object or mid-string.
    """
    buf = b""
    pos = 0  # next unscanned byte in buf -- persists across chunks so each
    # byte is only ever examined once, regardless of how small the chunks are
    started = False
    obj_start = None
    depth = 0
    in_string = False
    escape = False

    for chunk in chunks:
        buf += bytes(chunk)
        n = len(buf)
        while pos < n:
            b = buf[pos]
            if not started:
                if b == _OPEN_BRACKET:
                    started = True
                pos += 1
                continue
            if obj_start is None:
                if b == _OPEN_BRACE:
                    obj_start = pos
                    depth = 1
                    in_string = False
                    escape = False
                elif b == _CLOSE_BRACKET:
                    return
                pos += 1
                continue
            if escape:
                escape = False
            elif in_string:
                if b == _BACKSLASH:
                    escape = True
                elif b == _QUOTE:
                    in_string = False
            else:
                if b == _QUOTE:
                    in_string = True
                elif b == _OPEN_BRACE:
                    depth += 1
                elif b == _CLOSE_BRACE:
                    depth -= 1
                    if depth == 0:
                        yield buf[obj_start : pos + 1]
                        obj_start = None
            pos += 1

        # Drop the fully-processed prefix so the buffer never grows past
        # roughly one object's worth of bytes, however small the chunks are.
        keep_from = obj_start if obj_start is not None else pos
        if keep_from > 0:
            buf = buf[keep_from:]
            pos -= keep_from
            if obj_start is not None:
                obj_start = 0
