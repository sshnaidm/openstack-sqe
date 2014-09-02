#!/bin/bash
if [ -n "$LAB" ]; then
    labid=$LAB
else
    echo "No \$LAB variable id defined"
    exit 1
fi
if [ -n "$WORKSPACE" ]; then
    this_=$(readlink -f $0)
    this_dir=$(dirname $this_)
    WORKSPACE="${this_dir}/../../.."
fi
tests="$WORKSPACE/openstack-sqe/tools/tempest-scripts/tests_set"
export DEV_IP=$(sed -n "/${labid}:/{n;p;n;p;}" tools/cloud/cloud-templates/lab.yaml | sed 'N;s/\n/ /' | sed "s/    ip_start: /./g" | sed "s/   net_start: //g")
source $WORKSPACE/openstack-sqe/.env/bin/activate
if [ -s "$tests" ]; then
    $WORKSPACE/openstack-sqe/.env/bin/python \
    $WORKSPACE/openstack-sqe/tools/tempest-scripts/run_tempest.py -r $DEV_IP -l "$tests" ||:
elif [ -n "$REG" ]; then
    $WORKSPACE/openstack-sqe/.env/bin/python \
    $WORKSPACE/openstack-sqe/tools/tempest-scripts/run_tempest.py -r $DEV_IP -f "$REG" ||:
else
    $WORKSPACE/openstack-sqe/.env/bin/python \
    $WORKSPACE/openstack-sqe/tools/tempest-scripts/run_tempest.py -r $DEV_IP ||:
fi