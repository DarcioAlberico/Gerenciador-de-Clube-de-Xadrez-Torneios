import ast,glob
for f in sorted(glob.glob("tests/test_*.py")):
    t=ast.parse(open(f,encoding="utf-8").read())
    for n in ast.walk(t):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith("test"):
            s=ast.dump(n)
            if not any(k in s for k in("assert","Raises","fail(","skip","pytest")) and "Assert" not in s:
                print(f,n.name,n.lineno)
