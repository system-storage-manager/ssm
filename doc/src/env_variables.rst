Environment variables
=====================

SSM_DEFAULT_BACKEND
    Specify which backend will be used by default. This can be overridden by
    specifying **-b** or **--backend** argument. Currently only *lvm* and *btrfs*
    is supported.

SSM_LVM_DEFAULT_POOL
    Name of the default lvm pool to be used if **-p** or **--pool** argument
    is omitted.

SSM_BTRFS_DEFAULT_POOL
    Name of the default btrfs pool to be used if **-p** or **--pool** argument
    is omitted.
