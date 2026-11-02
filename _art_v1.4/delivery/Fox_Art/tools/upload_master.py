# -*- coding: utf-8 -*-
"""把母版 PNG 通过一次性 ticket 上传到可灵，返回可直用的文件 URL。"""
import json
import mimetypes
import os
import sys
import urllib.request
import uuid

UPLOAD_URL = "https://klingai.com/api/mcp/files"
TICKET = sys.argv[1]
PATH = sys.argv[2]

boundary = "----wbFormBoundary" + uuid.uuid4().hex


def field(name, value):
    return ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
            % (boundary, name, value)).encode("utf-8")


def file_field(name, path):
    fn = os.path.basename(path)
    ct = mimetypes.guess_type(path)[0] or "application/octet-stream"
    head = ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
            "Content-Type: %s\r\n\r\n" % (boundary, name, fn, ct)).encode("utf-8")
    with open(path, "rb") as f:
        data = f.read()
    return head + data + b"\r\n"


body = field("ticket", TICKET) + file_field("file", PATH)
body += ("--%s--\r\n" % boundary).encode("utf-8")

req = urllib.request.Request(UPLOAD_URL, data=body, method="POST")
req.add_header("Content-Type", "multipart/form-data; boundary=%s" % boundary)
req.add_header("Accept", "application/json")
req.add_header("User-Agent", "Mozilla/5.0")

resp = urllib.request.urlopen(req, timeout=300).read().decode("utf-8", "replace")
print(resp)
