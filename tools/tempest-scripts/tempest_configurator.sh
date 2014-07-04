#!/bin/bash
source ./openrc

# external_net is file, containing IP of externl subnet, i.e.: 192.168.33 or 10.123.29, first 3 numbers

if [ -e ./external_net ]; then
    EXTERNAL_NET=$(cat ./external_net)
else
    EXTERNAL_NET="10.10.10"
fi

echo "Reinitialize the dir"
rm -rf prepare_for_tempest_dir
mkdir -p prepare_for_tempest_dir
cd prepare_for_tempest_dir/
echo "downloading cirros-0.3.2-x86_64-disk.img ...."
wget -nv http://172.29.173.233/cirros-0.3.2-x86_64-disk.img
#wget -nv http://download.cirros-cloud.net/0.3.1/cirros-0.3.1-x86_64-disk.img
glance image-create --name=cirros-0.3-x86_64 --is-public=true --container-format=bare --disk-format=qcow2 < ./cirros-0.3.2-x86_64-disk.img
#wget http://uec-images.ubuntu.com/trusty/current/trusty-server-cloudimg-amd64-disk1.img
#glance image-create --name=trusty-server --is-public=true --container-format=bare --disk-format=qcow2 < ./trusty-server-cloudimg-amd64-disk1.img
echo "downloading precise-server-cloudimg-amd64-disk1.img ...."
#wget -nv http://uec-images.ubuntu.com/server/precise/current/precise-server-cloudimg-amd64-disk1.img
#wget -nv http://172.29.173.233/precise-server-cloudimg-amd64-disk1.img
glance image-create --name=precise-server  --is-public=true --container-format=bare --disk-format=qcow2 < ./cirros-0.3.2-x86_64-disk.img
keystone tenant-create --name demo
kid1=$(keystone tenant-list | grep " demo " | awk {'print $2'})
keystone user-create --name=demo --pass=secret --tenant-id=$kid1 --email=demo@domain1.com
keystone tenant-create --name alt_demo
kid2=$(keystone tenant-list | grep " alt_demo " | awk {'print $2'})
keystone user-create --name=alt_demo --pass=secret --tenant-id=$kid2  --email=alt_demo@domain1.com
keystone tenant-create --name openstack
kid3=$(keystone tenant-list | grep " openstack " | awk {'print $2'})
keystone user-create --name=admin --pass=Cisco123 --tenant-id=$kid3 --email=admin@domain1.com
uid1=$(keystone user-list | grep " admin " | awk {'print $2'})
rid1=$(keystone role-list | grep " admin " |  awk {'print $2'})
keystone user-role-add --tenant-id=$kid3 --user-id=$uid1 --role-id=$rid1
keystone user-role-add --tenant-id=$kid1 --user-id=$uid1 --role-id=$rid1
neutron net-create public --router:external=True
neutron subnet-create --allocation-pool start=${EXTERNAL_NET}.2,end=${EXTERNAL_NET}.254 public ${EXTERNAL_NET}.0/24
neutron net-create net10 --shared
neutron subnet-create net10 192.168.1.0/24 --dns_nameservers list=true 8.8.8.8 8.8.4.4
neutron router-create router1
sid=$(neutron subnet-list | grep "192.168.1.0/24" |  awk {'print $2'})
neutron router-interface-add router1 $sid
nid=$(neutron net-list | grep " public " |  awk {'print $2'}) 
neutron router-gateway-set router1 $nid
test -e /tmp/cirros-0.3.2-x86_64-uec.tar.gz || wget -nv -P /tmp/ http://download.cirros-cloud.net/0.3.2/cirros-0.3.2-x86_64-uec.tar.gz

image1_id=$(glance image-list | grep " cirros-0.3-x86_64 " |  awk {'print $2'})
image2_id=$(glance image-list | grep " precise-server " |  awk {'print $2'})
publicnet_id=$(neutron net-list | grep " public " |  awk {'print $2'})
public_router_id=$(neutron router-list | grep " router1 " |  awk {'print $2'})

if [ -z "$1" ]; then
    ip=127.0.0.1
else
    ip="$1"
fi
cd ..
cat >tempest.conf.jenkins<<EOF
#!/bin/bash
[DEFAULT]
#log_config = /opt/stack/tempest/etc/logging.conf.sample

# disable logging to the stderr
use_stderr = False

# log file
log_file = tempest.log

# lock/semaphore base directory
lock_path=/tmp

default_log_levels=tempest.stress=INFO,amqplib=WARN,sqlalchemy=WARN,boto=WARN,suds=INFO,keystone=INFO,eventlet.wsgi.server=WARN

# Print debugging output (set logging level to DEBUG instead
# of default WARNING level). (boolean value)
debug=true

[identity]
# This section contains configuration options that a variety of Tempest
# test clients use when authenticating with different user/tenant
# combinations

# The type of endpoint for a Identity service. Unless you have a
# custom Keystone service catalog implementation, you probably want to leave
# this value as "identity"
catalog_type = identity
# Ignore SSL certificate validation failures? Use when in testing
# environments that have self-signed SSL certs.
disable_ssl_certificate_validation = False
# URL for where to find the OpenStack Identity API endpoint (Keystone)
uri = http://$ip:5000/v2.0/
# URL for where to find the OpenStack V3 Identity API endpoint (Keystone)
uri_v3 = http://$ip:5000/v3/
# The identity region. Also used as the other services' region name unless
# they are set explicitly.
region = RegionOne

# This should be the username of a user WITHOUT administrative privileges
username = demo
# The above non-administrative user's password
password = secret
# The above non-administrative user's tenant name
tenant_name = demo

# This should be the username of an alternate user WITHOUT
# administrative privileges
alt_username = alt_demo
# The above non-administrative user's password
alt_password = secret
# The above non-administrative user's tenant name
alt_tenant_name = alt_demo

# This should be the username of a user WITH administrative privileges
admin_username = admin
# The above administrative user's password
admin_password = Cisco123
# The above administrative user's tenant name
admin_tenant_name = openstack

# The role that is required to administrate keystone.
admin_role = admin

[compute]
# This section contains configuration options used when executing tests
# against the OpenStack Compute API.

# Allows test cases to create/destroy tenants and users. This option
# enables isolated test cases and better parallel execution,
# but also requires that OpenStack Identity API admin credentials
# are known.
allow_tenant_isolation = false

# Allows test cases to create/destroy tenants and users. This option
# enables isolated test cases and better parallel execution,
# but also requires that OpenStack Identity API admin credentials
# are known.
allow_tenant_reuse = true

# Reference data for tests. The ref and ref_alt should be
# distinct images/flavors.
image_ref = $image1_id
image_ref_alt = $image2_id
flavor_ref = 1
flavor_ref_alt = 2

# User name used to authenticate to an instance. (string
# value)
image_ssh_user=cirros

# Password used to authenticate to an instance. (string value)
image_ssh_password=cubswin:)

# User name used to authenticate to an instance using the
# alternate image. (string value)
image_alt_ssh_user=cirros

# Password used to authenticate to an instance using the
# alternate image. (string value)
image_alt_ssh_password=cubswin:)

# Number of seconds to wait while looping to check the status of an
# instance that is building.
build_interval = 10

# Number of seconds to time out on waiting for an instance
# to build or reach an expected status
build_timeout = 600

# Run additional tests that use SSH for instance validation?
# This requires the instances be routable from the host
#  executing the tests
run_ssh = false

# Name of a user used to authenticate to an instance.
ssh_user = cirros

# Visible fixed network name
fixed_network_name = net10

# Network id used for SSH (public, private, etc)
network_for_ssh = net10

# IP version of the address used for SSH
ip_version_for_ssh = 4

# Number of seconds to wait to ping to an instance
ping_timeout = 60

# Number of seconds to wait to authenticate to an instance
ssh_timeout = 300

# Additinal wait time for clean state, when there is
# no OS-EXT-STS extension availiable
ready_wait = 0

# Number of seconds to wait for output from ssh channel
ssh_channel_timeout = 60

# Dose the SSH uses Floating IP?
use_floatingip_for_ssh = True

# The type of endpoint for a Compute API service. Unless you have a
# custom Keystone service catalog implementation, you probably want to leave
# this value as "compute"
catalog_type = compute

# The name of a region for compute. If empty or commented-out, the value of
# identity.region is used instead. If no such region is found in the service
# catalog, the first found one is used.
#region = RegionOne

# Does the Compute API support creation of images?
create_image_enabled = true

# For resize to work with libvirt/kvm, one of the following must be true:
# Single node: allow_resize_to_same_host=True must be set in nova.conf
# Cluster: the 'nova' user must have scp access between cluster nodes
resize_available = false

# Does the compute API support changing the admin password?
change_password_available=false

# Run live migration tests (requires 2 hosts)
live_migration_available = false

# Use block live migration (Otherwise, non-block migration will be
# performed, which requires XenServer pools in case of using XS)
use_block_migration_for_live_migration = false

# Supports iSCSI block migration - depends on a XAPI supporting
# relax-xsm-sr-check
block_migrate_supports_cinder_iscsi = false

# When set to false, disk config tests are forced to skip
disk_config_enabled = true

# When set to false, flavor extra data tests are forced to skip
flavor_extra_enabled = true

# Expected first device name when a volume is attached to an instance
volume_device_name = vdb

[compute-admin]
# This should be the username of a user WITH administrative privileges
# If not defined the admin user from the identity section will be used
username =
# The above administrative user's password
password =
# The above administrative user's tenant name
tenant_name =

[image]
# This section contains configuration options used when executing tests
# against the OpenStack Images API

# The type of endpoint for an Image API service. Unless you have a
# custom Keystone service catalog implementation, you probably want to leave
# this value as "image"
catalog_type = image

# The name of a region for image. If empty or commented-out, the value of
# identity.region is used instead. If no such region is found in the service
# catalog, the first found one is used.
#region = RegionOne

# The version of the OpenStack Images API to use
api_version = 1

# HTTP image to use for glance http image testing
http_image = http://download.cirros-cloud.net/0.3.1/cirros-0.3.1-x86_64-uec.tar.gz

[network]
# This section contains configuration options used when executing tests
# against the OpenStack Network API.

# Version of the Neutron API
api_version = v1.1
# Catalog type of the Neutron Service
catalog_type = network

# The name of a region for network. If empty or commented-out, the value of
# identity.region is used instead. If no such region is found in the service
# catalog, the first found one is used.
#region = RegionOne

# A large private cidr block from which to allocate smaller blocks for
# tenant networks.
tenant_network_cidr = 172.16.0.0/12

# The mask bits used to partition the tenant block.
tenant_network_mask_bits = 24

# If tenant networks are reachable, connectivity checks will be
# performed directly against addresses on those networks.
tenant_networks_reachable = false

# Id of the public network that provides external connectivity.
public_network_id = $publicnet_id

# Id of a shared public router that provides external connectivity.
# A shared public router would commonly be used where IP namespaces
# were disabled.  If namespaces are enabled, it would be preferable
# for each tenant to have their own router.
#public_router_id = $public_router_id


[volume]
# This section contains the configuration options used when executing tests
# against the OpenStack Block Storage API service

# The type of endpoint for a Cinder or Block Storage API service.
# Unless you have a custom Keystone service catalog implementation, you
# probably want to leave this value as "volume"
catalog_type = volume
# The name of a region for volume. If empty or commented-out, the value of
# identity.region is used instead. If no such region is found in the service
# catalog, the first found one is used.
#region = RegionOne
# The disk format to use when copying a volume to image
disk_format = raw
# Number of seconds to wait while looping to check the status of a
# volume that is being made available
build_interval = 10
# Number of seconds to time out on waiting for a volume
# to be available or reach an expected status
build_timeout = 300
# Runs Cinder multi-backend tests (requires 2 backends declared in cinder.conf)
# They must have different volume_backend_name (backend1_name and backend2_name
# have to be different)
multi_backend_enabled = false
backend1_name = BACKEND_1
backend2_name = BACKEND_2
# Protocol and vendor of volume backend to target when testing volume-types.
# You should update to reflect those exported by configured backend driver.
storage_protocol = iSCSI
vendor_name = Open Source

[object-storage]
# This section contains configuration options used when executing tests
# against the OpenStack Object Storage API.

# You can configure the credentials in the compute section

# The type of endpoint for an Object Storage API service. Unless you have a
# custom Keystone service catalog implementation, you probably want to leave
# this value as "object-store"
catalog_type = object-store

# The name of a region for object storage. If empty or commented-out, the
# value of identity.region is used instead. If no such region is found in
# the service catalog, the first found one is used.
#region = RegionOne

# Number of seconds to time on waiting for a container to container
# synchronization complete
container_sync_timeout = 120
# Number of seconds to wait while looping to check the status of a
# container to container synchronization
container_sync_interval = 5
# Set to True if the Account Quota middleware is enabled
accounts_quotas_available = True
# Set to True if the Container Quota middleware is enabled
container_quotas_available = True

# Set operator role for tests that require creating a container
operator_role = _member_

[boto]
# This section contains configuration options used when executing tests
# with boto.

# EC2 URL
ec2_url = http://$ip:8773/services/Cloud
# S3 URL
s3_url = http://$ip:3333

# Use keystone ec2-* command to get those values for your test user and tenant
aws_access =
aws_secret =

# Image materials for S3 upload
# ALL content of the specified directory will be uploaded to S3
s3_materials_path = /opt/stack/devstack/files/images/s3-materials/cirros-0.3.1

# The manifest.xml files, must be in the s3_materials_path directory
# Subdirectories not allowed!
# The filenames will be used as a Keys in the S3 Buckets

# ARI Ramdisk manifest. Must be in the above s3_materials_path
ari_manifest = cirros-0.3.1-x86_64-initrd.manifest.xml

# AMI Machine Image manifest. Must be in the above s3_materials_path
ami_manifest = cirros-0.3.1-x86_64-blank.img.manifest.xml

# AKI Kernel Image manifest, Must be in the above s3_materials_path
aki_manifest = cirros-0.3.1-x86_64-vmlinuz.manifest.xml

# Instance type
instance_type = m1.tiny

# TCP/IP connection timeout
http_socket_timeout = 5

# Number of retries actions on connection or 5xx error
num_retries = 1

# Status change wait timout
build_timeout = 120

# Status change wait interval
build_interval = 1

[orchestration]
# The type of endpoint for an Orchestration API service. Unless you have a
# custom Keystone service catalog implementation, you probably want to leave
# this value as "orchestration"
catalog_type = orchestration

# The name of a region for orchestration. If empty or commented-out, the value
# of identity.region is used instead. If no such region is found in the service
# catalog, the first found one is used.
#region = RegionOne

# Status change wait interval
build_interval = 1

# Status change wait timout. This may vary across environments as some some
# tests spawn full VMs, which could be slow if the test is already in a VM.
build_timeout = 300

# Instance type for tests. Needs to be big enough for a
# full OS plus the test workload
instance_type = m1.micro

# Name of heat-cfntools enabled image to use when launching test instances
# If not specified, tests that spawn instances will not run
#image_ref = ubuntu-vm-heat-cfntools

# Name of existing keypair to launch servers with. The default is not to specify
# any key, which will generate a keypair for each test class
#keypair_name = heat_key

max_template_size = 524288

[dashboard]
# URL where to find the dashboard home page
dashboard_url = 'http://$ip/horizon/'

# URL where to submit the login form
login_url = 'http://$ip/horizon/auth/login/'

[scenario]
# Directory containing image files
#img_dir = /opt/stack/new/devstack/files/images/cirros-0.3.1-x86_64-uec
img_dir = /tmp/cirros-0.3.1-x86_64-uec

# AMI image file name
ami_img_file = cirros-0.3.1-x86_64-blank.img

# ARI image file name
ari_img_file = cirros-0.3.1-x86_64-initrd

# AKI image file name
aki_img_file = cirros-0.3.1-x86_64-vmlinuz

# ssh username for the image file
ssh_user = cirros

# specifies how many resources to request at once. Used for large operations
# testing."
large_ops_number = 0

[cli]
# Enable cli tests
enabled = True
# directory where python client binaries are located
cli_dir = $WORKSPACE/tempest/.venv/bin
# Number of seconds to wait on a CLI timeout
timeout = 15

# Whether the tempest run location has access to the *-manage
# commands. In a pure blackbox environment it will not.
# (boolean value)
has_manage=false

[service_available]
# Whether or not cinder is expected to be available
cinder = False
# Whether or not neutron is expected to be available
neutron = True
# Whether or not glance is expected to be available
glance = True
# Whether or not swift is expected to be available
swift = True
# Whether or not nova is expected to be available
nova = True
# Whether or not Heat is expected to be available
heat = True
# Whether or not horizon is expected to be available
horizon = True

[stress]
# Maximum number of instances to create during test
max_instances = 32
# Time (in seconds) between log file error checks
log_check_interval = 60
# The default number of threads created while stress test
default_thread_number_per_action=4

[debug]
# Enable diagnostic commands
enable = True

[compute-feature-enabled]

#
# Options defined in tempest.config
#

# If false, skip all nova v3 tests. (boolean value)
api_v3=false

# If false, skip disk config tests (boolean value)
#disk_config=true

# A list of enabled compute extensions with a special entry
# all which indicates every extension is enabled (list value)
#api_extensions=all

# A list of enabled v3 extensions with a special entry all
# which indicates every extension is enabled (list value)
#api_v3_extensions=all

# Does the test environment support changing the admin
# password? (boolean value)
#change_password=false

# Does the test environment support resizing? (boolean value)
#resize=false

# Does the test environment support pausing? (boolean value)
#pause=true

# Does the test environment support suspend/resume? (boolean
# value)
#suspend=true

# Does the test environment support live migration available?
# (boolean value)
#live_migration=false

# Does the test environment use block devices for live
# migration (boolean value)
#block_migration_for_live_migration=false

# Does the test environment block migration support cinder
# iSCSI volumes (boolean value)
#block_migrate_cinder_iscsi=false

# Enable VNC console. This configuration value should be same
# as [nova.vnc]->vnc_enabled in nova.conf (boolean value)
#vnc_console=false
tenant_network_v6_cidr=2003::/64
tenant_network_v6_mask_bits=96
ipv6=true
ipv6_subnet_attributes=true
EOF

