"""Publish a Tiny City release on GitHub with dist/TinyCity.scr and dist/TinyCity.exe attached.

    .venv\\Scripts\\python.exe release.py v1.3.0 notes.md

The tag must already be pushed. Uses the GitHub login that git already has saved
(git credential fill); the token is never printed or written anywhere.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

REPO = "derrickbarasa/evolution"
FILES = ("TinyCity.scr", "TinyCity.exe")
HERE = os.path.dirname(os.path.abspath(__file__))


def token():
    out = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                         capture_output=True, text=True, check=True).stdout
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)["password"]


def main():
    if len(sys.argv) != 3 or not re.fullmatch(r"v\d+\.\d+\.\d+", sys.argv[1]):
        sys.exit("usage: release.py vX.Y.Z NOTES_FILE")
    tag, notes_file = sys.argv[1], sys.argv[2]
    with open(notes_file, encoding="utf-8") as f:
        notes = f.read()
    headers = {"Authorization": f"Bearer {token()}", "Accept": "application/vnd.github+json",
               "User-Agent": "tinycity-release"}

    def call(url, data, ctype="application/json"):
        req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": ctype})
        with urllib.request.urlopen(req) as r:
            return json.load(r)

    rel = call(f"https://api.github.com/repos/{REPO}/releases",
               json.dumps({"tag_name": tag, "name": f"Tiny City {tag[1:]}", "body": notes}).encode())
    print("release:", rel["html_url"])
    upload = rel["upload_url"].split("{")[0]
    for name in FILES:
        with open(os.path.join(HERE, "dist", name), "rb") as f:
            data = f.read()
        a = call(f"{upload}?name={name}", data, "application/octet-stream")
        print("uploaded", a["name"], a["size"], "bytes")

    # check the public "latest" download matches what was uploaded
    url = f"https://github.com/{REPO}/releases/latest/download/{FILES[0]}"
    with urllib.request.urlopen(url) as r:
        public = hashlib.sha256(r.read()).hexdigest()
    with open(os.path.join(HERE, "dist", FILES[0]), "rb") as f:
        local = hashlib.sha256(f.read()).hexdigest()
    print("latest download matches local build:", public == local)


if __name__ == "__main__":
    main()
