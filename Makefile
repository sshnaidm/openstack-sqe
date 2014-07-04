.DEFAULT_GOAL := init
VENV=.env
PYTHON=$(VENV)/bin/python
CYAN=$(shell echo `tput bold``tput setaf 6`)
RED=$(shell echo `tput bold``tput setaf 1`)
RESET=$(shell echo `tput sgr0`)
#WORKSPACE=$(shell echo ${WORKSPACE})
ifndef LAB
	LAB="lab1"
endif
ifndef WORKSPACE
	WORKSPACE=$$(pwd)"/.."
endif


clean:
	@echo "$(CYAN)>>> Cleaning...$(RESET)"
	deactivate || :
	rm -rf $(VENV) .coverage || :
	find . -name '*.pyc' | xargs rm || :
	find . -name '*~' | xargs rm || :

venv:
	@echo "$(CYAN)>>>> Creating virtualenv for LAB=${LAB}...$(RESET)"
	test $(VENV)/requirements_packages_installed -nt requirements_packages || sudo apt-get install -y `cat requirements_packages` || :
	test -d $(VENV) || virtualenv --setuptools $(VENV)

requirements: venv
	@echo "$(CYAN)>>>> Installing dependencies...$(RESET)"
	test $(VENV)/requirements_installed -nt requirements || (. $(VENV)/bin/activate; pip install -Ur requirements && echo > $(VENV)/requirements_installed) || :

init: venv requirements

aio: init prepare-aio give-a-time install-aio

flake8: init
	@echo "$(CYAN)>>>> Running static analysis...$(RESET)"
	@. $(VENV)/bin/activate; flake8 --max-line-length=120 --show-source --exclude=.env . | \
	awk '{ print } END { if (NR) exit 1}'

flake8-mild:
	@echo "$(CYAN)>>>> Running static analysis...$(RESET)"
	@. $(VENV)/bin/activate; flake8 --max-line-length=120 --show-source --exclude=.env . || echo

help:
	@echo "List of available targets:"
	@make -qp | awk -F ':' '/^[a-zA-Z0-9][^$$#\/\t=]*:([^=]|$$)/ {split($$1,A,/ /); for(i in A) printf " %s\n", A[i]}'| grep -v Makefile | sort

prepare-aio:
	@echo "$(CYAN)>>>> Preparing AIO box...$(RESET)"
	test -e trusty-server-cloudimg-amd64-disk1.img || wget -nv http://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img
	time $(PYTHON) ./tools/libvirt-scripts/create.py -u root -a localhost -b cloudimg -l ${LAB} -d /opt/imgs -z ./trusty-server-cloudimg-amd64-disk1.img -o > config_file

prepare-aio-local:
	@echo "$(CYAN)>>>> Preparing AIO box...$(RESET)"
	time ./tools/libvirt-scripts/create.py -u root -a localhost -b cloudimg -l lab1 -d /media/hdd/tmpdir/tmp/imgs -z /media/hdd/tmpdir/trusty-server-cloudimg-amd64-disk1.img -o > config_file

prepare-2role:
	@echo "$(CYAN)>>>> Preparing 2_role boxes...$(RESET)"
	test -e trusty-server-cloudimg-amd64-disk1.img || wget -nv http://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img
	time $(PYTHON) ./tools/libvirt-scripts/create.py -u root -a localhost -b cloudimg -l ${LAB} -d /opt/imgs -z ./trusty-server-cloudimg-amd64-disk1.img > config_file

prepare-2role-cobbler:
	@echo "$(CYAN)>>>> Preparing 2_role boxes for cobbler...$(RESET)"
	test -e trusty-server-cloudimg-amd64-disk1.img || wget -nv http://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img
	time $(PYTHON) ./tools/libvirt-scripts/create.py -u root -a localhost -b net -l ${LAB} -d /opt/imgs -z ./trusty-server-cloudimg-amd64-disk1.img > config_file

prepare-fullha:
	@echo "$(CYAN)>>>> Preparing full HA boxes...$(RESET)"
	test -e trusty-server-cloudimg-amd64-disk1.img || wget -nv http://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img
	time $(PYTHON) ./tools/libvirt-scripts/create.py -u root -a localhost -s -b cloudimg -l ${LAB} -d /opt/imgs -z ./trusty-server-cloudimg-amd64-disk1.img > config_file

prepare-fullha-cobbler:
	@echo "$(CYAN)>>>> Preparing full HA boxes for cobbler...$(RESET)"
	test -e trusty-server-cloudimg-amd64-disk1.img || wget -nv http://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img
	time $(PYTHON) ./tools/libvirt-scripts/create.py -u root -a localhost -s -b net -l ${LAB} -d /opt/imgs -z ./trusty-server-cloudimg-amd64-disk1.img > config_file


give-a-time:
	sleep 180

install-aio:
	@echo "$(CYAN)>>>> Installing AIO...$(RESET)"
	time $(PYTHON) ./tools/deployers/install_aio_coi.py -c config_file

install-2role:
	@echo "$(CYAN)>>>> Installing 2_role multinode...$(RESET)"
	time $(PYTHON) ./tools/deployers/install_aio_2role.py -c config_file

install-2role-cobbler:
	@echo "$(CYAN)>>>> Installing 2_role multinode with cobbler...$(RESET)"
	time $(PYTHON) ./tools/deployers/install_aio_2role.py -e -c config_file

install-fullha:
	@echo "$(CYAN)>>>> Installing full HA setup...$(RESET)"
	time $(PYTHON) ./tools/deployers/install_fullha.py -c config_file

install-fullha-cobbler:
	@echo "$(CYAN)>>>> Installing full HA setup with cobbler...$(RESET)"
	time $(PYTHON) ./tools/deployers/install_fullha.py -e -c config_file

install-devstack:
	@echo "$(CYAN)>>>> Installing Devstack...$(RESET)"
	time $(PYTHON) ./tools/deployers/install_devstack.py -c config_file  -u localadmin -p ubuntu

prepare-tempest:
	@echo "$(CYAN)>>>> Preparing tempest...$(RESET)"
	time $(PYTHON) ./tools/tempest-scripts/tempest_align.py -c config_file -u localadmin -p ubuntu
	time python ${WORKSPACE}/tempest/tools/install_venv.py
	${WORKSPACE}/tempest/.venv/bin/pip install junitxml python-ceilometerclient nose testresources testtools
	. ${WORKSPACE}/tempest/.venv/bin/activate
	./tools/tempest-scripts/tempest_unconfig.sh
	./tools/tempest-scripts/tempest_configurator.sh $$(grep OS_AUTH_URL ./openrc | grep -Eo "/.*:" | sed "s@/@@g"  | sed "s@:@@g")
	mv ./tempest.conf.jenkins ${WORKSPACE}/tempest/etc/tempest.conf

run-tests:
	@echo "$(CYAN)>>>> Run tempest tests ...$(RESET)"
	time /bin/bash ./tools/tempest-scripts/run_tempest_tests.sh

run-tests-parallel:
	@echo "$(CYAN)>>>> Run tempest tests in parallel ...$(RESET)"
	sed -i 's/testr run/testr run --parallel /g' ./tools/tempest-scripts/run_tempest_tests.sh
	time /bin/bash ./tools/tempest-scripts/run_tempest_tests.sh

init: venv requirements

aio: init prepare-aio give-a-time install-aio

2role: init prepare-2role give-a-time install-2role

2role-cobbler: init prepare-2role-cobbler give-a-time install-2role-cobbler

fullha: init prepare-fullha give-a-time install-fullha

fullha-cobbler: init prepare-fullha-cobbler give-a-time install-fullha-cobbler

devstack: init prepare-aio give-a-time install-devstack

run-tempest: prepare-tempest run-tests

run-tempest-parallel: prepare-tempest run-tests-parallel

full-aio: aio run-tempest

full-aio-quick: aio run-tempest-parallel

full-2role: 2role run-tempest

full-2role-quick: 2role run-tempest-parallel

full-fullha: fullha run-tempest

test-me:
	@echo "$(CYAN)>>>> test your commands :) ...$(RESET)"
	echo ${LAB}
	echo ${WORKSPACE}
	ls ${WORKSPACE}
