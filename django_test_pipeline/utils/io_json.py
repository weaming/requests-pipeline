import os
import json
from datetime import datetime, date


def json_serializer(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "to_json"):
        return obj.to_json()
    # all to string
    return str(obj)
    # raise TypeError("Type %s not serializable" % type(obj))


def json_dumps(data, *args, **kwargs):
    return json.dumps(data, *args, default=json_serializer, **kwargs)


def green_dict(d):  # type: (dict) -> dict
    return json.loads(json_dumps(d))


def read_json(fp):
    if not os.path.exists(fp):
        return None

    with open(fp) as f:
        return json.loads(f.read())


def save_json(data, out_path, **kwargs):
    with open(out_path, "w") as f:
        return f.write(json_dumps(data, **kwargs))
