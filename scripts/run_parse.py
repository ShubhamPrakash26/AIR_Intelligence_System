from pathlib import Path
import json
import sys

try:
    from src.ingestion.excel_parser import ExcelParser
except Exception as e:
    print("Failed to import ExcelParser:", e)
    raise

p = Path('data/input/Log.xlsx')
if not p.exists():
    print(f"Sample file not found: {p}")
    sys.exit(2)

parser = ExcelParser()
try:
    incidents = parser.parse_file(p)
    out = []
    for i in incidents:
        # Pydantic v2: model_dump
        try:
            out.append(i.model_dump())
        except Exception:
            try:
                out.append(i.dict())
            except Exception:
                out.append(str(i))
    print(json.dumps(out, indent=2))
except Exception as e:
    print('Error parsing file:', e)
    raise
