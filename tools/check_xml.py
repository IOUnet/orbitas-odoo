from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
errors = []
for path in sorted((ROOT / "orbitas_connector").rglob("*.xml")):
    try:
        ET.parse(path)
    except ET.ParseError as exc:
        errors.append(f"{path.relative_to(ROOT)}: {exc}")

if errors:
    print("\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
print("XML syntax OK")
