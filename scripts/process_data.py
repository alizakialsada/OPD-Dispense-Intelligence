from pathlib import Path
from datetime import datetime, timedelta, date
from collections import defaultdict, Counter
import json, re, zipfile, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "incoming"
DATA = ROOT / "data"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

ALIASES = {
    "id": ["Patient ID", "MRN"], "name": ["Patient Name", "Patient EName", "Name"],
    "drug": ["Drug Name", "Medication"], "disp": ["Disp Date", "Dispense Date"],
    "qty": ["Disp Qty", "Dispensed Qty", "Dispensed Quantity"],
    "spec": ["Speciality", "Specialty"], "loc": ["Location", "Clinic"],
    "national_id": ["ID", "Identification Number", "National ID"],
    "mobile": ["mobile_phone", "Mobile Number", "Mobile"],
    "national_address": ["Short Adress", "Short Address", "National Address", "nati"],
    "order_date": ["Order Date", "Prescription Start Date"],
    "prescription": ["Prescription", "Duration"],
    "prescription_no": ["Prescription No", "Prescription Number"],
}

def clean(v):
    if v is None: return ""
    s = str(v).strip()
    return "" if s.lower() in {"nan", "none", "0.0"} else s

def parse_date(v):
    s = clean(v)
    if not s: return None
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y"):
        try: return datetime.strptime(s, f).date()
        except ValueError: pass
    try:
        n = float(s)
        return date(1899, 12, 30) + timedelta(days=n)
    except Exception:
        return None

def estimate_rx_end(order_date, prescription):
    if not order_date: return ""
    txt = clean(prescription)
    m = re.search(r"for\s+(\d+(?:\.\d+)?)\s*(day|week|month|year)", txt, re.I)
    if not m: return ""
    n = float(m.group(1)); unit = m.group(2).lower()
    days = n if unit == "day" else n*7 if unit == "week" else n*30 if unit == "month" else n*365
    return (order_date + timedelta(days=round(days))).isoformat()

def col_idx(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters: n = n*26 + ord(ch)-64
    return n-1

def read_xlsx_rows(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(NS+"si"):
                shared.append("".join(t.text or "" for t in si.iter(NS+"t")))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        relroot = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        relmap = {r.attrib["Id"]: r.attrib["Target"] for r in relroot}
        sheets = []
        for sh in wb.find(NS+"sheets"):
            target = relmap[sh.attrib[REL_NS+"id"]]
            sheets.append((sh.attrib["name"], "xl/"+target.lstrip("/")))
        required = {"patient id", "drug name", "disp date"}
        selected = None
        for name, spath in sheets:
            with z.open(spath) as fh:
                header = None
                for _, elem in ET.iterparse(fh, events=("end",)):
                    if elem.tag == NS+"row":
                        vals = {}
                        for c in elem.findall(NS+"c"):
                            ref = c.attrib.get("r", "A1"); typ = c.attrib.get("t")
                            val = ""
                            if typ == "inlineStr":
                                isel = c.find(NS+"is")
                                val = "".join(t.text or "" for t in isel.iter(NS+"t")) if isel is not None else ""
                            else:
                                v = c.find(NS+"v")
                                if v is not None:
                                    val = v.text or ""
                                    if typ == "s": val = shared[int(val)]
                            vals[col_idx(ref)] = val
                        if vals:
                            header = [vals.get(i, "") for i in range(max(vals)+1)]
                        elem.clear(); break
                if header and required.issubset({clean(x).lower() for x in header}):
                    selected = (name, spath, header); break
        if not selected: raise ValueError(f"{path.name}: no sheet with Patient ID, Drug Name and Disp Date")
        _, spath, headers = selected
        with z.open(spath) as fh:
            first = True
            for _, elem in ET.iterparse(fh, events=("end",)):
                if elem.tag != NS+"row": continue
                if first: first = False; elem.clear(); continue
                vals = {}
                for c in elem.findall(NS+"c"):
                    ref = c.attrib.get("r", "A1"); typ = c.attrib.get("t")
                    val = ""
                    if typ == "inlineStr":
                        isel = c.find(NS+"is")
                        val = "".join(t.text or "" for t in isel.iter(NS+"t")) if isel is not None else ""
                    else:
                        v = c.find(NS+"v")
                        if v is not None:
                            val = v.text or ""
                            if typ == "s": val = shared[int(val)]
                    vals[col_idx(ref)] = val
                if vals: yield {headers[i]: vals.get(i, "") for i in range(len(headers))}
                elem.clear()

def find_col(headers, names):
    lookup = {clean(h).lower(): h for h in headers}
    return next((lookup[n.lower()] for n in names if n.lower() in lookup), None)

def recurring_dates(last_iso, end_iso, interval):
    if not last_iso or not end_iso: return []
    try:
        d=date.fromisoformat(last_iso)+timedelta(days=interval)
        end=date.fromisoformat(end_iso)
    except Exception:
        return []
    out=[]
    # Keep current/upcoming preparation dates only; each following monthly cycle is 30 days.
    floor=date.today()-timedelta(days=1)
    while d <= end:
        if d >= floor: out.append(d.isoformat())
        d += timedelta(days=30)
    return out

def main():
    files = sorted(IN.glob("*.xlsx"))
    if not files: raise SystemExit("No .xlsx report found in incoming/")
    latest = {}; demographics = {}; raw = valid = 0
    for f in files:
        rows = read_xlsx_rows(f)
        first = next(rows, None)
        if first is None: continue
        headers = list(first.keys()); cols = {k: find_col(headers,v) for k,v in ALIASES.items()}
        if not cols["id"] or not cols["drug"] or not cols["disp"]: raise ValueError(f"{f.name}: missing required columns")
        for row in [first, *rows]:
            raw += 1
            pid=clean(row.get(cols["id"])); drug=clean(row.get(cols["drug"])); d=parse_date(row.get(cols["disp"]))
            if not pid or not drug or not d: continue
            valid += 1
            qty_raw=clean(row.get(cols["qty"])) if cols["qty"] else ""
            try: qty=float(qty_raw or 0)
            except: qty=0
            order=parse_date(row.get(cols["order_date"])) if cols["order_date"] else None
            rec={"id":pid,"name":clean(row.get(cols["name"])) if cols["name"] else "","drug":drug,"last":d.isoformat(),"qty":qty,
                 "speciality":clean(row.get(cols["spec"])) if cols["spec"] else "","location":clean(row.get(cols["loc"])) if cols["loc"] else "",
                 "national_id":clean(row.get(cols["national_id"])) if cols["national_id"] else "","mobile":clean(row.get(cols["mobile"])) if cols["mobile"] else "",
                 "national_address":clean(row.get(cols["national_address"])) if cols["national_address"] else "","order_date":order.isoformat() if order else "",
                 "prescription":clean(row.get(cols["prescription"])) if cols["prescription"] else "","prescription_no":clean(row.get(cols["prescription_no"])) if cols["prescription_no"] else ""}
            rec["rx_end"] = estimate_rx_end(order, rec["prescription"])
            demo=demographics.setdefault(pid,{})
            for k in ("name","national_id","mobile","national_address"):
                if rec[k]: demo[k]=rec[k]
            same=(pid,drug.casefold(),rec["last"])
            if same in latest: latest[same]["qty"] += qty
            else: latest[same]=rec
    # Keep latest dispense date per MRN + medication after same-date quantity aggregation.
    med_latest={}
    for rec in latest.values():
        k=(rec["id"],rec["drug"].casefold())
        if k not in med_latest or rec["last"]>med_latest[k]["last"]: med_latest[k]=rec
    by=defaultdict(list)
    for x in med_latest.values(): by[x["id"]].append(x)
    patients=[]; demand=[]
    for pid, meds in by.items():
        counts=Counter(m["last"] for m in meds); top=max(counts.values()); dom=max(d for d,c in counts.items() if c==top)
        p=max(meds,key=lambda x:x["last"]); demo=demographics.get(pid,{})
        patient={"id":pid,"name":demo.get("name") or p["name"],"base_last":dom,"meds":len(meds),"aligned":sum(m["last"]==dom for m in meds),
                 "exceptions":sum(m["last"]!=dom for m in meds),"speciality":p["speciality"],"location":p["location"],
                 "national_id":demo.get("national_id",p["national_id"]),"mobile":demo.get("mobile",p["mobile"]),
                 "national_address":demo.get("national_address",p["national_address"]),
                 "drug_text":" | ".join(sorted({m["drug"] for m in meds})[:10]),"prescription_end":max((m["rx_end"] for m in meds if m["rx_end"]),default="")}
        schedules={}
        for interval in (15,20,25,30):
            dates=set()
            for m in meds:
                dates.update(recurring_dates(m["last"],m.get("rx_end") or "",interval))
            schedules[str(interval)]=sorted(dates)
        patient["schedule_dates"]=schedules
        patients.append(patient)
        demand.append({"id":pid,"name":patient["name"],"speciality":patient["speciality"],"base_last":dom,
                       "items":[{"drug":m["drug"],"qty":m["qty"],"last":m["last"],"end":m.get("rx_end","")} for m in meds]})
    patients.sort(key=lambda x:(x["base_last"],x["name"],x["id"]))
    for old in DATA.glob("patients-*.json"): old.unlink()
    chunks=[]
    for i in range(0,len(patients),750):
        name=f"patients-{i//750:02d}.json"; (DATA/name).write_text(json.dumps(patients[i:i+750],ensure_ascii=False,separators=(",",":")),encoding="utf-8"); chunks.append(name)
    demand_dir=DATA/"demand"; demand_dir.mkdir(exist_ok=True)
    for old in demand_dir.glob("demand-*.json"): old.unlink()
    demand_chunks=[]
    for i in range(0,len(demand),700):
        name=f"demand-{i//700:02d}.json"; (demand_dir/name).write_text(json.dumps(demand[i:i+700],ensure_ascii=False,separators=(",",":")),encoding="utf-8"); demand_chunks.append(f"data/demand/{name}")
    (DATA/"demand-meta.json").write_text(json.dumps({"patients":len(demand),"chunks":demand_chunks},separators=(",",":")),encoding="utf-8")
    for interval in (15,20,25,30):
        pre=DATA/"precomputed"/str(interval); pre.mkdir(parents=True,exist_ok=True)
        for old in pre.glob("demand-*.json"): old.unlink()
        cal=defaultdict(lambda:{"patients":set(),"medications":set(),"quantity":0.0})
        day=defaultdict(lambda:defaultdict(lambda:{"patients":set(),"quantity":0.0,"patientRows":[]}))
        for x in demand:
            for item in x["items"]:
                for eligible in recurring_dates(item["last"],item.get("end") or "",interval):
                    drug=item["drug"]; qty=float(item.get("qty") or 0); cal[eligible]["patients"].add(x["id"]); cal[eligible]["medications"].add(drug); cal[eligible]["quantity"]+=qty
                    r=day[eligible][drug]; r["patients"].add(x["id"]); r["quantity"]+=qty; r["patientRows"].append({"mrn":x["id"],"name":x["name"],"speciality":x["speciality"],"qty":qty})
        (pre/"calendar.json").write_text(json.dumps({k:{"patients":len(v["patients"]),"medications":len(v["medications"]),"quantity":round(v["quantity"],2)} for k,v in sorted(cal.items())},separators=(",",":")),encoding="utf-8")
        didx={}
        for d,drugs in sorted(day.items()):
            rows=[]
            for drug,v in drugs.items():
                n=len(v["patients"]); rows.append({"drug":drug,"patients":n,"qty":round(v["quantity"],2),"avg":round(v["quantity"]/n,2) if n else 0,"patientRows":v["patientRows"]})
            rows.sort(key=lambda r:(-r["qty"],-r["patients"],r["drug"])); fn=f"demand-{d}.json"; (pre/fn).write_text(json.dumps({"date":d,"rows":rows},ensure_ascii=False,separators=(",",":")),encoding="utf-8"); didx[d]=f"data/precomputed/{interval}/{fn}"
        (pre/"demand-index.json").write_text(json.dumps(didx,separators=(",",":")),encoding="utf-8")
    meta={"generated_at":datetime.now().isoformat(timespec="seconds"),"source_file":files[-1].name,"raw_records":raw,"valid_records":valid,"unique_patients":len(patients),"patient_medication_records":len(med_latest),"chunks":chunks,"default_interval":20,"recurring_until_prescription_end":True}
    (DATA/"meta.json").write_text(json.dumps(meta,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(json.dumps(meta,indent=2))
if __name__=="__main__": main()
