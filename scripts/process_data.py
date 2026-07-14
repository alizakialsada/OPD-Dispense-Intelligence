from pathlib import Path
from datetime import datetime,timedelta
from collections import defaultdict,Counter
import pandas as pd,json,glob
ROOT=Path(__file__).resolve().parents[1]; IN=ROOT/"incoming"; DATA=ROOT/"data"
ALIASES={"id":["Patient ID","MRN"],"name":["Patient Name","Name"],"drug":["Drug Name","Medication"],"disp":["Disp Date","Dispense Date"],"qty":["Disp Qty","Dispensed Qty"],"spec":["Speciality","Specialty"],"loc":["Location","Clinic"]}
def col(cols,names):
 m={str(c).strip().lower():c for c in cols};return next((m[n.lower()] for n in names if n.lower() in m),None)
def s(v):return "" if pd.isna(v) else str(v).strip()
def main():
 files=sorted([*IN.glob("*.xlsx"),*IN.glob("*.xls")])
 if not files: raise SystemExit("No Excel report found in incoming/")
 latest={};raw=valid=0
 for f in files:
  df=pd.read_excel(f);c={k:col(df.columns,v) for k,v in ALIASES.items()}
  if not c["id"] or not c["drug"] or not c["disp"]:raise ValueError(f"{f.name}: missing required columns")
  for _,r in df.iterrows():
   raw+=1;pid=s(r[c["id"]]);drug=s(r[c["drug"]]);d=pd.to_datetime(r[c["disp"]],errors="coerce",dayfirst=True)
   if not pid or not drug or pd.isna(d):continue
   valid+=1;rec={"id":pid,"name":s(r[c["name"]]) if c["name"] else "","drug":drug,"last":d.date().isoformat(),"qty":float(r[c["qty"]]) if c["qty"] and pd.notna(r[c["qty"]]) else 0,"speciality":s(r[c["spec"]]) if c["spec"] else "","location":s(r[c["loc"]]) if c["loc"] else ""}
   k=(pid,drug.casefold())
   if k not in latest or rec["last"]>latest[k]["last"]:latest[k]=rec
 by=defaultdict(list)
 for x in latest.values():by[x["id"]].append(x)
 patients=[]
 for pid,meds in by.items():
  counts=Counter(m["last"] for m in meds);dom=max(d for d,cnt in counts.items() if cnt==max(counts.values()));p=max(meds,key=lambda x:x["last"])
  patients.append({"id":pid,"name":p["name"],"base_last":dom,"meds":len(meds),"aligned":sum(m["last"]==dom for m in meds),"exceptions":sum(m["last"]!=dom for m in meds),"speciality":p["speciality"],"location":p["location"],"drug_text":" | ".join(sorted({m["drug"] for m in meds})[:10])})
 patients.sort(key=lambda x:(x["base_last"],x["name"],x["id"]))
 for f in DATA.glob("patients-*.json"):f.unlink()
 chunks=[]
 for i in range(0,len(patients),750):
  name=f"patients-{i//750:02d}.json";(DATA/name).write_text(json.dumps(patients[i:i+750],ensure_ascii=False,separators=(",",":")),encoding="utf-8");chunks.append(name)
 meta={"generated_at":datetime.now().isoformat(timespec="seconds"),"source_file":files[-1].name,"raw_records":raw,"valid_records":valid,"unique_patients":len(patients),"patient_medication_records":len(latest),"chunks":chunks,"default_interval":25}
 (DATA/"meta.json").write_text(json.dumps(meta,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
if __name__=="__main__":main()
