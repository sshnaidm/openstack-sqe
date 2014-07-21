#!/usr/bin/env python
from aio import AIO
from devstack import Devstack, DevstackDeploy
from role2 import Role2, Role2Deploy
from fullha import FullHA, FullHADeploy
from config import opts, ssh_key_file, verb_mode
from StringIO import StringIO
from fabric.colors import green, red

from common import prepare_repo, prepare_hosts, check_results

__author__ = 'sshnaidm'


from utils import warn_if_fail, collect_logs, resolve_names, update_time, all_servers
from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get
from fabric.contrib.files import exists, contains, append, sed


def install_openstack(settings_dict,
                      envs=None,
                      verbose=None,
                      force=False,
                      config=None,
                      use_cobbler=False,
                      proxy=None,
                      scenario=None):
    """
        Install OS with COI on build server

    :param settings_dict: settings dictionary for Fabric
    :param envs: environment variables to inject when executing job
    :param verbose: if to hide all output or print everything
    :param url_script: URl of Cisco installer script from Chris
    :param force: Use if you don't connect via interface you gonna bridge later
    :return: always true
    """
    envs = envs or {}
    verbose = verbose or []
    if settings_dict['user'] != 'root':
        use_sudo_flag = True
        run_func = sudo
    else:
        use_sudo_flag = False
        run_func = run

    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        with cd("/root/"):
            if proxy:
                warn_if_fail(put(StringIO('Acquire::http::proxy "http://proxy.esl.cisco.com:8080/";'),
                                 "/etc/apt/apt.conf.d/00proxy",
                                 use_sudo=use_sudo_flag))
                warn_if_fail(put(StringIO('Acquire::http::Pipeline-Depth "0";'),
                                 "/etc/apt/apt.conf.d/00no_pipelining",
                                 use_sudo=use_sudo_flag))
            run_func("apt-get update")
            run_func("apt-get install -y git")
            run_func("git config --global user.email 'test.node@example.com';"
                     "git config --global user.name 'Test Node'")
            if not force:
                update_time(run_func)
                # avoid grub and other prompts
                warn_if_fail(run_func('DEBIAN_FRONTEND=noninteractive apt-get -y '
                                      '-o Dpkg::Options::="--force-confdef" -o '
                                      'Dpkg::Options::="--force-confold" dist-upgrade'))
                # prepare /etc/hosts file
                append("/etc/hosts", prepare_hosts(config, scenario))
                with cd("/root"):
                    warn_if_fail(run_func("git clone -b icehouse "
                                          "https://github.com/CiscoSystems/puppet_openstack_builder"))
                    with cd("puppet_openstack_builder"):
                        prepare_repo(run_func, use_sudo_flag)
                        with cd("install-scripts"):
                            warn_if_fail(run_func("./install.sh"))
                resolve_names(run_func, use_sudo_flag)
                if scenario != "all_in_one":
                    prepare_hosts(config, scenario)
                    map = {
                        "2role": Role2Deploy,
                        "fullha": FullHADeploy,
                        "devstack": DevstackDeploy,
                    }
                    map[scenario].prepare_all_files(config, use_sudo_flag)

                check_results(run_func, use_cobbler)
                if exists('/root/openrc'):
                    get('/root/openrc', "./openrc")
                else:
                    print (red("No openrc file, something went wrong! :("))
                print (green("Copying logs and configs"))
                collect_logs(run_func=run_func, hostname=config["servers"]["build-server"][0]["hostname"], clean=True)
                print (green("Finished!"))
            else:
                return True
    print (green("Finished!"))
    return True



def main():

    params = opts, ssh_key_file, verb_mode
    mapa = {
        "all-in-one": AIO,
        "devstack": Devstack,
        "2role": Role2,
        "fullha": FullHA,

    }
    deployer = mapa[opts.scenario](*params)
    deployer.run()

if __name__ == "__main__":
    main()
