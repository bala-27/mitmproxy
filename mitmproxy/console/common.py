from __future__ import absolute_import, print_function, division

import os

import urwid
import urwid.util
import six

import netlib
<<<<<<< a7bc7d29a484c87bc1576d33bf5ab23aa5031c43
from mitmproxy import flow
=======
from mitmproxy import models
>>>>>>> Common function for both file and clipboard
from mitmproxy import utils
from mitmproxy.console import signals
from mitmproxy.flow import export
from netlib import human

try:
    import pyperclip
except:
    pyperclip = False


VIEW_FLOW_REQUEST = 0
VIEW_FLOW_RESPONSE = 1

METHOD_OPTIONS = [
    ("get", "g"),
    ("post", "p"),
    ("put", "u"),
    ("head", "h"),
    ("trace", "t"),
    ("delete", "d"),
    ("options", "o"),
    ("edit raw", "e"),
]


def is_keypress(k):
    """
        Is this input event a keypress?
    """
    if isinstance(k, six.string_types):
        return True


def highlight_key(str, key, textattr="text", keyattr="key"):
    l = []
    parts = str.split(key, 1)
    if parts[0]:
        l.append((textattr, parts[0]))
    l.append((keyattr, key))
    if parts[1]:
        l.append((textattr, parts[1]))
    return l


KEY_MAX = 30


def format_keyvals(lst, key="key", val="text", indent=0):
    """
        Format a list of (key, value) tuples.

        If key is None, it's treated specially:
            - We assume a sub-value, and add an extra indent.
            - The value is treated as a pre-formatted list of directives.
    """
    ret = []
    if lst:
        maxk = min(max(len(i[0]) for i in lst if i and i[0]), KEY_MAX)
        for i, kv in enumerate(lst):
            if kv is None:
                ret.append(urwid.Text(""))
            else:
                if isinstance(kv[1], urwid.Widget):
                    v = kv[1]
                elif kv[1] is None:
                    v = urwid.Text("")
                else:
                    v = urwid.Text([(val, kv[1])])
                ret.append(
                    urwid.Columns(
                        [
                            ("fixed", indent, urwid.Text("")),
                            (
                                "fixed",
                                maxk,
                                urwid.Text([(key, kv[0] or "")])
                            ),
                            v
                        ],
                        dividechars = 2
                    )
                )
    return ret


def shortcuts(k):
    if k == " ":
        k = "page down"
    elif k == "ctrl f":
        k = "page down"
    elif k == "ctrl b":
        k = "page up"
    elif k == "j":
        k = "down"
    elif k == "k":
        k = "up"
    return k


def fcol(s, attr):
    s = six.text_type(s)
    return (
        "fixed",
        len(s),
        urwid.Text(
            [
                (attr, s)
            ]
        )
    )

if urwid.util.detected_encoding:
    SYMBOL_REPLAY = u"\u21ba"
    SYMBOL_RETURN = u"\u2190"
    SYMBOL_MARK = u"\u25cf"
else:
    SYMBOL_REPLAY = u"[r]"
    SYMBOL_RETURN = u"<-"
    SYMBOL_MARK = "[m]"


# Save file to disk
def save_data(path, data):
    if not path:
        return
    try:
        with open(path, "wb") as f:
            f.write(data)
    except IOError as v:
        signals.status_message.send(message=v.strerror)


def ask_save_overwrite(path, data):
    if not path:
        return
    path = os.path.expanduser(path)
    if os.path.exists(path):
        def save_overwrite(k):
            if k == "y":
                save_data(path, data)

        signals.status_prompt_onekey.send(
            prompt = "'" + path + "' already exists. Overwrite?",
            keys = (
                ("yes", "y"),
                ("no", "n"),
            ),
            callback = save_overwrite
        )
    else:
        save_data(path, data)


def ask_save_path(data, prompt="File path"):
    signals.status_prompt_path.send(
        prompt = prompt,
        callback = ask_save_overwrite,
        args = (data, )
    )


def copy_to_clipboard_or_prompt(data):
    # pyperclip calls encode('utf-8') on data to be copied without checking.
    # if data are already encoded that way UnicodeDecodeError is thrown.
    toclip = ""
    try:
        toclip = data.decode('utf-8')
    except (UnicodeDecodeError):
        toclip = data

    try:
        pyperclip.copy(toclip)
    except (RuntimeError, UnicodeDecodeError, AttributeError, TypeError):
        def save(k):
            if k == "y":
                ask_save_path(data, "Save data")
        signals.status_prompt_onekey.send(
            prompt = "Cannot copy data to clipboard. Save as file?",
            keys = (
                ("yes", "y"),
                ("no", "n"),
            ),
            callback = save
        )


def flow_format_data(part, scope, flow):
    if part == "u":
        data = flow.request.url
    else:
        data = ""
        if scope in ("q", "a"):
            request = flow.request.copy()
            request.decode(strict=False)
            if request.content is None:
                return None, "Request content is missing"
            if part == "h":
                data += netlib.http.http1.assemble_request(request)
            elif part == "c":
                data += request.content
            else:
                raise ValueError("Unknown part: {}".format(part))
        if scope == "a" and flow.request.raw_content and flow.response:
            # Add padding between request and response
            data += "\r\n" * 2
        if scope in ("s", "a") and flow.response:
            response = flow.response.copy()
            response.decode(strict=False)
            if response.content is None:
                return None, "Response content is missing"
            if part == "h":
                data += netlib.http.http1.assemble_response(response)
            elif part == "c":
                data += response.content
            else:
                raise ValueError("Unknown part: {}".format(part))
    return data, False


def copy_flow(part, scope, flow, master, state):
    """
    part: _c_ontent, _h_eaders+content, _u_rl
    scope: _a_ll, re_q_uest, re_s_ponse
    """
    data, err = flow_format_data(part, scope, flow)

    if err:
        signals.status_message.send(message=err)
        return

    if not data:
        if scope == "q":
            signals.status_message.send(message="No request content to copy.")
        elif scope == "s":
            signals.status_message.send(message="No response content to copy.")
        else:
            signals.status_message.send(message="No contents to copy.")
        return

    copy_to_clipboard_or_prompt(data)


def ask_copy_part(scope, flow, master, state):
    choices = [
        ("content", "c"),
        ("headers+content", "h")
    ]
    if scope != "s":
        choices.append(("url", "u"))

    signals.status_prompt_onekey.send(
        prompt = "Copy",
        keys = choices,
        callback = copy_flow,
        args = (scope, flow, master, state)
    )


def ask_save_body(part, master, state, flow):
    """
    Save either the request or the response body to disk.

    'part' can either be "q" (request), "s" (response) or None (ask user if necessary).
    """

    request_has_content = flow.request and flow.request.raw_content
    response_has_content = flow.response and flow.response.raw_content

    if part is None:
        # We first need to determine whether we want to save the request or the
        # response content.
        if request_has_content and response_has_content:
            signals.status_prompt_onekey.send(
                prompt = "Save",
                keys = (
                    ("request", "q"),
                    ("response", "s"),
                ),
                callback = ask_save_body,
                args = (master, state, flow)
            )
        elif response_has_content:
            ask_save_body("s", master, state, flow)
        else:
            ask_save_body("q", master, state, flow)

    elif part == "q" and request_has_content:
        ask_save_path(
            flow.request.get_content(strict=False),
            "Save request content",
        )
    elif part == "s" and response_has_content:
        ask_save_path(
            flow.response.get_content(strict=False),
            "Save response content",
        )
    else:
        signals.status_message.send(message="No content to save.")


def export_to_clip_or_file(key, flow, writer):
    """
    Export selected flow to clipboard or a file.

    'writer' is a function that handles the data
    can be: copy_to_clipboard_or_prompt or ask_save_path
    """
    for exporter in export.EXPORTERS:
        if key == exporter[1]:
            writer(exporter[2](flow))

flowcache = utils.LRUCache(800)


def raw_format_flow(f, focus, extended):
    f = dict(f)
    pile = []
    req = []
    if extended:
        req.append(
            fcol(
                human.format_timestamp(f["req_timestamp"]),
                "highlight"
            )
        )
    else:
        req.append(fcol(">>" if focus else "  ", "focus"))

    if f["marked"]:
        req.append(fcol(SYMBOL_MARK, "mark"))

    if f["req_is_replay"]:
        req.append(fcol(SYMBOL_REPLAY, "replay"))
    req.append(fcol(f["req_method"], "method"))

    preamble = sum(i[1] for i in req) + len(req) - 1

    if f["intercepted"] and not f["acked"]:
        uc = "intercept"
    elif "resp_code" in f or "err_msg" in f:
        uc = "text"
    else:
        uc = "title"

    url = f["req_url"]
    if f["req_http_version"] not in ("HTTP/1.0", "HTTP/1.1"):
        url += " " + f["req_http_version"]
    req.append(
        urwid.Text([(uc, url)])
    )

    pile.append(urwid.Columns(req, dividechars=1))

    resp = []
    resp.append(
        ("fixed", preamble, urwid.Text(""))
    )

    if "resp_code" in f:
        codes = {
            2: "code_200",
            3: "code_300",
            4: "code_400",
            5: "code_500",
        }
        ccol = codes.get(f["resp_code"] / 100, "code_other")
        resp.append(fcol(SYMBOL_RETURN, ccol))
        if f["resp_is_replay"]:
            resp.append(fcol(SYMBOL_REPLAY, "replay"))
        resp.append(fcol(f["resp_code"], ccol))
        if extended:
            resp.append(fcol(f["resp_reason"], ccol))
        if f["intercepted"] and f["resp_code"] and not f["acked"]:
            rc = "intercept"
        else:
            rc = "text"

        if f["resp_ctype"]:
            resp.append(fcol(f["resp_ctype"], rc))
        resp.append(fcol(f["resp_clen"], rc))
        resp.append(fcol(f["roundtrip"], rc))

    elif f["err_msg"]:
        resp.append(fcol(SYMBOL_RETURN, "error"))
        resp.append(
            urwid.Text([
                (
                    "error",
                    f["err_msg"]
                )
            ])
        )
    pile.append(urwid.Columns(resp, dividechars=1))
    return urwid.Pile(pile)


def format_flow(f, focus, extended=False, hostheader=False, marked=False):
    d = dict(
        intercepted = f.intercepted,
        acked = f.reply.acked,

        req_timestamp = f.request.timestamp_start,
        req_is_replay = f.request.is_replay,
        req_method = f.request.method,
        req_url = f.request.pretty_url if hostheader else f.request.url,
        req_http_version = f.request.http_version,

        err_msg = f.error.msg if f.error else None,

        marked = marked,
    )
    if f.response:
        if f.response.raw_content:
            contentdesc = human.pretty_size(len(f.response.raw_content))
        elif f.response.raw_content is None:
            contentdesc = "[content missing]"
        else:
            contentdesc = "[no content]"
        duration = 0
        if f.response.timestamp_end and f.request.timestamp_start:
            duration = f.response.timestamp_end - f.request.timestamp_start
        roundtrip = human.pretty_duration(duration)

        d.update(dict(
            resp_code = f.response.status_code,
            resp_reason = f.response.reason,
            resp_is_replay = f.response.is_replay,
            resp_clen = contentdesc,
            roundtrip = roundtrip,
        ))
        t = f.response.headers.get("content-type")
        if t:
            d["resp_ctype"] = t.split(";")[0]
        else:
            d["resp_ctype"] = ""
    return flowcache.get(
        raw_format_flow,
        tuple(sorted(d.items())), focus, extended
    )
