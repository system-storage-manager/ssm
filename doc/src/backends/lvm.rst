Lvm backend
===========

Pools, volumes and snapshots can be created with lvm, which pretty much match
the lvm abstraction.

pool
    Lvm pool is just *volume group* in lvm language. It means that it is
    grouping devices and new logical volumes can be created out of the lvm
    pool. Default lvm pool name is **lvm_pool**.

    Lvm pool is created when **create** or **add** command is used with
    devices specified and non existing pool name.

volume
    Lvm volume is just *logical volume* in lvm language. Lvm volume can be
    created wit **create** command.

snapshot
    Lvm volumes can be snapshotted as well. When a snapshot is created from
    the lvm volume, new *snapshot* volume is created, which can be handled as
    any other lvm volume. Unlike :ref:`btrfs <btrfs-backend>` lvm is able
    to distinguish snapshot from regular volume, so there is no need for a
    snapshot name to match special pattern.

device
    Lvm requires *physical device* to be created on the device, but with
    **ssm** this is transparent for the user.
