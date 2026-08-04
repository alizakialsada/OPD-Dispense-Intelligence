from pathlib import Path
from datetime import datetime, timedelta, date
from collections import defaultdict, Counter
import csv, json, re, zipfile, unicodedata, urllib.request, xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "incoming"
DATA = ROOT / "data"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
INVENTORY_DATA_URL = "https://raw.githubusercontent.com/alizakialsada/QCH-DASBOARD/main/dashboard-data.js"

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
    "order_id": ["Order ID", "Order Id"],
    "dispense_status": ["Dispense", "Dispense Status"],
    "order_status": ["Status", "Order Status", "Prescription Status"],
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


def read_csv_rows(path):
    """Stream a UTF-8 CSV file as dictionaries."""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            return
        for row in reader:
            yield row

def load_contact_master(path):
    """Load patient contact details keyed by Patient ID/MRN."""
    contacts = {}
    if not path.exists():
        return contacts
    for row in read_csv_rows(path):
        headers = list(row.keys())
        id_col = find_col(headers, ALIASES["id"])
        if not id_col:
            raise ValueError(f"{path.name}: missing Patient ID/MRN column")
        pid = clean(row.get(id_col))
        if not pid:
            continue
        name_col = find_col(headers, ALIASES["name"])
        national_id_col = find_col(headers, ALIASES["national_id"])
        mobile_col = find_col(headers, ALIASES["mobile"])
        address_col = find_col(headers, ALIASES["national_address"])
        short_address_col = find_col(headers, ["Short Address", "Short Adress"])
        contacts[pid] = {
            "name": clean(row.get(name_col)) if name_col else "",
            "national_id": clean(row.get(national_id_col)) if national_id_col else "",
            "mobile": clean(row.get(mobile_col)) if mobile_col else "",
            "national_address": (
                clean(row.get(address_col)) if address_col else ""
            ) or (clean(row.get(short_address_col)) if short_address_col else ""),
        }
    return contacts


def normalize_medication_name(value):
    """Normalize Medica and NUPCO medication names for safe exact matching."""
    s = unicodedata.normalize("NFKD", clean(value)).upper()
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\bTRD\b", " ", s)
    s = re.sub(r"\bOLD\b", " ", s)
    s = re.sub(r"\bBOX\s*\d+\b", " ", s)
    s = re.sub(r"[^A-Z0-9.]+", " ", s)
    return " ".join(s.split())

def load_nupco_codes(path):
    """Load NUPCO aliases and return a normalized-name lookup."""
    lookup = {}
    if not path.exists():
        return lookup
    payload = json.loads(path.read_text(encoding="utf-8"))
    for entry in payload.get("entries", []):
        name = normalize_medication_name(entry.get("medication_name", ""))
        code = clean(entry.get("nupco_code", ""))
        if name and code:
            lookup[name] = code
    return lookup

def find_col(headers, names):
    lookup = {clean(h).lower(): h for h in headers}
    return next((lookup[n.lower()] for n in names if n.lower() in lookup), None)


def parse_inventory_data_js(text):
    """Parse QCH-DASBOARD/dashboard-data.js into a NUPCO stock lookup."""
    payload = re.sub(r"^\s*window\.DASHBOARD_DB\s*=\s*", "", text.strip())
    payload = re.sub(r";\s*$", "", payload)
    db = json.loads(payload)
    lookup = {}
    for item in db.get("items", []):
        code = clean(item.get("generic"))
        if not code:
            continue
        try:
            lc = int(round(float(item.get("lc_qty", 0) or 0)))
        except Exception:
            lc = 0
        try:
            mosool = int(round(float(item.get("mosool_qty", 0) or 0)))
        except Exception:
            mosool = 0
        lookup[code] = {"lc": lc, "mosool": mosool}
    updated = clean(db.get("overall", {}).get("last_inventory_update"))
    return lookup, updated

def load_inventory_stock():
    """
    Download the latest Inventory Intelligence data.
    A network failure must not stop Dispense processing; quantities remain blank.
    """
    try:
        req = urllib.request.Request(
            INVENTORY_DATA_URL,
            headers={"User-Agent": "Dispense-Intelligence-GitHub-Action"}
        )
        with urllib.request.urlopen(req, timeout=45) as response:
            text = response.read().decode("utf-8-sig")
        return (*parse_inventory_data_js(text), "")
    except Exception as exc:
        return {}, "", str(exc)

def order_rank(order_date, dispense_date, order_id):
    """Comparable rank for identifying the newest prescription/order."""
    date_part = order_date or dispense_date or ""
    oid = clean(order_id)
    try:
        oid_part = (1, int(float(oid)))
    except Exception:
        oid_part = (0, oid)
    return (date_part, oid_part)

def preparation_date(last_iso, end_iso, interval):
    """Return one preparation date only: latest actual dispense + interval."""
    if not last_iso:
        return ""
    try:
        due = date.fromisoformat(last_iso) + timedelta(days=interval)
    except Exception:
        return ""
    if end_iso:
        try:
            if due > date.fromisoformat(end_iso):
                return ""
        except Exception:
            pass
    return due.isoformat()

def main():
    cutoff = date(2026, 6, 4)
    xlsx_files = sorted(IN.glob("*.xlsx"))
    csv_files = sorted(IN.glob("medica-latest-part-*.csv"))
    files = csv_files + xlsx_files
    if not files:
        raise SystemExit("No Medica .xlsx or medica-latest-part-*.csv report found in incoming/")

    contacts = load_contact_master(DATA / "Patient_Contact_Master.csv")
    nupco_lookup = load_nupco_codes(DATA / "nupco-codes.json")
    inventory_lookup, inventory_updated, inventory_error = load_inventory_stock()
    unmatched_drugs = set()
    latest = {}
    newest_order = {}
    demographics = dict(contacts)
    raw = valid = 0

    for f in files:
        rows = read_csv_rows(f) if f.suffix.lower() == ".csv" else read_xlsx_rows(f)
        first = next(rows, None)
        if first is None:
            continue
        headers = list(first.keys())
        cols = {k: find_col(headers, v) for k, v in ALIASES.items()}
        if not cols["id"] or not cols["drug"] or not cols["disp"]:
            raise ValueError(f"{f.name}: missing required columns")

        for row in [first, *rows]:
            raw += 1
            pid = clean(row.get(cols["id"]))
            drug = clean(row.get(cols["drug"]))
            if not pid or not drug:
                continue

            dispense_status = clean(row.get(cols["dispense_status"])) if cols.get("dispense_status") else ""
            order_status = clean(row.get(cols["order_status"])) if cols.get("order_status") else ""
            disp_date = parse_date(row.get(cols["disp"])) if cols.get("disp") else None
            order_date = parse_date(row.get(cols["order_date"])) if cols.get("order_date") else None
            order_id = clean(row.get(cols["order_id"])) if cols.get("order_id") else ""

            # Track the newest order regardless of dispensing. This prevents an old
            # dispensed prescription from continuing to schedule after a newer Stop.
            order_key = (pid, drug.casefold())
            current_order = {
                "status": order_status,
                "dispense_status": dispense_status,
                "order_date": order_date.isoformat() if order_date else "",
                "dispense_date": disp_date.isoformat() if disp_date else "",
                "order_id": order_id,
            }
            current_rank = order_rank(
                current_order["order_date"],
                current_order["dispense_date"],
                order_id
            )
            old = newest_order.get(order_key)
            if old is None or current_rank > old["rank"]:
                newest_order[order_key] = {"rank": current_rank, **current_order}

            # Only actual dispensing creates a new preparation cycle.
            if dispense_status and dispense_status.casefold() not in {"dispensed", "صرف", "تم الصرف"}:
                continue
            if not disp_date or disp_date < cutoff:
                continue

            valid += 1
            qty_raw = clean(row.get(cols["qty"])) if cols["qty"] else ""
            try: qty = float(qty_raw or 0)
            except Exception: qty = 0
            normalized_drug = normalize_medication_name(drug)
            nupco_code = nupco_lookup.get(normalized_drug, "")
            if not nupco_code:
                unmatched_drugs.add(drug)
            rec = {
                "id": pid,
                "name": clean(row.get(cols["name"])) if cols["name"] else "",
                "drug": drug,
                "nupco_code": nupco_code,
                "last": disp_date.isoformat(),
                "qty": qty,
                "speciality": clean(row.get(cols["spec"])) if cols["spec"] else "",
                "location": clean(row.get(cols["loc"])) if cols["loc"] else "",
                "national_id": clean(row.get(cols["national_id"])) if cols["national_id"] else "",
                "mobile": clean(row.get(cols["mobile"])) if cols["mobile"] else "",
                "national_address": clean(row.get(cols["national_address"])) if cols["national_address"] else "",
                "order_date": order_date.isoformat() if order_date else "",
                "prescription": clean(row.get(cols["prescription"])) if cols["prescription"] else "",
                "prescription_no": clean(row.get(cols["prescription_no"])) if cols["prescription_no"] else "",
                "order_id": order_id,
                "order_status": order_status,
                "dispense_status": dispense_status,
            }
            rec["rx_end"] = estimate_rx_end(order_date, rec["prescription"])

            demo = demographics.setdefault(pid, {})
            for k in ("name", "national_id", "mobile", "national_address"):
                if rec[k] and not demo.get(k):
                    demo[k] = rec[k]

            # Same order may contain repeated rows. Order ID prevents duplicate counting.
            identity = rec["order_id"] or rec["last"]
            same = (pid, drug.casefold(), identity)
            if same in latest:
                latest[same]["qty"] += qty
            else:
                latest[same] = rec

    med_latest = {}
    stopped_current = 0
    awaiting_dispense = 0
    superseded_dispense = 0
    for rec in latest.values():
        k = (rec["id"], rec["drug"].casefold())
        current = newest_order.get(k, {})
        current_status = clean(current.get("status")).casefold()
        current_dispense = clean(current.get("dispense_status")).casefold()

        # A current Stopped prescription remains in source history but is excluded
        # from Smart Calendar and Drug Demand until a newer Active order is dispensed.
        if current_status in {"stopped", "stop", "inactive", "discontinued", "cancelled", "canceled"}:
            stopped_current += 1
            continue

        # A newer Active order that is not yet dispensed must not inherit scheduling
        # from an older dispensing. It becomes eligible after actual dispensing.
        rec_rank = order_rank(rec.get("order_date", ""), rec.get("last", ""), rec.get("order_id", ""))
        current_rank = current.get("rank")
        if current_rank and current_rank > rec_rank:
            superseded_dispense += 1
            if current_dispense not in {"dispensed", "صرف", "تم الصرف"}:
                awaiting_dispense += 1
            continue

        rank = order_rank(rec.get("order_date", ""), rec.get("last", ""), rec.get("order_id", ""))
        old_rank = (
            order_rank(
                med_latest[k].get("order_date", ""),
                med_latest[k].get("last", ""),
                med_latest[k].get("order_id", "")
            )
            if k in med_latest else None
        )
        if old_rank is None or rank > old_rank:
            med_latest[k] = rec

    by = defaultdict(list)
    for rec in med_latest.values():
        by[rec["id"]].append(rec)

    patients = []; demand = []
    for pid, meds in by.items():
        # Patient cycle is anchored to the newest actual dispensing event.
        dom = max(m["last"] for m in meds)
        p = max(meds, key=lambda x: (x["last"], x.get("order_id", "")))
        demo = demographics.get(pid, {})
        patient = {
            "id": pid,
            "name": demo.get("name") or p["name"],
            "base_last": dom,
            "meds": len(meds),
            "aligned": sum(m["last"] == dom for m in meds),
            "exceptions": sum(m["last"] != dom for m in meds),
            "speciality": p["speciality"],
            "location": p["location"],
            "national_id": demo.get("national_id", "") or p["national_id"],
            "mobile": demo.get("mobile", "") or p["mobile"],
            "national_address": demo.get("national_address", "") or p["national_address"],
            "drug_text": " | ".join(sorted({m["drug"] for m in meds})[:10]),
            "prescription_end": max((m["rx_end"] for m in meds if m["rx_end"]), default=""),
            "latest_order_id": p.get("order_id", ""),
        }
        schedules = {}
        patient_end = patient["prescription_end"]
        for interval in (15, 20, 25, 30):
            due = preparation_date(dom, patient_end, interval)
            schedules[str(interval)] = [due] if due else []
        patient["schedule_dates"] = schedules
        patients.append(patient)
        demand.append({
            "id": pid, "name": patient["name"], "speciality": patient["speciality"], "base_last": dom,
            "prescription_end": patient["prescription_end"],
            "items": [{
                "drug": m["drug"], "nupco_code": m.get("nupco_code", ""), "qty": m["qty"], "last": m["last"],
                "end": m.get("rx_end", ""), "order_id": m.get("order_id", ""),
                "mosool": inventory_lookup.get(m.get("nupco_code", ""), {}).get("mosool") if m.get("nupco_code") in inventory_lookup else None,
                "lc": inventory_lookup.get(m.get("nupco_code", ""), {}).get("lc") if m.get("nupco_code") in inventory_lookup else None
            } for m in meds]
        })

    patients.sort(key=lambda x: (x["base_last"], x["name"], x["id"]))
    for old in DATA.glob("patients-*.json"): old.unlink()
    chunks = []
    for i in range(0, len(patients), 750):
        name = f"patients-{i//750:02d}.json"
        (DATA / name).write_text(json.dumps(patients[i:i+750], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        chunks.append(name)

    demand_dir = DATA / "demand"; demand_dir.mkdir(exist_ok=True)
    for old in demand_dir.glob("demand-*.json"): old.unlink()
    demand_chunks = []
    for i in range(0, len(demand), 700):
        name = f"demand-{i//700:02d}.json"
        (demand_dir / name).write_text(json.dumps(demand[i:i+700], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        demand_chunks.append(f"data/demand/{name}")
    (DATA / "demand-meta.json").write_text(json.dumps({"patients": len(demand), "chunks": demand_chunks}, separators=(",", ":")), encoding="utf-8")

    for interval in (15, 20, 25, 30):
        pre = DATA / "precomputed" / str(interval); pre.mkdir(parents=True, exist_ok=True)
        for old in pre.glob("demand-*.json"): old.unlink()
        cal = defaultdict(lambda: {"patients": set(), "medications": set(), "quantity": 0.0})
        day = defaultdict(lambda: defaultdict(lambda: {"patients": set(), "quantity": 0.0, "patientRows": []}))
        for x in demand:
            eligible = preparation_date(x["base_last"], x.get("prescription_end") or "", interval)
            if not eligible:
                continue
            for item in x["items"]:
                # Do not include a medication whose prescription has already ended before preparation.
                item_end = item.get("end") or ""
                if item_end:
                    try:
                        if date.fromisoformat(eligible) > date.fromisoformat(item_end):
                            continue
                    except Exception:
                        pass
                drug = item["drug"]; nupco_code = item.get("nupco_code", ""); qty = float(item.get("qty") or 0)
                cal[eligible]["patients"].add(x["id"]); cal[eligible]["medications"].add(drug); cal[eligible]["quantity"] += qty
                r = day[eligible][drug]
                r["nupco_code"] = nupco_code
                stock = inventory_lookup.get(nupco_code, {})
                r["mosool"] = stock.get("mosool") if nupco_code in inventory_lookup else None
                r["lc"] = stock.get("lc") if nupco_code in inventory_lookup else None
                r["patients"].add(x["id"]); r["quantity"] += qty
                r["patientRows"].append({"mrn": x["id"], "name": x["name"], "speciality": x["speciality"], "qty": qty})
        (pre / "calendar.json").write_text(json.dumps({k: {"patients": len(v["patients"]), "medications": len(v["medications"]), "quantity": round(v["quantity"], 2)} for k, v in sorted(cal.items())}, separators=(",", ":")), encoding="utf-8")
        didx = {}
        for d, drugs in sorted(day.items()):
            rows = []
            for drug, v in drugs.items():
                n = len(v["patients"])
                rows.append({
                    "drug": drug,
                    "nupco_code": v.get("nupco_code", ""),
                    "patients": n,
                    "qty": round(v["quantity"], 2),
                    "mosool": v.get("mosool"),
                    "lc": v.get("lc"),
                    "avg": round(v["quantity"] / n, 2) if n else 0,
                    "patientRows": v["patientRows"]
                })
            rows.sort(key=lambda r: (-r["qty"], -r["patients"], r["drug"]))
            fn = f"demand-{d}.json"
            (pre / fn).write_text(json.dumps({"date": d, "rows": rows}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            didx[d] = f"data/precomputed/{interval}/{fn}"
        (pre / "demand-index.json").write_text(json.dumps(didx, separators=(",", ":")), encoding="utf-8")

    unmatched_path = DATA / "unmatched-nupco-medications.json"
    unmatched_path.write_text(json.dumps(sorted(unmatched_drugs), ensure_ascii=False, indent=2), encoding="utf-8")

    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_files": [f.name for f in files],
        "raw_records": raw, "valid_records": valid,
        "unique_patients": len(patients),
        "patient_medication_records": len(med_latest),
        "contacts_loaded": len(contacts),
        "nupco_aliases_loaded": len(nupco_lookup),
        "unmatched_nupco_medications": len(unmatched_drugs),
        "current_stopped_medications_excluded": stopped_current,
        "newer_orders_awaiting_dispense_excluded": awaiting_dispense,
        "superseded_dispense_records_excluded": superseded_dispense,
        "inventory_codes_loaded": len(inventory_lookup),
        "inventory_last_update": inventory_updated,
        "inventory_source": INVENTORY_DATA_URL,
        "inventory_error": inventory_error,
        "chunks": chunks, "default_interval": 20,
        "recurring_until_prescription_end": False,
        "single_preparation_from_latest_dispense": True,
        "dispense_cutoff": cutoff.isoformat(),
    }
    (DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(meta, indent=2))

if __name__=="__main__": main()
