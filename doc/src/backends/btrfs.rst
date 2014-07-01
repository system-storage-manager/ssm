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
    A pool is actually a btrfs file system itself, because it can be extended
    by adding more devices, or shrunk by removing devices from it. Subvolumes
    and snapshots can also be created. When the new btrfs pool should be
    created, **ssm** simply creates a btrfs file system, which means that every
    new btrfs pool has one volume of the same name as the pool itself which can
    not be removed without removing the entire pool. The default btrfs pool
    name is **btrfs_pool**.

    When creating a new btrfs pool, the name of the pool is used as the file
    system label. If there is an already existing btrfs file system in the system
    without a label, a btrfs pool name will be generated for internal use in the
    following format "btrfs_{device base name}".

    A btrfs pool is created when the **create** or **add** command is used
    with specified devices and non existing pool name.

volume
    A volume in the btrfs back-end is actually just btrfs subvolume with the
    exception of the first volume created on btrfs pool creation, which is the
    file system itself. Subvolumes can only be created on the btrfs file system
    when it is mounted, but the user does not have to worry about that since
    **ssm** will automatically mount the file system temporarily in order to
    create a new subvolume.

    The volume name is used as subvolume path in the btrfs file system and
    every object in this path must exist in order to create a volume. The volume
    name for internal tracking and that is visible to the user is generated in the
    format "{pool_name}:{volume name}", but volumes can be also referenced by its
    mount point.

    The btrfs volumes are only shown in the *list* output, when the file system is
    mounted, with the exception of the main btrfs volume - the file system
    itself.

    Also note that btrfs volumes and subvolumes cannot be resized. This is
    mainly limitation of the btrfs tools which currently do not work reliably.

    A new btrfs volume can be created with the **create** command.

snapshot
    The btrfs file system supports subvolume snapshotting, so you can take a
    snapshot of any btrfs volume in the system with **ssm**. However btrfs does
    not distinguish between subvolumes and snapshots, because a snapshot is
    actually just a subvolume with some blocks shared with a different subvolume.
    This means, that **ssm** is not able to directly recognize a btrfs snapshot.
    Instead, **ssm** will try to recognize a special name format of the btrfs
    volume that denotes it is a snapshot. However, if the *NAME* is specified when
    creating snapshot which does not match the special pattern, snapshot will not
    be recognized by the **ssm** and it will be listed as regular btrfs volume.

    A new btrfs snapshot can be created with the **snapshot** command.

device
    Btrfs does not require a special device to be created on.
