import sys, os, importlib.util, unittest
sys.path.insert(0, os.getcwd())
path = sys.argv[1]
spec = importlib.util.spec_from_file_location("probe", path)
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
names = sys.argv[2:]
loader = unittest.TestLoader()
suite = unittest.TestSuite()
for cls_name in [n for n in dir(mod) if n.startswith("Sonda")]:
    cls = getattr(mod, cls_name)
    for t in loader.getTestCaseNames(cls):
        if not names or any(n in t for n in names):
            suite.addTest(cls(t))
unittest.TextTestRunner(verbosity=2).run(suite)
