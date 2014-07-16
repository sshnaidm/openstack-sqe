#!/bin/bash
source $WORKSPACE/tempest/.venv/bin/activate
source $WORKSPACE/openstack-sqe/openrc
tests="$WORKSPACE/openstack-sqe/tools/tempest-scripts/tests_set"
cd $WORKSPACE/tempest/
testr init || :
if [ -s "$tests" ]; then
    testr run --load-list "$tests" --subunit  | subunit-2to1 | tools/colorizer.py || :
else
    testr run "$REG" --subunit | subunit-2to1 | tools/colorizer.py || :
fi

testr last --subunit | subunit-1to2 | subunit2junitxml --output-to="${WORKSPACE}/nosetests.xml" || :
export REG=$(testr failing --list | grep -Eo "tempest[\._A-z]+" | sed "s/\(.*\)\..*\(JSON\)*\(XML\)*/\1/g" | sort -u | xargs echo | sed 's/ /.*\|/g' | sed "s/\(.*$\)/(\1)/g")
