Introduction
============

Ssm aims to create unified user interface for various technologies like Device
Mapper (dm), Btrfs file system, Multiple Devices (md) and possibly more. In
order to do so we have a core abstraction layer in ``ssmlib/main.py``. This
abstraction layer should ideally know nothing about the underlying technology,
but rather comply with **device**, **pool** and **volume** abstraction.

Various backends can be registered in ``ssmlib/main.py`` in order to handle
specific storage technology implementing methods like *create*, *snapshot*, or
*remove* volumes and pools. The core will then call these methods to manage
the storage without needing to know what lies underneath it. There are already
several backends registered in ssm.
