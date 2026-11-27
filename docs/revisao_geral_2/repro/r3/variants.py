import subprocess, json, sys, os
R = sys.argv[1]
base = open(f"{R}/check_late.trf", encoding="utf-8").read().splitlines()
def run(lines, tag, n=3, extra=()):
    p = f"{R}/v.trf"; open(p, "w", encoding="utf-8", newline="").write("".join(l + "\r\n" for l in lines))
    env = dict(os.environ, PYTHONPATH=".")
    r = subprocess.run([r".venv\Scripts\python.exe", r"src\services\pairing\gacrux\pairingchecker.py", "-i", p, "-o", f"{R}/v.json", "-b", "utf-8", "-c", "-n", str(n), "-m", "dutch", "-F", "JSON", *extra], capture_output=True, text=True, env=env)
    d = json.load(open(f"{R}/v.json"))
    print(tag, d["status"]["code"], (r.stderr or "")[-600:])
run(base, "base")
run([l.replace("0000 - H  0000 - H", "0000 - Z  0000 - Z").replace("Tardio                            1900 BRA             2000        1.0", "Tardio                            1900 BRA             2000        0.0") for l in base], "ZZ0")
run([l for l in base if not l.startswith("162")], "no162")
run([l.replace("    4 w", "    4 w  ") if "Tardio" in l else l for l in base], "tardio pad")
