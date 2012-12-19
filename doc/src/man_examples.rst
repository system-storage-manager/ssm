Examples
========

**List** system storage information::

    # ssm list

**List** all pools in the system::

    # ssm list pools

**Create** a new 100GB **volume** with default lvm backend using */dev/sda* and
*/dev/sdb* with xfs file system::

    # ssm create --size 100G --fs xfs /dev/sda /dev/sdb

**Create** a new **volume** with btrfs backend using */dev/sda* and */dev/sdb* and
let the volume to be RAID 1::

    # ssm -b btrfs create --raid 1 /dev/sda /dev/sdb

Using lvm backend **create** a RAID 0 **volume** with devices */dev/sda* and
*/dev/sdb* with 128kB stripe size, ext4 file system and mount it on
*/home*::

    # ssm create --raid 0 --stripesize 128k /dev/sda /dev/sdb /home

**Extend** btrfs **volume** *btrfs_pool* by 500GB and use */dev/sdc* and
*/dev/sde* to cover the resize::

    # ssm resize -s +500G btrfs_pool /dev/sdc /dev/sde

**Shrink volume** */dev/lvm_pool/lvol001* by 1TB::

    # ssm resize -s-1t /dev/lvm_pool/lvol001

**Remove** */dev/sda* **device** from the pool, remove the *btrfs_pool*
**pool** and also remove the **volume** */dev/lvm_pool/lvol001*::

    # ssm remove /dev/sda btrfs_pool /dev/lvm_pool/lvol001

**Take a snapshot** of the btrfs volume *btrfs_pool:my_volume*::

    # ssm snapshot btrfs_pool:my_volume

**Add devices** */dev/sda* and */dev/sdb* into the *btrfs_pool* pool::

    # ssm add -p btrfs_pool /dev/sda /dev/sdb

**Mount btrfs subvolume** *btrfs_pool:vol001* on */mnt/test*::

    # ssm mount btrfs_pool:vol001 /mnt/test
