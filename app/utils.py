# app/utils.py
import ast
from pathlib import Path

def save_screenshot_blob(blob, out_path: Path):
    """
    Save `blob` into out_path (Path). `blob` may be:
     - bytes
     - a Python bytes literal string like "b'....'"
     - a base64 string (if you choose to handle that later)
    Returns the str(path).
    """
    if isinstance(blob, bytes):
        b = blob
    elif isinstance(blob, str):
        blob_str = blob
        if blob_str.startswith("b'") or blob_str.startswith('b"'):
            try:
                b = ast.literal_eval(blob_str)
            except Exception:
                b = blob_str.encode("latin-1", errors="ignore")
        else:
            import base64
            try:
                b = base64.b64decode(blob_str)
            except Exception:
                b = blob_str.encode("utf-8", errors="ignore")
    else:
        raise TypeError("Unsupported blob type for screenshot")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(b)
    return str(out_path)
