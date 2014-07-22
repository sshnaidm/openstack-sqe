import time
import sys
import yaml

from StringIO import StringIO
from utils import warn_if_fail, collect_logs, resolve_names, update_time, all_servers
from fabric.api import sudo, settings, run, hide, put, shell_env, cd, get
from fabric.contrib.files import exists, contains, append, sed
from fabric.colors import green, red

from config import APPLY_LIMIT, DOMAIN_NAME
#from role2 import Role2Deploy
#from fullha import FullHADeploy


__author__ = 'sshnaidm'


def install_openstack(settings_dict,
                      envs=None,
                      verbose=None,
                      force=False,
                      config=None,
                      use_cobbler=False,
                      proxy=None,
                      scenario=None,
                      cls=None):
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
                    #map = {
                    #    "2role": Role2Deploy,
                    #    "fullha": FullHADeploy,
                    #    "devstack": DevstackDeploy,
                    #}
                    cls.prepare_all_files(cls(), config, use_sudo_flag)

                check_results(run_func, use_cobbler)
                if exists('/root/openrc'):
                    get('/root/openrc', "./openrc")
                else:
                    print (red("No openrc file, something went wrong! :("))
                print (green("Copying logs and configs"))
                if scenario != "all_in_one":
                    collect_logs(run_func=run_func,
                                 hostname=config["servers"]["build-server"][0]["hostname"],
                                 clean=True)
                else:
                    collect_logs(run_func=run_func,
                                 hostname=config["servers"]["aio-server"][0]["hostname"],
                                 clean=True)
                print (green("Finished!"))
            else:
                return True
    print (green("Finished!"))
    return True



def run_services(host,
                 settings_dict,
                 envs=None,
                 verbose=None,
                 config=None,
                 scenario=None):
    """
        Install OS with COI on other servers

    :param host: configuration of current lab box
    :param settings_dict: settings dictionary for Fabric
    :param envs: environment variables to inject when executing job
    :param verbose: if to hide all output or print everything
    :param config: configurations of all boxes for /etc/hosts
    """
    envs = envs or {}
    verbose = verbose or []
    if settings_dict['user'] != 'root':
        run_func = sudo
        use_sudo_flag = True
    else:
        run_func = run
        use_sudo_flag = False
    print >> sys.stderr, "FABRIC connecting to", settings_dict["host_string"], host["hostname"]
    with settings(**settings_dict), hide(*verbose), shell_env(**envs):
        with cd("/root/"):
            update_time(run_func)
            run_func("apt-get update")
            run_func('DEBIAN_FRONTEND=noninteractive apt-get -y '
                     '-o Dpkg::Options::="--force-confdef" -o '
                     'Dpkg::Options::="--force-confold" dist-upgrade')
            # prepare /etc/hosts
            if config:
                append("/etc/hosts", prepare_hosts(config, scenario))
            run_func("apt-get install -y git")
            run_func("git clone -b icehouse https://github.com/CiscoSystems/puppet_openstack_builder")
            # use latest, not i.0 release
            #with cd("/root/puppet_openstack_builder"):
            #        run_func('git checkout i.0')
            #sed("/root/puppet_openstack_builder/install-scripts/cisco.install.sh",
            #                "icehouse/snapshots/i.0",
            #                "icehouse-proposed", use_sudo=use_sudo_flag)
            prepare_repo(run_func, use_sudo_flag)
            with cd("/root/puppet_openstack_builder/install-scripts"):
                warn_if_fail(run_func("./setup.sh"))
                warn_if_fail(run_func('puppet agent --enable'))
                warn_if_fail(run_func("puppet agent -td --server=build-server.domain.name --pluginsync"))
                collect_logs(run_func=run_func, hostname=host["hostname"])


def check_results(run_func, use_cobbler):
    result = run_func('puppet apply -v /etc/puppet/manifests/site.pp')
    tries = 1
    if use_cobbler:
        cobbler_error = "[cobbler-sync]/returns: unable to connect to cobbler on localhost using cobbler"
        while cobbler_error in result and tries <= APPLY_LIMIT:
            time.sleep(60)
            print >> sys.stderr, "Cobbler is not installed properly, running apply again"
            result = run_func('puppet apply -v /etc/puppet/manifests/site.pp', pty=False)
            tries += 1
    error = "Error:"
    while error in result and tries <= APPLY_LIMIT:
        time.sleep(60)
        print >> sys.stderr, "Some errors found, running apply again"
        result = run_func('puppet apply -v /etc/puppet/manifests/site.pp', pty=False)
        tries += 1


def prepare_repo(run_func, sudo_flag):
    ## run the latest, not i.0 release
    #run_func('git checkout i.0')
    sed("/root/puppet_openstack_builder/install-scripts/cisco.install.sh",
        "icehouse/snapshots/i.0",
        "icehouse-proposed", use_sudo=sudo_flag)




def prepare_hosts(config, scenario):
    """ Prepare /etc/hosts file """
    hosts = '\n'
    if scenario == "fullha":
        net_ip = ".".join(config["servers"]["control-server"][0]["ip"].split(".")[:3])
        hosts += "{ip}    control.{domain}    control\n".format(ip=net_ip + ".253", domain=DOMAIN_NAME)
        hosts += "{ip}    swiftproxy.{domain}    swiftproxy\n".format(ip=net_ip + ".252", domain=DOMAIN_NAME)
    for s in all_servers(config):
        hosts += "{ip}    {hostname}.{domain}    {hostname}\n".format(
            ip=s["ip"],
            hostname=s["hostname"],
            domain=DOMAIN_NAME
        )
    return hosts




def track_cobbler(config, setts, hosts):

    """
        Function for tracking cobbler installation on boxes

    :param config: boxes configuration
    :param setts: settings for connecting to boxes
    :return: Nothing, but exist with 1 when failed
    """

    def ping(h, s):
        with settings(**s), hide('output', 'running', 'warnings'):
            res = run("ping -W 5 -c 3 %s" % h)
            return res.succeeded

    def catalog_finished(h, s):
        s["host_string"] = h
        s["user"] = "localadmin"
        s["password"] = "ubuntu"
        with settings(**s), hide('output', 'running', 'warnings'):
            try:
                return contains("/var/log/syslog", "Finished catalog run")
            except Exception as e:
                return False

    wait_os_up = 15*60
    wait_catalog = 40*60

    # reset machines
    try:
        import libvirt
        conn = libvirt.open('qemu+ssh://{user}@localhost/system'.format(user=setts["user"]))
        for servbox in hosts:
            vm_name = servbox["vm_name"]
            vm = conn.lookupByName(vm_name)
            vm.destroy()
            vm.create()
            print >> sys.stderr, "Domain {name} is restarted...".format(name=vm_name)
        conn.close()
    except Exception as e:
        print >> sys.stderr, "Exception", e

    for check_func, timeout in (
            (ping, wait_os_up),
            (catalog_finished, wait_catalog)):

        host_ips = [i["ip"] for i in hosts]
        start = time.time()
        while time.time() - start < timeout:
            for host in host_ips:
                if check_func(host, setts.copy()):
                    host_ips.remove(host)
            if not host_ips:
                print >> sys.stderr, "Current step with '%s' was finished successfully!" % check_func.func_name
                break
            time.sleep(3*60)
        else:
            print >> sys.stderr, "TImeout of %d minutes of %s is over. Exiting...." % (timeout/60, check_func.func_name)
            sys.exit(1)



