Environment variables
=====================

SSM_DEFAULT_BACKEND
    Specify which backend will be used by default. This can be overridden by
    specifying the **-b** or **--backend** argument. Currently only *lvm* and
    *btrfs* are supported.

SSM_LVM_DEFAULT_POOL
    Name of the default lvm pool to be used if the **-p** or **--pool**
    argument is omitted.

SSM_BTRFS_DEFAULT_POOL
    Name of the default btrfs pool to be used if the **-p** or **--pool**
    argument is omitted.

SSM_PREFIX_FILTER
    When this is set, **ssm** will filter out all devices, volumes and pools
    whose name does not start with this prefix. It is used mainly in the **ssm**
    test suite to make sure that we do not scramble the local system
    configuration.
