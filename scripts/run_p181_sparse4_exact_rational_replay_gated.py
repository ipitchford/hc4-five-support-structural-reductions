#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os
from pathlib import Path
import run_p181_target_blind_linbox_rank_gated as base
CAMPAIGN=Path(__file__).resolve().parents[1]; FREEZE=CAMPAIGN/'receipts/hsop-j2-secant-r10-p181-sparse4-exact-rational-replay-implementation-freeze.json'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run-id',default='20260831T004');a=ap.parse_args();f=json.loads(FREEZE.read_text());base.require(f.get('status')=='PASS_P181_SPARSE4_EXACT_RATIONAL_REPLAY_FREEZE','freeze');
 for rel,w in f['bound_files'].items():base.require(base.file_hash(CAMPAIGN/rel)==w,f'drift {rel}')
 o={k:CAMPAIGN/v for k,v in f['canonical_outputs'].items()};base.require(not any(p.exists() for p in o.values()),'output exists');stage=CAMPAIGN/'artifacts/staging'/f'sparse4-exact-{a.run_id}';telstage=CAMPAIGN/'artifacts/staging'/f'sparse4-exact-telemetry-{a.run_id}';terminal={'schema':'hc4.third-colon-p181-sparse4-exact-rational-terminal.v1','implementation_freeze':{'path':str(FREEZE.relative_to(CAMPAIGN)),'sha256':base.file_hash(FREEZE)}}
 try:
  p=f['policy'];tel=base.supervise(['/Users/admin/.local/bin/sage','-python',str(CAMPAIGN/'scripts/reconstruct_p181_sparse4_exact_rational.py'),'--output-dir',str(stage)],telstage,int(p['wall_seconds_maximum']),int(p['rss_bytes_maximum']));rec=json.loads((stage/'replay.json').read_text()) if (stage/'replay.json').exists() else None;ext=tel.get('external_time') or {};passed=tel['return_code']==0 and not tel['rss_breach_killed'] and ext.get('real_seconds',10**9)<=p['wall_seconds_maximum'] and ext.get('maximum_rss_bytes',10**12)<=p['rss_bytes_maximum'] and ext.get('process_swaps',1)==0 and rec and rec.get('status')=='PASS_P181_SPARSE4_EXACT_RATIONAL_SYSTEM_REPLAY';status='PASS_P181_SPARSE4_EXACT_RATIONAL_SYSTEM_REPLAY' if passed else 'FAIL_P181_SPARSE4_EXACT_RATIONAL_REPLAY_INTEGRITY';terminal.update({'status':status,'telemetry':tel,'claim_boundary':'A PASS proves four rational residual syzygies in the fixed chart only; not all 114, the target identity, colon, saturation, secant, nullcone, or HC4.'});os.rename(stage,o['artifact']);o['telemetry'].parent.mkdir(parents=True,exist_ok=True);os.rename(telstage,o['telemetry']);terminal['promoted']={'artifact':base.tree_hashes(o['artifact']),'telemetry':base.tree_hashes(o['telemetry'])};o['terminal'].write_text(json.dumps(terminal,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':status,'terminal':str(o['terminal']),'sha256':base.file_hash(o['terminal'])}));return 0 if passed else 2
 except Exception as e:
  terminal.setdefault('status','FAIL_P181_SPARSE4_EXACT_RATIONAL_REPLAY_INTEGRITY');terminal['error']=f'{type(e).__name__}: {e}';o['terminal'].parent.mkdir(parents=True,exist_ok=True);o['terminal'].write_text(json.dumps(terminal,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':terminal['status'],'error':terminal['error']}));return 2
if __name__=='__main__':raise SystemExit(main())
