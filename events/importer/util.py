
def partial_copy(d, leave_out):
    """Copies a dict, leaving out specified keys."""
    return { k: d[k] for k in d.iterkeys() if k not in leave_out }

def partial_equals(da, db, leave_out):
    """Checks if dicts are equal, ignoring specified keys."""
    for key in da.viewkeys() | db.viewkeys():
        if key in leave_out:
            continue
        if da[key] != db[key]:
            return False
    return True
