"""Check known race conditions without editing the installed simulator."""

import hashlib
import os
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
if "TORCS_HOME" not in os.environ:
    raise SystemExit("Set TORCS_HOME to the directory containing wtorcs.exe")
TORCS_HOME = Path(os.environ["TORCS_HOME"]).expanduser().resolve()

EXPECTED = {
    HERE / "controller_v3_4.py": "71f264d1839203d9d77246a9fdef20ab8a613702bb82414dc0df2a389b9edc4f",
    HERE / "snakeoil3_gym.py": "6fe87efcd6c772152f8910476c4bfe9ce682f8b71adaf640072e292c0075bdcc",
    HERE / "fastest-clean.json": "4ffe7a45c6a4b4e5c7bd71986bcb908226486603b24fd60f5df072a878a83fb8",
    TORCS_HOME / "cars/car1-ow1/car1-ow1.xml": "33b3057e306793fbd395a734c54ea7c649bc9f26d2f15ce0c2e8efceb889fae3",
    TORCS_HOME / "tracks/road/corkscrew/corkscrew.xml": "2fdbf78f6151093c2450d03edcedc88436877cdd86112795cec6b1d9a5057ea9",
}
for path, digest in EXPECTED.items():
    if not path.is_file():
        raise SystemExit(f"Missing required file: {path}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise SystemExit(f"File differs from the recorded race: {path}")

race_path = TORCS_HOME / "config/raceman/quickrace.xml"
if not race_path.is_file():
    raise SystemExit(f"Missing Quick Race configuration: {race_path}")
race = ET.parse(race_path)


def value(xpath):
    node = race.find(xpath)
    if node is None:
        raise SystemExit(f"Missing race setting: {xpath}")
    return node.get("val")


if value('./section[@name="Tracks"]/section[@name="1"]/attstr[@name="name"]') != "corkscrew":
    raise SystemExit("Select Corkscrew")
if float(value('./section[@name="Quick Race"]/attnum[@name="laps"]')) != 1:
    raise SystemExit("Select one lap")
if float(value('./section[@name="Quick Race"]/section[@name="Starting Grid"]/attnum[@name="initial speed"]')) != 0:
    raise SystemExit("Select a standing start")
drivers = race.findall('./section[@name="Drivers"]/section')
if len(drivers) != 1:
    raise SystemExit("Select only scr_server 1")
driver = {item.get("name"): item.get("val") for item in drivers[0]}
if driver.get("module") != "scr_server" or driver.get("idx") != "0":
    raise SystemExit("Select scr_server 1")

print("Verified recorded track and car files, Corkscrew, one lap, standing start, and scr_server 1.")
print("This check does not prove competition eligibility or reproduce the 67.064-second lap.")
