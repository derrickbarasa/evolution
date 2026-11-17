// The TinyCity.scr that Windows runs. It carries the whole app (dist/TinyCity/, zipped) inside it,
// unpacks it once into %LOCALAPPDATA%\TinyCity\app\<build>, and from then on just starts it from
// there. Nothing is unpacked or deleted per run, so the screen saver starts and stops quickly.
// Built by build.py with the C# compiler that comes with Windows.
using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;

[assembly: AssemblyTitle("Tiny City")]
[assembly: AssemblyProduct("Tiny City")]

static class Launcher
{
    [STAThread]
    static int Main(string[] args)
    {
        string root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                                   "TinyCity", "app");
        string dir = Path.Combine(root, BuildInfo.Id);
        string exe = Path.Combine(dir, "TinyCity.exe");
        if (!File.Exists(exe))
            Unpack(root, dir);

        string line = string.Join(" ", args.Select(Quote));
        var info = new ProcessStartInfo(exe, line) { UseShellExecute = false, WorkingDirectory = dir };
        using (var app = Process.Start(info))
        {
            app.WaitForExit();
            return app.ExitCode;
        }
    }

    static void Unpack(string root, string dir)
    {
        string tmp = dir + ".tmp" + Process.GetCurrentProcess().Id;
        if (Directory.Exists(tmp))
            Directory.Delete(tmp, true);
        using (var zip = new ZipArchive(Assembly.GetExecutingAssembly().GetManifestResourceStream("app.zip")))
            zip.ExtractToDirectory(tmp);
        try
        {
            Directory.Move(tmp, dir);
        }
        catch (IOException)         // another copy (the preview, say) unpacked it first
        {
            Directory.Delete(tmp, true);
        }
        foreach (string old in Directory.GetDirectories(root))     // earlier versions
        {
            if (!string.Equals(old, dir, StringComparison.OrdinalIgnoreCase) && !old.Contains(".tmp"))
            {
                try { Directory.Delete(old, true); } catch (Exception) { }      // still running: next time
            }
        }
    }

    static string Quote(string arg)
    {
        if (arg.Length > 0 && arg.IndexOfAny(new[] { ' ', '\t', '"' }) < 0)
            return arg;
        return "\"" + arg.Replace("\"", "\\\"") + "\"";
    }
}
