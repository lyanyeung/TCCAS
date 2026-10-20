#!/usr/bin/env python3
"""TCCAS Research Filestore archival: inspect, copy, verify, optionally move."""
import argparse, hashlib, json, os, pathlib, re, shutil, stat, subprocess, sys, tarfile, datetime
P=pathlib.Path
DEST=P("/research/xclimatetbm/ly3n24/TCCAS_Archive")
NAMES={"DB","D&B","TCCAS","DB_example"}

def die(s): raise RuntimeError(str(s))
def sha_stream(f):
    h=hashlib.sha256()
    for b in iter(lambda:f.read(4*1024*1024),b""): h.update(b)
    return h.hexdigest()
def sha_file(p):
    with open(p,"rb") as f:return sha_stream(f)
def below(path, root):
    try: P(path).resolve().relative_to(P(root).resolve()); return True
    except ValueError: return False
def tree(root):
    entries={}; external=[]
    def walk(p):
        rel=p.relative_to(root.parent).as_posix(); st=p.lstat()
        if stat.S_ISLNK(st.st_mode):
            link=os.readlink(p)
            entries[rel]={"kind":"link","target":link}
            if not below(p.parent/link,root): external.append(rel+" -> "+link)
        elif stat.S_ISDIR(st.st_mode):
            entries[rel]={"kind":"dir"}
            for child in sorted(p.iterdir()):walk(child)
        elif stat.S_ISREG(st.st_mode):
            entries[rel]={"kind":"file","size":st.st_size,"sha256":sha_file(p)}
        else:die("Special file blocks archive: "+str(p))
    walk(root);return entries,external
def validate_tar(path,entries):
    found=set()
    with tarfile.open(path,"r:gz") as t:
        for m in t:
            key=m.name.rstrip("/")
            if key not in entries or key in found:die("Unexpected/duplicate TAR entry: "+key)
            x=entries[key]
            if x["kind"]=="dir" and m.isdir():pass
            elif x["kind"]=="link" and m.issym() and m.linkname==x["target"]:pass
            elif x["kind"]=="file" and m.isfile() and m.size==x["size"]:
                with t.extractfile(m) as f:
                    if sha_stream(f)!=x["sha256"]:die("Checksum mismatch: "+key)
            else:die("Type mismatch: "+key)
            found.add(key)
    if found!=set(entries):die("Missing archive entries")
def jobs_reference(src):
    q=subprocess.run(["squeue","-h","-u",os.environ.get("USER",""),"-o","%i"],capture_output=True,text=True)
    if q.returncode:die("Cannot inspect Slurm queue: "+q.stderr)
    for job in q.stdout.split():
        p=subprocess.run(["scontrol","show","job","-o",job],capture_output=True,text=True)
        if p.returncode:die("Cannot inspect Slurm job "+job)
        if str(src) in p.stdout or re.search(r"JobName=\S*(TCCAS|D&B|DB_example)\S*",p.stdout,re.I):
            die("Active Slurm reference; refusing move: "+job)
def check_mount(dest):
    # Force the autofs mount before statfs check; never silently fall back to local filesystem.
    if not P("/research/xclimatetbm/ly3n24").is_dir():die("Research Filestore unavailable")
    dest.parent.mkdir(parents=True,exist_ok=True)
    p=subprocess.run(["stat","-f","-c","%T",str(dest.parent)],capture_output=True,text=True)
    if p.returncode or p.stdout.strip() not in ("nfs","nfs4"):
        die("Research destination not confirmed NFS: "+p.stdout+" "+p.stderr)
def discover():
    home=P.home(); scratch=P("/scratch")/os.environ.get("USER",home.name)
    sources=[home/n for n in ("DB","D&B","TCCAS")]+[scratch/n for n in ("DB","D&B","TCCAS","DB_example")]
    chosen=[p for p in sources if p.is_dir() and not p.is_symlink()]
    others=[]
    if scratch.is_dir():
        cmd=["find",str(scratch),"-maxdepth","7","-type","d","(","-iname","*TCCAS*","-o","-name","DB","-o","-name","D&B","-o","-name","DB_example",")","-print"]
        p=subprocess.run(cmd,capture_output=True,text=True)
        if p.returncode:die("Scratch discovery incomplete: "+p.stderr)
        others=[P(x) for x in p.stdout.splitlines() if P(x) not in chosen]
    return chosen,others
def verify_previous(tar,man,source):
    rec=json.loads(man.read_text())
    if rec.get("source")!=str(source) or rec.get("archive")!=tar.name:die("Existing manifest mismatch")
    if sha_file(tar)!=rec.get("archive_sha256"):die("Existing archive SHA mismatch")
    validate_tar(tar,rec["entries"])
    now,links=tree(source)
    if now!=rec["entries"]:die("Existing backup no longer matches source")
    return rec,links
def archive(src,mode):
    root=src.resolve(strict=True)
    if root.name not in NAMES or root.is_symlink():die("Unexpected selected source: "+str(root))
    if "CLM_FATES" in root.parts or "CTSM_FATES_OUTPUTS" in root.parts:die("CLM-FATES protected")
    area="scratch" if below(root,"/scratch") else "home"
    dest=DEST/area
    name=str(root).strip("/").replace("/","__")
    tar=dest/(name+".tar.gz")
    man=dest/(name+".manifest.json")
    sha=dest/(name+".tar.gz.sha256")
    check_mount(tar)
    if tar.exists() or man.exists() or sha.exists():
        if not all(x.is_file() for x in (tar,man,sha)):die("Incomplete prior archive; inspect manually: "+str(tar))
        rec,links=verify_previous(tar,man,root)
        if sha.read_text().split()[0]!=rec["archive_sha256"]:die("SHA receipt mismatch")
        print("VERIFIED_EXISTING",tar,flush=True)
    else:
        entries,links=tree(root)
        print("INVENTORY",root,"files",sum(v["kind"]=="file" for v in entries.values()),"external_symlinks",len(links),flush=True)
        temp=P(str(tar)+".partial")
        if temp.exists():die("Unfinished previous .partial present: "+str(temp))
        with tarfile.open(temp,"w:gz",dereference=False,format=tarfile.PAX_FORMAT) as t:
            t.add(root,arcname=root.name,recursive=True)
        validate_tar(temp,entries)
        after,new_links=tree(root)
        if after!=entries:die("Source changed during backup; original untouched")
        links=new_links
        digest=sha_file(temp)
        # A manifest is written before the TAR is promoted, and verified again on reuse.
        rec={"format":1,"source":str(root),"archive":tar.name,"archive_sha256":digest,
             "created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "entries":entries,"external_symlinks":links,"removed":False}
        tempman=P(str(man)+".partial")
        tempman.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+"\n")
        temp.replace(tar)
        tempman.replace(man)
        sha.write_text(digest+"  "+tar.name+"\n")
        print("VERIFIED_NEW",tar,flush=True)
    if mode=="copy":return
    # Conservative deletion policy: never delete if any link escapes the source.
    if links:
        print("COPY_ONLY: external symlinks; retained source",root)
        for l in links:print("  ",l)
        return
    jobs_reference(root)
    now,_=tree(root)
    if now!=rec["entries"]:die("Source changed after verification; original untouched")
    # Restore hazard: other scripts may reference this location without appearing in Slurm.
    # We require a second explicit, operator-controlled cleanup invocation.
    if os.environ.get("TCCAS_CONFIRM_DELETE")!="YES":
        print("COPY_VERIFIED; deletion NOT authorized. Set TCCAS_CONFIRM_DELETE=YES after reviewing dependencies.")
        return
    jobs_reference(root)
    if tree(root)[0]!=rec["entries"]:die("Source changed before deletion")
    shutil.rmtree(root)
    rec["removed"]=True
    man.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+"\n")
    print("MOVED_AND_REMOVED",root,flush=True)
def main():
    a=argparse.ArgumentParser()
    a.add_argument("mode",choices=("inspect","copy","move"))
    a.add_argument("--source",type=P,action="append",default=[])
    args=a.parse_args()
    selected,other=discover()
    for src in args.source:
        if not src.is_absolute() or not src.is_dir() or src.is_symlink() or src.name not in NAMES:
            die("Invalid --source; use exact TCCAS directory path")
        if src not in selected:selected.append(src)
    print("SELECTED:",*(str(s) for s in selected),sep="\n  ")
    print("OTHER UNCLASSIFIED SCRATCH CANDIDATES:",*(str(s) for s in other),sep="\n  ")
    if args.mode=="inspect":
        for s in selected:
            e,links=tree(s)
            print(s,"entries",len(e),"files",sum(v["kind"]=="file" for v in e.values()),"external links",len(links))
            for l in links:print(" EXTERNAL",l)
        return
    if other:die("Additional Scratch candidates found; classify before any move")
    if not selected:die("No selected TCCAS directories")
    for s in selected:archive(s,args.mode)
if __name__=="__main__":
    try:main()
    except (RuntimeError,OSError,tarfile.TarError) as e:
        print("STOP:",e,file=sys.stderr);sys.exit(2)
