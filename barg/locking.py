"""One Linux sandbox lease, held across all trials including vanilla baselines."""
import os
from pathlib import Path


def acquire(state, inherited_fd=None):
    import fcntl
    path = Path(state)/'agent.lock'
    if inherited_fd is None:
        handle = path.open('a+')
    else:
        expected, actual = path.stat(), os.fstat(inherited_fd)
        if (expected.st_dev, expected.st_ino) != (actual.st_dev, actual.st_ino):
            raise ValueError('Inherited sandbox lease does not match the lock file')
        handle = os.fdopen(os.dup(inherited_fd), 'a+')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError('Another BARG agent or experiment holds this sandbox lock') from None
    return handle
