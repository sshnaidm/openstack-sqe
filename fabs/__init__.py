import os

WEB = "http://172.29.173.233/"
UBUNTU_URL_CLOUD = "http://cloud-images.ubuntu.com/trusty/current/"
UBUNTU_DISK = "trusty-server-cloudimg-amd64-disk1.img"
CENTOS65_DISK = "centos-6.5.x86_64.qcow2"
CENTOS7_DISK = "centos-7.x86_64.qcow2"
FEDORA20_DISK = "fedora-20.x86_64.qcow2"

GLOBAL_TIMEOUT=180

def _get_lab():
    if "LAB" not in os.environ:
        return "lab1"
    else:
        return os.environ["LAB"]

def _get_waittime():
    if "QA_WAITTIME" not in os.environ:
        return "18000"
    else:
        return os.environ["QA_WAITTIME"]

def _get_killtime():
    if "QA_KILLTIME" not in os.environ:
        return "18060"
    else:
        return os.environ["QA_KILLTIME"]

def _get_workspace():
    if "WORKSPACE" not in os.environ:
        return os.path.normpath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                ".."))
    else:
        return os.environ["WORKSPACE"]

def _get_tempest_dir():
    return os.path.join(
        _get_workspace(),
        "tempest")

def _get_tempest_venv_path():
    return os.path.join(
        _get_tempest_dir(), ".venv")


LAB =_get_lab()
QA_WAITTIME =_get_waittime()
QA_KILLTIME =_get_killtime()
WORKSPACE =_get_workspace
TEMPEST_DIR = _get_tempest_dir()
TEMPEST_VENV =_get_tempest_venv_path()
