#!/usr/bin/env python3
"""READ-ONLY privacy-minimizing audit of precomputed demand + patients from OPD.
Run: python audit_schedule.py /path/to/OPD-Dispense-Intelligence
Outputs only aggregate counts; does not disclose patient identifiers.
"""
import sys, json, collections
from pathlib import Path
from datetime import date, timedelta

def main(root):
    root=Path(root); data=root/'data'; meta=json.loads((data/'demand-meta.json').read_text(encoding='utf-8'))
    meds=collections.Counter(); patient_dates=collections.defaultdict(set); errors=collections.Counter(); day=collections.Counter()
    checked=0
    for chunk in meta['chunks']:
        path=root/chunk
        for p in json.loads(path.read_text(encoding='utf-8')):
            pid=str(p['id']); dates=set()
            for item in p.get('items',[]):
                checked+=1
                last=item.get('last') or ''; end=item.get('end') or ''
                if not last: errors['missing_last_dispense']+=1; continue
                if not end: errors['missing_prescription_end_manual_review']+=1
                try: due=date.fromisoformat(last)+timedelta(days=20)
                except ValueError: errors['malformed_last_dispense']+=1;continue
                if due.weekday()==4: due-=timedelta(days=1)
                elif due.weekday()==5: due+=timedelta(days=1)
                if end:
                    try:
                        if due>date.fromisoformat(end): errors['due_after_rx_end_should_be_excluded']+=1;continue
                    except ValueError: errors['invalid_prescription_end']+=1; continue
                dates.add(due.isoformat());meds[due.isoformat()]+=1
            for d in dates: day[d]+=1
            if len(dates)>1: errors['patients_with_multiple_medication_due_dates']+=1
    report={'total_patients_in_demand':meta.get('patients'), 'patient_medication_pairs_checked':checked,
            'audit_flags':dict(errors),
            'patients_per_due_day':dict(sorted(day.items())),
            'medication_records_per_due_day':dict(sorted(meds.items()))}
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return report
if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Usage: python audit_schedule.py PATH_TO_OPD_PROJECT')
    main(sys.argv[1])
