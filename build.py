"""Build the Windows screen saver: dist/TinyCity.scr, and the same file as dist/TinyCity.exe.

PyInstaller builds the app as a folder, which is zipped into a small launcher compiled with the
C# compiler that ships with Windows. See launcher/TinyCity.cs.

    .venv\\Scripts\\python.exe build.py
"""
import glob
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DIST, BUILD = os.path.join(HERE, "dist"), os.path.join(HERE, "build")


def main():
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "TinyCity.spec"], cwd=HERE, check=True)

    app = os.path.join(DIST, "TinyCity")
    zip_path = os.path.join(BUILD, "app.zip")
    digest = hashlib.sha1()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _, files in sorted(os.walk(app)):
            for name in sorted(files):
                path = os.path.join(folder, name)
                arc = os.path.relpath(path, app)
                z.write(path, arc)
                digest.update(arc.encode())
                with open(path, "rb") as f:
                    digest.update(f.read())

    info = os.path.join(BUILD, "BuildInfo.cs")
    with open(info, "w", encoding="utf-8") as f:     # each different build unpacks into its own folder
        f.write('static class BuildInfo { public const string Id = "%s"; }\n' % digest.hexdigest()[:12])

    windir = os.environ.get("WINDIR", r"C:\Windows")
    found = sorted(glob.glob(os.path.join(windir, "Microsoft.NET", "Framework64", "v4.*", "csc.exe")))
    if not found:
        sys.exit("Couldn't find the C# compiler (csc.exe) from the .NET Framework 4.")
    out = os.path.join(DIST, "TinyCity.exe")
    subprocess.run([found[-1], "/nologo", "/target:winexe", "/optimize+", f"/out:{out}",
                    f"/resource:{zip_path},app.zip", "/r:System.IO.Compression.dll",
                    "/r:System.IO.Compression.FileSystem.dll",
                    os.path.join(HERE, "launcher", "TinyCity.cs"), info], check=True)
    shutil.copyfile(out, os.path.join(DIST, "TinyCity.scr"))
    print(f"Built {os.path.relpath(out, HERE)} and TinyCity.scr ({os.path.getsize(out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
