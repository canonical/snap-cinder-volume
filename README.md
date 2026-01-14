# Cinder Volume Snap

This repository contains the source for the the Cinder Volume snap.

This snap is designed to be used with a deployed OpenStack Control plane such
as delivered by Sunbeam.

## Getting Started

To get started with Cinder Volume, install the snap using snapd:

```bash
$ sudo snap install cinder-volume
```

The snap needs to be configured with credentials and URLs for the Identity
service of the OpenStack cloud that it will form part of. For example:

```bash
$ sudo snap set cinder-volume \
    cinder.project-id=project-uuid \
    cinder.user-id=user-uuid
```

You must also configure access to RabbitMQ:

```bash
$ sudo snap set cinder-volume \
    rabbitmq.url=rabbit://cinder:supersecure@10.152.183.212:5672/openstack
```

And provide the database connection URL:

```bash
$ sudo snap set cinder-volume \
    database.url=mysql+pymysql://cinder:password@10.152.183.210/cinder
```

The snap supports multiple storage backends, such as Ceph. For example, to
configure a Ceph backend:

```bash
$ sudo snap set cinder-volume \
    ceph.mybackend.rbd-pool=volumes \
    ceph.mybackend.rbd-user=cinder \
    ceph.mybackend.rbd-secret-uuid=uuid \
    ceph.mybackend.rbd-key=<base64key> \
    ceph.mybackend.volume-backend-name=mybackend
```

See "Configuration Reference" for full details.

## Configuration Reference

### cinder

* `cinder.project-id` Project ID for Cinder service
* `cinder.user-id` User ID for Cinder service
* `cinder.image-volume-cache-enabled` (false) Enable image volume cache
* `cinder.image-volume-cache-max-size-gb` (0) Max size of image volume cache in GB
* `cinder.image-volume-cache-max-count` (0) Max number of images in cache
* `cinder.default-volume-type` (optional) Default volume type
* `cinder.cluster` (optional) Cinder cluster name

### database

* `database.url` Full connection URL to the database

### rabbitmq

* `rabbitmq.url` Full connection URL to RabbitMQ

### settings

* `settings.debug` (false) Enable debug log level
* `settings.enable-telemetry-notifications` (false) Enable telemetry notifications

### ceph (backend)

Configure one or more Ceph backends using the `ceph.<backend-name>.*` namespace:

* `ceph.<backend-name>.volume-backend-name`  Name for this backend (must be unique)
* `ceph.<backend-name>.rbd-pool`             Name of the Ceph pool to use
* `ceph.<backend-name>.rbd-user`             Ceph user for access
* `ceph.<backend-name>.rbd-secret-uuid`      Secret UUID for authentication
* `ceph.<backend-name>.rbd-key`              Key for the Ceph user (base64 encoded)
* `ceph.<backend-name>.mon-hosts`            Comma-separated list of Ceph monitor hosts
* `ceph.<backend-name>.auth`                 Authentication type (default: cephx)
* `ceph.<backend-name>.rbd-exclusive-cinder-pool`  (true) Whether the pool is exclusive to Cinder
* `ceph.<backend-name>.report-discard-supported`   (true) Report discard support
* `ceph.<backend-name>.rbd-flatten-volume-from-snapshot` (false) Flatten volumes from snapshot
* `ceph.<backend-name>.image-volume-cache-enabled` (optional) Enable image volume cache for this backend
* `ceph.<backend-name>.image-volume-cache-max-size-gb` (optional) Max cache size in GB for this backend
* `ceph.<backend-name>.image-volume-cache-max-count` (optional) Max cache count for this backend
* `ceph.<backend-name>.volume-dd-blocksize`  (4096) Block size for volume copy operations

You may define multiple backends by using different backend names, e.g. `ceph.ceph1.*`, `ceph.ssdpool.*`, etc. Each backend name must be unique and each pool must only be used by one backend.

### hitachi (backend)

Configure one or more Hitachi VSP backends using the `hitachi.<backend-name>.*` namespace:

**Required options:**
* `hitachi.<backend-name>.volume-backend-name`  Unique name for this backend
* `hitachi.<backend-name>.san-ip`              Management IP or FQDN of the VSP array
* `hitachi.<backend-name>.san-login`           Username for the array
* `hitachi.<backend-name>.san-password`        Password for the array
* `hitachi.<backend-name>.hitachi-storage-id`  Serial number / storage ID of the array
* `hitachi.<backend-name>.hitachi-pools`       Comma-separated list of pool names or IDs

**Optional / common settings:**
* `hitachi.<backend-name>.protocol`            Protocol (`FC` or `iSCSI`) – default `FC`
* `hitachi.<backend-name>.hitachi-target-ports` Comma-separated list of target ports (e.g., `CL1-A,CL2-A`)
* `hitachi.<backend-name>.hitachi-group-request` (false) Auto-create HostGroups / iSCSI targets
* `hitachi.<backend-name>.hitachi-default-copy-method` Copy method (default `FULL`)
* `hitachi.<backend-name>.hitachi-copy-speed`  Copy speed (1–15, default 3)
* `hitachi.<backend-name>.hitachi-auth-method` iSCSI authentication method (`CHAP` or none)
* `hitachi.<backend-name>.hitachi-add-chap-user` (false) Auto-create CHAP user
* `hitachi.<backend-name>.hitachi-discard-zero-page` (true) Enable zero-page reclamation
* `hitachi.<backend-name>.hitachi-rest-timeout` (30) REST API timeout in seconds
* `hitachi.<backend-name>.hitachi-replication-number` (0) Replication instance number

See the driver documentation for additional advanced settings.

**Example:**
```bash
sudo snap set cinder-volume \
  hitachi.vsp350.volume-backend-name=vsp350 \
  hitachi.vsp350.san-ip=10.0.0.50 \
  hitachi.vsp350.san-login=svcuser \
  hitachi.vsp350.san-password=supersecret \
  hitachi.vsp350.hitachi-storage-id=45000 \
  hitachi.vsp350.hitachi-pools=DP_POOL_01 \
  hitachi.vsp350.protocol=FC
```

### pure (backend)

Configure one or more Pure Storage FlashArray backends using the `pure.<backend-name>.*` namespace:

**Required options:**
* `pure.<backend-name>.volume-backend-name`  Unique name for this backend
* `pure.<backend-name>.san-ip`              Management IP or FQDN of the FlashArray
* `pure.<backend-name>.pure-api-token`      REST API authorization token from Purity system

**Protocol configuration:**
* `pure.<backend-name>.protocol`            Protocol (`iscsi`, `fc`, or `nvme`) – default `iscsi`

**Network access control (iSCSI/NVMe):**
* `pure.<backend-name>.pure-iscsi-cidr`     (0.0.0.0/0) CIDR of FlashArray iSCSI targets hosts can connect to
* `pure.<backend-name>.pure-iscsi-cidr-list` Comma-separated list of CIDR for iSCSI targets (overrides pure-iscsi-cidr)
* `pure.<backend-name>.pure-nvme-cidr`      (0.0.0.0/0) CIDR of FlashArray NVMe targets hosts can connect to  
* `pure.<backend-name>.pure-nvme-cidr-list` Comma-separated list of CIDR for NVMe targets (overrides pure-nvme-cidr)
* `pure.<backend-name>.pure-nvme-transport` (`roce`) NVMe transport layer: `roce` or `tcp`

**Host and storage tuning:**
* `pure.<backend-name>.pure-host-personality` Host personality for protocol tuning: `aix`, `esxi`, `hitachi-vsp`, `hpux`, `oracle-vm-server`, `solaris`, `vms`
* `pure.<backend-name>.pure-automatic-max-oversubscription-ratio` (true) Auto-determine oversubscription ratio
* `pure.<backend-name>.pure-eradicate-on-delete` (false) Immediately eradicate volumes on delete (WARNING: not recoverable)

**Replication settings:**
* `pure.<backend-name>.pure-replica-interval-default` (3600) Snapshot replication interval in seconds
* `pure.<backend-name>.pure-replica-retention-short-term-default` (14400) Retain all snapshots for this time (seconds)
* `pure.<backend-name>.pure-replica-retention-long-term-per-day-default` (3) Snapshots to retain per day
* `pure.<backend-name>.pure-replica-retention-long-term-default` (7) Days to retain daily snapshots
* `pure.<backend-name>.pure-replication-pg-name` (`cinder-group`) Protection Group name for async replication
* `pure.<backend-name>.pure-replication-pod-name` (`cinder-pod`) Pod name for sync replication

**Advanced replication (TriSync):**
* `pure.<backend-name>.pure-trisync-enabled` (false) Enable 3-site replication (sync + async)
* `pure.<backend-name>.pure-trisync-pg-name` (`cinder-trisync`) Protection Group name for TriSync replication

**Requirements:**
- Pure Storage FlashArray with Purity 6.1.0+ (6.4.2+ for NVMe-TCP)
- API token from Purity system management interface
- Python SDK: py-pure-client 1.47.0+ (automatically installed)

**Example:**
```bash
sudo snap set cinder-volume \
  pure.flasharray1.volume-backend-name=flasharray1 \
  pure.flasharray1.san-ip=10.0.0.100 \
  pure.flasharray1.pure-api-token=your-api-token-here \
  pure.flasharray1.protocol=iscsi \
  pure.flasharray1.pure-host-personality=esxi \
  pure.flasharray1.pure-iscsi-cidr=10.0.0.0/24


### Dell PowerStore (backend)

Configure one or more Dell PowerStore backends using the `dellpowerstore.<backend-name>.*` namespace:

**Required options:**
* `dellpowerstore.<backend-name>.volume-backend-name`  Unique name for this backend
* `dellpowerstore.<backend-name>.san-ip`               Dell PowerStore management IP/FQDN 
* `dellpowerstore.<backend-name>.san-login`            Dell PowerStore management username 
* `dellpowerstore.<backend-name>.san-password`         Dell PowerStore management password

**Protocol configuration:**
* `dellpowerstore.<backend-name>.storage-protocol`     Protocol (`iscsi`, `fc`) – default `fc`

**Driver options:**
* `dellpowerstore.<backend-name>.powerstore-nvme`      Enable connection using NVMe-OF
* `dellpowerstore.<backend-name>.powerstore-ports`     Comma separated list of PowerStore iSCSI IPs or FC WWNs. All ports are allowed by default.
* `dellpowerstore.<backend-name>.replication-device`   Replication configuration. Must follow the format: backend_id:<backend_id>,san_ip:<san_ip>,san_login:<san_login>,san_password:<san_password>
