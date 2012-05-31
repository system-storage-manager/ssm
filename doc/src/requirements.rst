.. _ssm-requirements:

Requirements
============

Python 2.6 or higher is required to run this tool. System Storage Manager
can only be run as root since most of the commands requires root privileges.

There are other requirements listed bellow, but note that you do not
necessarily need all dependencies for all backends, however if some of the
tools required by the backend is missing, the backend would not work.


Python modules
--------------
* os
* re
* sys
* stat
* argparse
* datetime
* threading
* subprocess

System tools
------------
* tune2fs
* fsck.SUPPORTED_FS
* resize2fs
* xfs_db
* xfs_check
* xfs_growfs
* mkfs.SUPPORTED_FS
* which
* mount
* blkid
* wipefs

Lvm backend
-----------
* lvm2 binaries

Btrfs backend
-------------
* btrfs progs

Crypt backend
--------------
* dmsetup
* cryptsetup
