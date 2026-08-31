#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,math,resource,struct,time
from pathlib import Path
import numpy as np
CAMPAIGN=Path(__file__).resolve().parents[1];ROWS=85651;COLUMNS=35881;RHS=4;P=181
BASE=CAMPAIGN/'artifacts/third-colon-p181-sparse4-two-digit-lift-v2';CERT=CAMPAIGN/'artifacts/third-colon-p181-sparse4-exact-rational-replay-v1';EXACT=BASE/'integral/A_Z_b4_Z_coefficient_primitive.i64csr';PAIRS=CERT/'rational_sparse4_pairs_row_major.json';COMMON=CERT/'primitive_common_denominator_vectors.json';X4=CAMPAIGN/'artifacts/third-colon-p181-sparse4-four-digit-extension-v1/X_mod_181_power_4_sparse4_row_major.u32le';SOURCE_AUDIT=CAMPAIGN/'receipts/hsop-j2-secant-r10-p181-sparse4-two-digit-lift-independent-audit.json';OUTPUT=CAMPAIGN/'receipts/hsop-j2-secant-r10-p181-sparse4-exact-rational-independent-audit.json'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def req(c,m):
 if not c:raise ValueError(m)
def read_exact():
 b=EXACT.read_bytes();req(b[:8]==b'HC4S4181','magic');r,c,n,k=struct.unpack_from('<QQQQ',b,8);req((r,c,k)==(ROWS,COLUMNS,RHS),'dims');q=40;off=np.frombuffer(b,dtype='<u8',count=r+1,offset=q).copy();q+=8*(r+1);ind=np.frombuffer(b,dtype='<u4',count=n,offset=q).copy();q+=4*n;val=np.frombuffer(b,dtype='<i8',count=n,offset=q).copy();q+=8*n;rhs=np.frombuffer(b,dtype='<i8',count=r*k,offset=q).copy().reshape(r,k);q+=8*r*k;req(q==len(b),'trailing');return off,ind,val,rhs
def main():
 start=time.perf_counter();req(not OUTPUT.exists(),'output exists');source=json.loads(SOURCE_AUDIT.read_text());req(source.get('status')=='PASS_INDEPENDENT_P181_SPARSE4_TWO_DIGIT_LIFT_REPLAY','source audit');req(source['exact_source_reconstruction']['coefficient_row_mismatch_count']==0 and source['exact_source_reconstruction']['rhs_row_mismatch_count']==0,'source mismatches');req(source['bound_hashes']['exact_system']==h(EXACT),'source exact hash')
 pairs=json.loads(PAIRS.read_text());common=json.loads(COMMON.read_text());den=list(map(int,common['denominators']));nums=[[int(v) for v in row] for row in common['integer_numerator_matrix_row_major']];req(len(pairs)==len(nums)==COLUMNS and all(len(r)==RHS for r in pairs) and len(den)==RHS,'certificate dims');encoding_mismatches=normalization_mismatches=0
 for i in range(COLUMNS):
  for j in range(RHS):
   n,d=map(int,pairs[i][j]);normalization_mismatches+=d<=0 or math.gcd(abs(n),d)!=1 or den[j]%d!=0;encoding_mismatches+=nums[i][j]!=n*(den[j]//d)
 req(normalization_mismatches==encoding_mismatches==0,'certificate encoding')
 modulus=P**4;res=np.frombuffer(X4.read_bytes(),dtype='<u4').reshape(COLUMNS,RHS);reduction_mismatches=sum(nums[i][j]%modulus*pow(den[j]%modulus,-1,modulus)%modulus!=int(res[i,j]) for i in range(COLUMNS) for j in range(RHS));req(reduction_mismatches==0,'reduction')
 off,ind,val,rhs=read_exact();mismatches=0;digest=hashlib.sha256()
 for row in range(ROWS):
  totals=[0]*RHS
  for k in range(int(off[row]),int(off[row+1])):
   c=int(val[k]);v=nums[int(ind[k])]
   for j in range(RHS):totals[j]+=c*v[j]
  for j in range(RHS):
   z=totals[j]-den[j]*int(rhs[row,j]);mismatches+=z!=0;digest.update(f'{z}\n'.encode())
 req(mismatches==0,'exact replay');resources={'wall_seconds':time.perf_counter()-start,'maximum_rss_native':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'process_swaps':int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)};req(resources['process_swaps']==0 and resources['wall_seconds']<120,'resources')
 receipt={'schema':'hc4.third-colon-p181-sparse4-exact-rational-independent-audit.v1','status':'PASS_INDEPENDENT_P181_SPARSE4_EXACT_RATIONAL_SOURCE_SYZYGIES','bound_hashes':{'exact_system':h(EXACT),'pairs':h(PAIRS),'common_denominator_vectors':h(COMMON),'p4_residues':h(X4),'independent_source_audit':h(SOURCE_AUDIT)},'certificate_checks':{'coordinate_count':COLUMNS*RHS,'normalization_mismatch_count':normalization_mismatches,'encoding_mismatch_count':encoding_mismatches,'p4_reduction_mismatch_count':reduction_mismatches},'exact_replay':{'scalar_comparisons':ROWS*RHS,'mismatch_count':mismatches,'residual_stream_sha256':digest.hexdigest()},'source_composition':{'exact_integer_system_independently_reconstructed_from_rational_source':True,'source_audit_status':source['status']},'resources':resources,'declarations':{'solver_not_executed':True,'p_adic_lifter_not_imported_or_executed':True,'rational_replay_reimplemented':True},'claim_boundary':'This PASS independently certifies four rational residual syzygies in the fixed source chart. It does not prove all 114 lift, the third-colon target identity, a colon, saturation, secant closure, nullcone containment, or HC4.'};OUTPUT.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':receipt['status'],'receipt':str(OUTPUT),'sha256':h(OUTPUT)}));return 0
if __name__=='__main__':raise SystemExit(main())
