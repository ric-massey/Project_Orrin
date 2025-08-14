import os
import json
import tempfile
from utils.log import log_error

def append_to_json(file_path: str, new_entry):
    """
    Appends a dictionary entry (or any JSON-serializable object) to a JSON file (which contains a list).
    If the file doesn't exist or is empty, it will be created with the entry as the first item.
    Uses atomic write to avoid corruption.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    data = []
    if os.path.exists(file_path) and os.stat(file_path).st_size > 0:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError(f"{file_path} does not contain a list.")
        except Exception as e:
            log_error(f"Error loading {file_path}: {e}")
            data = []

    # Append
    data.append(new_entry)

    # Write atomically
    try:
        dir_name = os.path.dirname(file_path)
        fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            json.dump(data, tmp_file, indent=2, ensure_ascii=False)
        os.replace(temp_path, file_path)  # atomic move
    except Exception as e:
        log_error(f"Error saving to {file_path} with entry {new_entry!r}: {e}")