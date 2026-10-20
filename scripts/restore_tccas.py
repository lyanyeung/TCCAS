#!/usr/bin/env python3
"""Verify a Research Filestore TCCAS TAR against its manifest, then restore."""
import hashlib,json,pathlib,sys,tarfile,os
P=pathlib.Path
def digest(f):
 h=hashlib.sha256()
 for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
 return h.hexdigest()
def main():
 if len(sys.argv)!=2:raise RuntimeError("Usage: python3 scripts/restore_tccas.py /research/.../archive.tar.gz")
 archive=P(sys.argv[1]).resolve(strict=True)
 if not str(archive).startswith("/research/xclimatetbm/ly3n24/TCCAS_Archive/"):raise RuntimeError("Unexpected storage location")
 man=P(str(archive).removesuffix(".tar.gz")+".manifest.json")
 rec=json.loads(man.read_text())
 with archive.open("rb") as f:
  if digest(f)!=rec["archive_sha256"]:raise RuntimeError("Archive checksum mismatch")
 if archive.name!=rec["archive"]:raise RuntimeError("Archive name mismatch")
 root=P(rec["source"])
 if root.name not in {"DB","D&B","TCCAS","DB_example"}:raise RuntimeError("Unexpected restore destination")
 if root.exists() or root.is_symlink():raise RuntimeError("Destination exists: "+str(root))
 if not root.parent.is_dir():raise RuntimeError("Restore parent missing: "+str(root.parent))
 names=set()
 with tarfile.open(archive,"r:gz") as t:
  members=t.getmembers()
  for m in members:
   key=m.name.rstrip("/")
   parts=P(key).parts
   if not parts or parts[0]!=root.name or key.startswith("/") or ".." in parts or key in names:
    raise RuntimeError("Unsafe archive member "+key)
   names.add(key)
   expected=rec["entries"].get(key)
   if not expected:raise RuntimeError("Unlisted member "+key)
   if m.isdir() and expected["kind"]=="dir":pass
   elif m.issym() and expected["kind"]=="link" and m.linkname==expected["target"]:pass
   elif m.isfile() and expected["kind"]=="file" and m.size==expected["size"]:
    with t.extractfile(m) as f:
     if digest(f)!=expected["sha256"]:raise RuntimeError("File checksum mismatch: "+key)
   else:raise RuntimeError("Unsupported member/type "+key)
  if names!=set(rec["entries"]):raise RuntimeError("Missing archived members")
  # Safety: reject symlink targets escaping their source tree. Such archives are not portable,
  # and writing through linked directories on extraction can be unsafe.
  for m in members:
   if m.issym():
    path=P("/"+m.name);resolved=(path.parent/m.linkname).resolve(strict=False)
    try:resolved.relative_to(P("/"+root.name))
    except ValueError:raise RuntimeError("External symlink in archive; manual restore required: "+m.name)
  # Compatible with IRIDIS Python 3.9; all members were validated above.\n  t.extractall(path=root.parent)
 print("RESTORED",root)
 print("Verify original compiler, NetCDF libraries and domain config before running.")
if __name__=="__main__":
 try:main()
 except (RuntimeError,OSError,tarfile.TarError) as e:
  print("STOP:",e,file=sys.stderr);sys.exit(2)
