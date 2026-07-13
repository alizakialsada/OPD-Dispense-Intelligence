from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import pandas as pd, json, hashlib, shutil

ROOT=Path(__file__).resolve().parents[1]
INCOMING=ROOT/"incoming"; DATA=ROOT/"data"; DETAILS=DATA/"details"; INTERVAL=25
ALIASES={"patient_id":["Patient ID","MRN"],"patient_name":["Patient Name","Name"],"drug_name":["Drug Name","Medication"],"disp_date":["Disp Date","Dispense Date"],"disp_qty":["Disp Qty","Dispensed Qty"],"qty":["Qty"],"order_id":["Order ID"],"order_date":["Order Date"],"location":["Location","Clinic"],"speciality":["Speciality","Specialty"],"gender":["Gender"],"age":["Age"]}
def col(cols,names):
    m={str(c).strip().lower():c for c in cols}
    return next((m[n.lower()] for n in names if n.lower() in m),None)
def ds(v):
    x=pd.to_datetime(v,errors="coerce",dayfirst=True)
    return None if pd.isna(x) else x.date()
def s(v): return "" if pd.isna(v) else str(v).strip()
def main():
    files=sorted([*INCOMING.glob("*.xlsx"),*INCOMING.glob("*.xls")])
    if not files: raise SystemExit("No Excel files in incoming/")
    latest={}; hist=defaultdict(list); raw=valid=0
    for file in files:
        df=pd.read_excel(file); c={k:col(df.columns,v) for k,v in ALIASES.items()}
        if not c["patient_id"] or not c["drug_name"] or not c["disp_date"]: raise ValueError(f"{file.name}: missing required columns")
        for _,r in df.iterrows():
            raw+=1; pid=s(r[c["patient_id"]]); drug=s(r[c["drug_name"]]); disp=ds(r[c["disp_date"]])
            if not pid or not drug or not disp: continue
            valid+=1
            def v(k): return "" if not c.get(k) else s(r[c[k]])
            rec={"pid":pid,"name":v("patient_name"),"drug":drug,"disp":disp.isoformat(),"next":(disp+timedelta(days=INTERVAL)).isoformat(),"disp_qty":v("disp_qty"),"qty":v("qty"),"order_id":v("order_id"),"order_date":ds(r[c["order_date"]]).isoformat() if c.get("order_date") and ds(r[c["order_date"]]) else "","location":v("location"),"speciality":v("speciality"),"gender":v("gender"),"age":v("age")}
            hist[pid].append(rec); key=(pid,drug.casefold())
            if key not in latest or rec["disp"]>latest[key]["disp"]: latest[key]=rec
    by=defaultdict(list)
    for rec in latest.values(): by[rec["pid"]].append(rec)
    patients=[]; details={}; drug_stats=defaultdict(lambda:{"patients":set(),"specialities":Counter(),"locations":Counter(),"due_dates":Counter()})
    for pid,meds in by.items():
        counts=Counter(m["disp"] for m in meds); mx=max(counts.values()); dominant=max(d for d,cnt in counts.items() if cnt==mx); primary=max(meds,key=lambda x:x["disp"]); bucket=hashlib.md5(pid.encode()).hexdigest()[:2]
        sm={"id":pid,"name":primary["name"],"last":dominant,"next":(datetime.fromisoformat(dominant).date()+timedelta(days=INTERVAL)).isoformat(),"meds":len(meds),"aligned":sum(m["disp"]==dominant for m in meds),"exceptions":sum(m["disp"]!=dominant for m in meds),"speciality":primary["speciality"],"location":primary["location"],"gender":primary["gender"],"age":primary["age"],"drug_text":" | ".join(sorted({m["drug"] for m in meds})[:12]),"bucket":bucket}
        patients.append(sm); details[pid]={"summary":sm,"medications":sorted(meds,key=lambda x:(x["disp"],x["drug"]),reverse=True),"history":sorted(hist[pid],key=lambda x:(x["disp"],x["drug"]))[-80:]}
        for m in meds:
            dsx=drug_stats[m["drug"]]; dsx["patients"].add(pid); dsx["specialities"][m["speciality"] or "Unknown"]+=1; dsx["locations"][m["location"] or "Unknown"]+=1; dsx["due_dates"][m["next"]]+=1
    patients.sort(key=lambda x:(x["next"],x["name"],x["id"]))
    for f in DATA.glob("patients-*.json"): f.unlink()
    if DETAILS.exists(): shutil.rmtree(DETAILS)
    DETAILS.mkdir(parents=True)
    chunks=[]
    for start in range(0,len(patients),1000):
        name=f"patients-{start//1000:02d}.json"; (DATA/name).write_text(json.dumps(patients[start:start+1000],ensure_ascii=False,separators=(",",":")),encoding="utf-8"); chunks.append(name)
    buckets=defaultdict(dict)
    for pid,payload in details.items(): buckets[payload["summary"]["bucket"]][pid]=payload
    for b,payload in buckets.items(): (DETAILS/f"{b}.json").write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    drugs=[]
    for drug,x in drug_stats.items(): drugs.append({"drug":drug,"patients":len(x["patients"]),"top_specialities":x["specialities"].most_common(8),"top_locations":x["locations"].most_common(8),"due_dates":dict(x["due_dates"])})
    drugs.sort(key=lambda x:(-x["patients"],x["drug"])); (DATA/"drugs.json").write_text(json.dumps(drugs,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    meta={"generated_at":datetime.now().isoformat(timespec="seconds"),"source_file":files[-1].name,"source_latest_dispense":max((x["disp"] for x in latest.values()),default=""),"raw_records":raw,"valid_records":valid,"unique_patients":len(patients),"patient_medication_records":len(latest),"date_exceptions":sum(p["exceptions"]>0 for p in patients),"duplicate_or_historical":valid-len(latest),"chunks":chunks}
    (DATA/"meta.json").write_text(json.dumps(meta,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
if __name__=="__main__":main()
