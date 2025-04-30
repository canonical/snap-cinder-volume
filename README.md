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
