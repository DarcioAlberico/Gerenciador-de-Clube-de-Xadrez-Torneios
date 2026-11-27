import subprocess,unicodedata,re,sys
out=subprocess.run(["git","diff","HEAD","-U0","--","src","app.py"],capture_output=True,text=True,encoding="utf-8").stdout
def n(s): return ''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
f=None;rem=[];add=[]
res=[]
def flush():
    for r in rem:
        for a in add:
            if r!=a and n(r)==n(a): res.append((f,r.strip(),a.strip()))
for l in out.splitlines():
    if l.startswith('+++ '): flush();f=l[6:];rem=[];add=[]
    elif l.startswith('@@'): flush();rem=[];add=[]
    elif l.startswith('-') and not l.startswith('---'): rem.append(l[1:])
    elif l.startswith('+') and not l.startswith('+++'): add.append(l[1:])
flush()
# keep only code lines (not comments / docstring-ish): those with quotes and not starting with #
for f,r,a in res:
    if r.startswith('#'): continue
    print(f,'|',a[:150])
