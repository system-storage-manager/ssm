Lvm backend
===========

Pools, volumes and snapshots can be created with lvm, which pretty much match
the lvm abstraction.

pool
    An lvm pool is just a *volume group* in lvm language. It means that it is
    grouping devices and new logical volumes can be created out of the lvm pool.
    The default lvm pool name is **lvm_pool**.

    An lvm pool is created when the **create** or **add** commands are used
    with specified devices and a non existing pool name.

    Alternatively a **thin pool** can be created as a result of using
    **--virtual-size** option to create **thin volume**.

volume
    An lvm volume is just a *logical volume* in lvm language. An lvm volume
    can be created with the **create** command.

snapshot
    Lvm volumes can be snapshotted as well. When a snapshot is created from
    the lvm volume, a new *snapshot* volume is created, which can be handled as
    any other lvm volume. Unlike :ref:`btrfs <btrfs-backend>` lvm is able
    to distinguish snapshot from regular volume, so there is no need for a
    snapshot name to match special pattern.

device
    Lvm requires a *physical device* to be created on the device, but with
    **ssm** this is transparent for the user.
