#!/usr/bin/env -S sage -python
"""Apply the frozen p96 exact-recovery hierarchy."""

from __future__ import annotations

import argparse, hashlib, json, math, resource, struct, time
from pathlib import Path
from sage.all import Matrix, ZZ

CAMPAIGN=Path(__file__).resolve().parents[1]; P=173; ROWS=85688; COLUMNS=36587; NONZEROS=1487624
MODULUS=P**96; DIMS=(8,16,24,32); SAMPLE=512
SYSTEM=CAMPAIGN/"artifacts/fourth-colon-p173-fixed-gauge-integral-lift-system-v1"
P54=CAMPAIGN/"artifacts/fourth-colon-p173-target-54digit-extension-v1"; P96=CAMPAIGN/"artifacts/fourth-colon-p173-target-96digit-extension-v1"
INTEGRAL=SYSTEM/"A_Z_b_Z_fixed_gauge_p173.i64csr"; X54=P54/"X_mod_173_power_54.json"; X96=P96/"X_mod_173_power_96.json"
AUDIT=CAMPAIGN/"receipts/hsop-j2-secant-r10-fourth-colon-p173-96digit-extension-independent-audit.json"

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def require(c,m):
    if not c: raise ValueError(m)
def rr(a,m):
    a%=m
    if a==0:return (0,1)
    b=math.isqrt((m-1)//2); r0,r1=m,a; t0,t1=0,1
    while abs(r1)>b:
        q=r0//r1; r0,r1=r1,r0-q*r1; t0,t1=t1,t0-q*t1
    n,d=r1,t1
    if d<0:n,d=-n,-d
    if d<=0 or abs(n)>b or d>b or math.gcd(abs(n),d)!=1 or (a*d-n)%m:return None
    return n,d
def read_system():
    b=INTEGRAL.read_bytes(); require(b[:8]==b"HC4ZI173","magic"); rows,cols,nnz=struct.unpack_from("<QQQ",b,8); require((rows,cols,nnz)==(ROWS,COLUMNS,NONZEROS),"dimensions"); c=32
    off=list(struct.unpack_from(f"<{rows+1}Q",b,c)); c+=8*(rows+1); ind=[x[0] for x in struct.iter_unpack("<I",b[c:c+4*nnz])]; c+=4*nnz; val=[x[0] for x in struct.iter_unpack("<q",b[c:c+8*nnz])]; c+=8*nnz; rhs=[x[0] for x in struct.iter_unpack("<q",b[c:c+8*rows])]; c+=8*rows; require(c==len(b),"trailing"); return off,ind,val,rhs
def centered(residues,D):
    half=MODULUS//2; out=[]
    for x in residues:
        v=D*x%MODULUS; out.append(v-MODULUS if v>half else v)
    return out
def replay(N,D,limit,off,ind,val,rhs):
    mis=0; maximum=0; h=hashlib.sha256()
    for row in range(limit):
        residual=sum(val[j]*N[ind[j]] for j in range(off[row],off[row+1]))-D*rhs[row]
        mis+=residual!=0; maximum=max(maximum,abs(residual)); h.update(f"{residual}\n".encode())
    return mis,maximum,h.hexdigest()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output-dir",type=Path,required=True); a=ap.parse_args(); started=time.perf_counter(); out=a.output_dir if a.output_dir.is_absolute() else CAMPAIGN/a.output_dir; out.mkdir(parents=True,exist_ok=False)
    audit=json.loads(AUDIT.read_text()); require(audit.get("status")=="PASS_INDEPENDENT_P173_FOURTH_COLON_96DIGIT_LIFT_REPLAY","audit status")
    x96=[int(v) for v in json.loads(X96.read_text())]; require(len(x96)==COLUMNS and audit["bound_hashes"]["x96"]==digest(X96),"x96 drift")
    x84=[int(v) for v in json.loads(X54.read_text())]; place=P**54
    for j in range(54,84):
        digit=list((P96/f"digit_{j:02d}.u8").read_bytes()); require(len(digit)==COLUMNS,"digit drift"); x84=[u+place*v for u,v in zip(x84,digit,strict=True)]; place*=P
    require(place==P**84,"p84 modulus")
    pairs96=[rr(x,MODULUS) for x in x96]; pairs84=[rr(x,P**84) for x in x84]
    off,ind,val,rhs=read_system(); attempts=[]; Dpass=None; Npass=None; mode=None
    if all(pair is not None for pair in pairs96):
        D=1
        for n,d in pairs96:D=math.lcm(D,d)
        N=[n*(D//d) for n,d in pairs96]; mis,mx,hd=replay(N,D,ROWS,off,ind,val,rhs); attempts.append({"mode":"complete_equal_height","denominator_bits":D.bit_length(),"full_mismatches":mis,"maximum_residual":str(mx),"residual_sha256":hd})
        if mis==0:Dpass,Npass,mode=D,N,"complete_equal_height"
    stable=[i for i,(u,v) in enumerate(zip(pairs84,pairs96,strict=True)) if u is not None and u[0]!=0 and u==v]
    L=1
    for i in stable:L=math.lcm(L,pairs96[i][1])
    if Dpass is None:
        N=centered(x96,L); mis,mx,hd=replay(N,L,ROWS,off,ind,val,rhs); attempts.append({"mode":"stable_lcm","denominator_bits":L.bit_length(),"full_mismatches":mis,"maximum_residual":str(mx),"residual_sha256":hd})
        if mis==0:Dpass,Npass,mode=L,N,"stable_lcm"
    unresolved=[i for i,pair in enumerate(pairs96) if pair is None]; lll=[]; seen=set()
    if Dpass is None:
        y=[L*x%MODULUS for x in x96]
        for k in DIMS:
            selected=unresolved[:k]; B=Matrix(ZZ,k+1,k+1)
            for i in range(k):B[i,i]=MODULUS; B[k,i]=y[selected[i]]
            B[k,k]=1; tick=time.perf_counter(); R=B.LLL(); run={"dimension":k,"seconds":time.perf_counter()-tick,"candidates":[]}
            for pos,row in enumerate(R.rows()):
                e=abs(int(row[-1])); D=L*e
                if e==0 or D in seen:continue
                seen.add(D); rec={"row":pos,"denominator_bits":D.bit_length(),"divisible_by_173":D%P==0}; run["candidates"].append(rec)
                if D%P==0:continue
                N=centered(x96,D); mis,mx,hd=replay(N,D,SAMPLE,off,ind,val,rhs); rec.update({"sample_mismatches":mis,"sample_maximum":str(mx),"sample_sha256":hd})
                if mis:continue
                mis,mx,hd=replay(N,D,ROWS,off,ind,val,rhs); rec.update({"full_mismatches":mis,"full_maximum":str(mx),"full_sha256":hd})
                if mis==0:Dpass,Npass,mode=D,N,f"lll_dimension_{k}"; break
            lll.append(run)
            if Dpass is not None:break
    passed=Dpass is not None; vector=None
    if passed:
        p=out/"primitive_common_denominator_vector.json"; p.write_text(json.dumps({"denominator":Dpass,"integer_numerators":Npass},separators=(",",":"))+"\n"); vector={"path":p.name,"sha256":digest(p),"bytes":p.stat().st_size}
    resources={"wall_seconds":time.perf_counter()-started,"maximum_rss_native":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"process_swaps":int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}; require(resources["wall_seconds"]<1800 and resources["maximum_rss_native"]<2_000_000_000 and resources["process_swaps"]==0,"resource gate")
    status="PASS_P173_FOURTH_COLON_TARGET_EXACT_RATIONAL_SYSTEM_REPLAY" if passed else "NO_P173_FOURTH_COLON_EXACT_RECOVERY_IN_FROZEN_P96_HIERARCHY"
    receipt={"schema":"hc4.fourth-colon-p173-p96-exact-recovery.v1","status":status,"inputs":{"integral":digest(INTEGRAL),"x54":digest(X54),"x96":digest(X96),"p96_audit":digest(AUDIT)},"p96_equal_height":{"resolved":sum(p is not None for p in pairs96),"unresolved":len(unresolved)},"p84_to_p96_stable":{"nonzero_count":len(stable),"index_sha256":hashlib.sha256(json.dumps(stable,separators=(",",":")).encode()).hexdigest(),"denominator_lcm":str(L),"denominator_bits":L.bit_length()},"direct_attempts":attempts,"lll_runs":lll,"passing_mode":mode,"exact_vector":vector,"resources":resources,"declarations":{"fixed_hierarchy":True,"alternate_subset_or_scaling_forbidden":True,"new_digit_forbidden":True},"claim_boundary":"A PASS proves exact rational membership in the frozen target system and requires source-level polynomial replay; exhaustion rejects only this recovery hierarchy. No colon equality, saturation, nullcone containment, or HC4 theorem follows."}
    rp=out/"replay.json"; rp.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n"); print(json.dumps({"status":status,"receipt":str(rp),"sha256":digest(rp)})); return 0 if passed else 4
if __name__=="__main__":raise SystemExit(main())
