.. _quick-examples:

Quick examples
==============

List system storage::

    # ssm list
    ----------------------------------
    Device          Total  Mount point  
    ----------------------------------
    /dev/loop0    5.00 GB               
    /dev/loop1    5.00 GB               
    /dev/loop2    5.00 GB               
    /dev/loop3    5.00 GB               
    /dev/loop4    5.00 GB               
    /dev/sda    149.05 GB  PARTITIONED  
    /dev/sda1    19.53 GB  /            
    /dev/sda2    78.12 GB               
    /dev/sda3     1.95 GB  SWAP         
    /dev/sda4     1.00 KB               
    /dev/sda5    49.44 GB  /mnt/test    
    ----------------------------------
    ------------------------------------------------------------------------------
    Volume     Pool      Volume size  FS     FS size      Free  Type   Mount point  
    ------------------------------------------------------------------------------
    /dev/dm-0  dm-crypt     78.12 GB  ext4  78.12 GB  45.01 GB  crypt  /home        
    /dev/sda1               19.53 GB  ext4  19.53 GB  12.67 GB  part   /            
    /dev/sda5               49.44 GB  ext4  49.44 GB  29.77 GB  part   /mnt/test    
    ------------------------------------------------------------------------------

Create a volume of the defined size with the defined file system. The default
back-end is set to lvm and the lvm default pool name (volume group) is lvm_pool::

    # ssm create --fs ext4 -s 15G /dev/loop0 /dev/loop1


The name of the new volume is '/dev/lvm_pool/lvol001'. Resize the volume
to 10GB::

    # ssm resize -s-5G /dev/lvm_pool/lvol001


Resize the volume to 100G, but it may require adding more devices into the
pool::

    # ssm resize -s 100G /dev/lvm_pool/lvol001 /dev/loop2

Now we can try to create a new lvm volume named 'myvolume' from the remaining pool
space with the xfs file system and mount it to /mnt/test1::

    # ssm create --fs xfs --name myvolume /mnt/test1

List all volumes with file systems::

    # ssm list filesystems
    -----------------------------------------------------------------------------------------------
    Volume                  Pool        Volume size  FS      FS size      Free  Type    Mount point  
    -----------------------------------------------------------------------------------------------
    /dev/lvm_pool/lvol001   lvm_pool       25.00 GB  ext4   25.00 GB  23.19 GB  linear               
    /dev/lvm_pool/myvolume  lvm_pool        4.99 GB  xfs     4.98 GB   4.98 GB  linear  /mnt/test1   
    /dev/dm-0               dm-crypt       78.12 GB  ext4   78.12 GB  45.33 GB  crypt   /home        
    /dev/sda1                              19.53 GB  ext4   19.53 GB  12.67 GB  part    /            
    /dev/sda5                              49.44 GB  ext4   49.44 GB  29.77 GB  part    /mnt/test    
    -----------------------------------------------------------------------------------------------

You can then easily remove the old volume with::

    # ssm remove /dev/lvm_pool/lvol001

Now let's try to create a btrfs volume. Btrfs is a separate backend, not just a
file system. That is because btrfs itself has an integrated volume manager.
The default btrfs pool name is btrfs_pool.::

    # ssm -b btrfs create /dev/loop3 /dev/loop4

Now we create btrfs subvolumes. Note that the btrfs file system has to be mounted
in order to create subvolumes. However ssm will handle this for you.::

    # ssm create -p btrfs_pool
    # ssm create -n new_subvolume -p btrfs_pool


    # ssm list filesystems
    -----------------------------------------------------------------
    Device         Free      Used      Total  Pool        Mount point  
    -----------------------------------------------------------------
    /dev/loop0  0.00 KB  10.00 GB   10.00 GB  lvm_pool                 
    /dev/loop1  0.00 KB  10.00 GB   10.00 GB  lvm_pool                 
    /dev/loop2  0.00 KB  10.00 GB   10.00 GB  lvm_pool                 
    /dev/loop3  8.05 GB   1.95 GB   10.00 GB  btrfs_pool               
    /dev/loop4  6.54 GB   1.93 GB    8.47 GB  btrfs_pool               
    /dev/sda                       149.05 GB              PARTITIONED  
    /dev/sda1                       19.53 GB              /            
    /dev/sda2                       78.12 GB                           
    /dev/sda3                        1.95 GB              SWAP         
    /dev/sda4                        1.00 KB                           
    /dev/sda5                       49.44 GB              /mnt/test    
    -----------------------------------------------------------------
    -------------------------------------------------------
    Pool        Type   Devices     Free      Used     Total  
    -------------------------------------------------------
    lvm_pool    lvm    3        0.00 KB  29.99 GB  29.99 GB  
    btrfs_pool  btrfs  2        3.84 MB  18.47 GB  18.47 GB  
    -------------------------------------------------------
    -----------------------------------------------------------------------------------------------
    Volume                  Pool        Volume size  FS      FS size      Free  Type    Mount point  
    -----------------------------------------------------------------------------------------------
    /dev/lvm_pool/lvol001   lvm_pool       25.00 GB  ext4   25.00 GB  23.19 GB  linear               
    /dev/lvm_pool/myvolume  lvm_pool        4.99 GB  xfs     4.98 GB   4.98 GB  linear  /mnt/test1   
    /dev/dm-0               dm-crypt       78.12 GB  ext4   78.12 GB  45.33 GB  crypt   /home        
    btrfs_pool              btrfs_pool     18.47 GB  btrfs  18.47 GB  18.47 GB  btrfs                
    /dev/sda1                              19.53 GB  ext4   19.53 GB  12.67 GB  part    /            
    /dev/sda5                              49.44 GB  ext4   49.44 GB  29.77 GB  part    /mnt/test    
    -----------------------------------------------------------------------------------------------

Now let's free up some of the loop devices so that we can try to add them into
the btrfs_pool. So we'll simply remove lvm myvolume and resize lvol001 so we
can remove /dev/loop2. Note that myvolume is mounted so we have to unmount it
first.::

    # umount /mnt/test1
    # ssm remove /dev/lvm_pool/myvolume
    # ssm resize -s-10G /dev/lvm_pool/lvol001
    # ssm remove /dev/loop2

Add device to the btrfs file system::

    # ssm add /dev/loop2 -p btrfs_pool

Now let's see what happened. Note that to actually see btrfs subvolumes you have to
mount the file system first::

    # mount -L btrfs_pool /mnt/test1/
    # ssm list volumes
    ------------------------------------------------------------------------------------------------------------------------
    Volume                         Pool        Volume size  FS      FS size      Free  Type    Mount point                    
    ------------------------------------------------------------------------------------------------------------------------
    /dev/lvm_pool/lvol001          lvm_pool       15.00 GB  ext4   15.00 GB  13.85 GB  linear                                 
    /dev/dm-0                      dm-crypt       78.12 GB  ext4   78.12 GB  45.33 GB  crypt   /home                          
    btrfs_pool                     btrfs_pool     28.47 GB  btrfs  28.47 GB  28.47 GB  btrfs   /mnt/test1                     
    btrfs_pool:2012-05-09-T113426  btrfs_pool     28.47 GB  btrfs  28.47 GB  28.47 GB  btrfs   /mnt/test1/2012-05-09-T113426  
    btrfs_pool:new_subvolume       btrfs_pool     28.47 GB  btrfs  28.47 GB  28.47 GB  btrfs   /mnt/test1/new_subvolume       
    /dev/sda1                                     19.53 GB  ext4   19.53 GB  12.67 GB  part    /                              
    /dev/sda5                                     49.44 GB  ext4   49.44 GB  29.77 GB  part    /mnt/test                      
    ------------------------------------------------------------------------------------------------------------------------

Remove the whole lvm pool, one of the btrfs subvolumes, and one unused device
from the btrfs pool btrfs_loop3. Note that with btrfs, pools have the same
name as their volumes::

    # ssm remove lvm_pool /dev/loop2 /mnt/test1/new_subvolume/

Snapshots can also be done with ssm::

    # ssm snapshot btrfs_pool
    # ssm snapshot -n btrfs_snapshot btrfs_pool

With lvm, you can also create snapshots::

    # ssm create -s 10G /dev/loop[01]
    # ssm snapshot /dev/lvm_pool/lvol001

Now list all snapshots. Note that btrfs snapshots are actually just subvolumes
with some blocks shared with the original subvolume, so there is currently no
way to distinguish between those. ssm is using a little trick to search for
name patterns to recognize snapshots, so if you specify your own name for the
snapshot, ssm will not recognize it as snapshot, but rather as regular volume
(subvolume). This problem does not exist with lvm.::

    # ssm list snapshots
    -------------------------------------------------------------------------------------------------------------
    Snapshot                            Origin   Volume size     Size  Type    Mount point                         
    -------------------------------------------------------------------------------------------------------------
    /dev/lvm_pool/snap20120509T121611   lvol001      2.00 GB  0.00 KB  linear                                      
    btrfs_pool:snap-2012-05-09-T121313              18.47 GB           btrfs   /mnt/test1/snap-2012-05-09-T121313  
    -------------------------------------------------------------------------------------------------------------

