import os
from fabric.api import env, prefix
from contextlib import contextmanager

import logging
import functools
import time
from . import TEMPEST_DIR
import subprocess

env.host_string = "localhost"

VENV=".env"
CUR_DIR = os.path.dirname(__file__)
# Local virtualenv, that is removed every build
LVENV = os.path.normpath(os.path.join(CUR_DIR, "..", VENV))
# Common virtualenv in HOME, that is persistent
CVENV = os.path.join(os.path.expanduser("~"), VENV)

TVENV = ".venv"
# Local virtualenv, that is removed every build
TLVENV = os.path.normpath(os.path.join(TEMPEST_DIR, VENV))
# Common virtualenv for tempest in HOME
TCVENV = os.path.join(os.path.expanduser("~"), VENV)


logger = logging.getLogger('ROBOT')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('robot.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
# add the handlers to logger
logger.addHandler(ch)
logger.addHandler(fh)

def timed(func):
    @functools.wraps(func)
    def newfunc(*args, **kwargs):
        startTime = time.time()
        func(*args, **kwargs)
        elapsedTime = time.time() - startTime
        logger.info('TIMED: Function [{}] finished in {} sec'.format(
            func.__name__, int(elapsedTime)))
    return newfunc

def _get_virtenv():
    if os.path.exists(LVENV):
        return LVENV
    return CVENV

CUR_VENV = _get_virtenv()

def _get_tempest_virtenv():
    if os.path.exists(TLVENV):
        return TLVENV
    return TCVENV

TEMPEST_VENV = _get_tempest_virtenv()

@contextmanager
def virtualenv(path):
    activate = os.path.normpath(os.path.join(path, "bin", "activate"))
    if not os.path.exists(activate):
        raise OSError("Cannot activate virtualenv %s" % path)
    with prefix('. %s' % activate):
        yield

def virtual(func, envpath=None):
    @functools.wraps(func)
    def newfunc(*args, **kwargs):
        if envpath == "tempest":
            venv = _get_tempest_virtenv()
        else:
            venv = _get_virtenv()
        with virtualenv(venv):
            logger.info("Executing in virtualenv: {venv}".format(venv=venv))
            func(*args, **kwargs)
    return newfunc

def intempest(func):
    return virtual(func, envpath="tempest")

def run_cmd(cmd):
    logging.info("Running command: %s" % " ".join(cmd))
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            close_fds=True)
    ret = proc.wait()
    return ret, proc.stdout.read(), proc.stderr.read()
