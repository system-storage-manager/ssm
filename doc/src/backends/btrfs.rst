.. _btrfs-backend:

Btrfs backend
=============

Btrfs is the file system with many advanced features including volume
management. This is the reason why btrfs is handled differently than other
*conventional* file systems in **ssm**. It is used as a volume
management back-end.

Pools, volumes and snapshots can be created with btrfs backend and here
is what it means from the btrfs point of view:

pool
    Pool is actually a btrfs file system itself, because it can be extended
    by adding more devices, or shrink by removing devices from it. Subvolumes
    and snapshots can also be created. When the new btrfs pool should be created
    **ssm** simply creates a btrfs file system, which means that every new
    btrfs pool has one volume of the same name as the pool itself which can
    not be removed without removing the entire pool. Default btrfs pool name is
    **btrfs_pool**.

    When creating new btrfs pool, the name of the pool is used as the file
    system label. If there is already existing btrfs file system in the system
    without a label, btrfs pool name will be generated for internal use
    in the following format "btrfs_{device base name}".

    Btrfs pool is created when **create** or **add** command is used with
    devices specified and non existing pool name.

volume
    Volume in btrfs back-end is actually just btrfs subvolume with the
    exception of the first volume created on btrfs pool creation, which is
    the file system itself. Subvolumes can only be created on btrfs file
    system when it is mounted, but user does not have to
    worry about that since **ssm** will automatically mount the file
    system temporarily in order to create a new subvolume.

    Volume name is used as subvolume path in the btrfs file system and every
    object in this path must exists in order to create a volume. Volume name
    for internal tracking and for representing to the user is generated in
    the format "{pool_name}:{volume name}", but volumes can be also referenced
    with its mount point.

    Btrfs volumes are only shown in the *list* output, when the file system is
    mounted, with the exception of the main btrfs volume - the file system
    itself. Also note that btrfs subvolume can not be resized.

    New btrfs volume can be created with **create** command.

snapshot
    Btrfs file system support subvolume snapshotting, so you can take a snapshot
    of any btrfs volume in the system with **ssm**. However btrfs does not
    distinguish between subvolumes and snapshots, because snapshot actually is
    just a subvolume with some block shared with different subvolume. It means,
    that **ssm** is not able to recognize btrfs snapshot directly, but instead
    it is trying to recognize special name format of the btrfs volume. However,
    if the *NAME* is specified when creating snapshot which does not match the
    special pattern, snapshot will not be recognized by the **ssm** and it will
    be listed as regular btrfs volume.

    New btrfs snapshot can be created with **snapshot** command.

device
    Btrfs does not require any special device to be created on.
