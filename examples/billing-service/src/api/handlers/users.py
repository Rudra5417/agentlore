"""User HTTP handlers."""
import json


def get_user(uid):
    return json.dumps({"id": uid})


def list_users():
    return json.dumps([])
