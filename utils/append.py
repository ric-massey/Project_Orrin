import os
import json
from utils.log import log_error

def append_to_json(file_path, new_entry):
    """
    Appends a dictionary entry to a JSON file (which contains a list).
    If the file doesn't exist or is empty, it will be created with the entry as the first item.
    """
    # Ensure the directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    data = []
    if os.path.exists(file_path):
        try:
            # Only try to load if the file is not empty
            if os.stat(file_path).st_size > 0:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    raise ValueError(f"{file_path} does not contain a list.")
        except Exception as e:
            log_error(f"Error loading {file_path}: {e}")
            data = []
    # else: data stays as []

    # Append the new entry and save
    data.append(new_entry)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)