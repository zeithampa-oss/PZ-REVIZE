from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAS = ROOT / "source" / "windows" / "pzrevize" / "nas_sync.py"

text = NAS.read_text(encoding="utf-8")

old = 'def pull_from_nas(db, base_url: str, token: str, client_name: str = "PZ-REVIZE PC", can_pull=None) -> dict:'
new = 'def pull_from_nas(db, base_url: str, token: str, client_name: str = "PZ-REVIZE PC", can_pull=None, allow_unchanged_local: bool = False) -> dict:'
if old not in text:
    raise SystemExit("pull_from_nas signature not found")
text = text.replace(old, new, 1)

old = 'if relation["relation"] not in ("remote_superset", "equal") and not initial_pull:'
new = 'if relation["relation"] not in ("remote_superset", "equal") and not initial_pull and not allow_unchanged_local:'
if old not in text:
    raise SystemExit("pull guard not found")
text = text.replace(old, new, 1)

old = 'result = pull_from_nas(db, base_url, token, can_pull=can_pull)'
new = 'result = pull_from_nas(db, base_url, token, can_pull=can_pull, allow_unchanged_local=True)'
marker = 'if server_generation > local_generation and last_signature and local_signature == last_signature:'
idx = text.find(marker)
if idx < 0:
    raise SystemExit("sequential pull block not found")
pos = text.find(old, idx)
if pos < 0:
    raise SystemExit("sequential pull call not found")
text = text[:pos] + text[pos:].replace(old, new, 1)
NAS.write_text(text, encoding="utf-8")
print("Applied trusted sequential NAS pull fix")
