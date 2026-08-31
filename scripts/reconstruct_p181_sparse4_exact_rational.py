#!/usr/bin/env python3
"""Equal-height reconstruct and exactly replay four p^4 residual sections."""

from __future__ import annotations
import argparse, hashlib, json, math, resource, struct, time
from pathlib import Path
import numpy as np

CAMPAIGN=Path(__file__).resolve().parents[1]; P=181; ROWS=85651; COLUMNS=35881; RHS=4
SOURCE=CAMPAIGN/"artifacts/third-colon-p181-sparse4-two-digit-lift-v2"
EXTENSION=CAMPAIGN/"artifacts/third-colon-p181-sparse4-four-digit-extension-v1"
EXACT=SOURCE/"integral/A_Z_b4_Z_coefficient_primitive.i64csr"; X4=EXTENSION/"X_mod_181_power_4_sparse4_row_major.u32le"

def file_hash(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def require(c,m):
    if not c: raise ValueError(m)
def rr(a,m):
    a=int(a)%m
    if a==0:return (0,1)
    bound=math.isqrt((m-1)//2); r0,r1=m,a; t0,t1=0,1
    while abs(r1)>bound:
        q,r2=divmod(r0,r1); r0,r1=r1,r2; t0,t1=t1,t0-q*t1
    n,d=r1,t1
    if d<0:n,d=-n,-d
    if d>0 and abs(n)<=bound and d<=bound and math.gcd(abs(n),d)==1 and (a*d-n)%m==0:return (n,d)
    return None
def read_exact():
    b=EXACT.read_bytes(); require(b[:8]==b"HC4S4181","magic"); rows,cols,nnz,rhsn=struct.unpack_from("<QQQQ",b,8); require((rows,cols,rhsn)==(ROWS,COLUMNS,RHS),"dimensions"); c=40
    off=np.frombuffer(b,dtype='<u8',count=rows+1,offset=c).copy(); c+=8*(rows+1); ind=np.frombuffer(b,dtype='<u4',count=nnz,offset=c).copy(); c+=4*nnz; val=np.frombuffer(b,dtype='<i8',count=nnz,offset=c).copy(); c+=8*nnz; rhs=np.frombuffer(b,dtype='<i8',count=rows*rhsn,offset=c).copy().reshape(rows,rhsn); c+=8*rows*rhsn; require(c==len(b),"trailing"); return off,ind,val,rhs
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output-dir',type=Path,required=True); a=ap.parse_args(); start=time.perf_counter(); out=a.output_dir if a.output_dir.is_absolute() else CAMPAIGN/a.output_dir; out.mkdir(parents=True,exist_ok=False)
    modulus=P**4; residues=np.frombuffer(X4.read_bytes(),dtype='<u4').reshape(COLUMNS,RHS); pairs=[]
    for row in residues:
        reconstructed=[rr(v,modulus) for v in row]; require(all(v is not None for v in reconstructed),"unresolved coordinate"); pairs.append(reconstructed)
    denominators=[math.lcm(*(pairs[i][j][1] for i in range(COLUMNS))) for j in range(RHS)]
    numerators=[[pairs[i][j][0]*(denominators[j]//pairs[i][j][1]) for j in range(RHS)] for i in range(COLUMNS)]
    reduction_mismatches=sum((numerators[i][j]%modulus)*pow(denominators[j]%modulus,-1,modulus)%modulus!=int(residues[i,j]) for i in range(COLUMNS) for j in range(RHS)); require(reduction_mismatches==0,"p4 reduction mismatch")
    off,ind,val,rhs=read_exact(); exact_mismatches=0; digest=hashlib.sha256()
    for row in range(ROWS):
        totals=[0]*RHS
        for k in range(int(off[row]),int(off[row+1])):
            coeff=int(val[k]); vector=numerators[int(ind[k])]
            for j in range(RHS): totals[j]+=coeff*vector[j]
        for j in range(RHS):
            residual=totals[j]-denominators[j]*int(rhs[row,j]); exact_mismatches+=residual!=0; digest.update(f"{residual}\n".encode())
    require(exact_mismatches==0,"exact rational replay mismatch")
    rational_path=out/'rational_sparse4_pairs_row_major.json'; rational_path.write_text(json.dumps(pairs,separators=(',',':'))+'\n')
    integer_path=out/'primitive_common_denominator_vectors.json'; integer_path.write_text(json.dumps({'denominators':denominators,'integer_numerator_matrix_row_major':numerators},separators=(',',':'))+'\n')
    support=[sum(pairs[i][j][0]!=0 for i in range(COLUMNS)) for j in range(RHS)]; resources={'wall_seconds':time.perf_counter()-start,'maximum_rss_native':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'process_swaps':int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)}; require(resources['wall_seconds']<300 and resources['process_swaps']==0,"resource gate")
    receipt={'schema':'hc4.third-colon-p181-sparse4-exact-rational-replay.v1','status':'PASS_P181_SPARSE4_EXACT_RATIONAL_SYSTEM_REPLAY','inputs':{'exact_system_sha256':file_hash(EXACT),'p4_residues_sha256':file_hash(X4)},'reconstruction':{'modulus':modulus,'equal_height_bound':math.isqrt((modulus-1)//2),'coordinate_count':COLUMNS*RHS,'unresolved_count':0,'support_counts':support,'global_denominators':denominators,'global_denominator_bit_lengths':[d.bit_length() for d in denominators],'maximum_absolute_numerators':[max(abs(pairs[i][j][0]) for i in range(COLUMNS)) for j in range(RHS)],'maximum_denominators':[max(pairs[i][j][1] for i in range(COLUMNS)) for j in range(RHS)],'p4_reduction_mismatch_count':reduction_mismatches},'exact_replay':{'scalar_comparisons':ROWS*RHS,'mismatch_count':exact_mismatches,'residual_stream_sha256':digest.hexdigest()},'outputs':{p.name:{'sha256':file_hash(p),'bytes':p.stat().st_size} for p in (rational_path,integer_path)},'resources':resources,'claim_boundary':'This PASS proves four rational residual syzygies for the fixed coefficient chart. It does not prove all 114 lift, the third-colon target identity, a colon, saturation, secant closure, nullcone containment, or HC4.'}
    rp=out/'replay.json'; rp.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n'); print(json.dumps({'status':receipt['status'],'receipt':str(rp),'sha256':file_hash(rp)})); return 0
if __name__=='__main__': raise SystemExit(main())

