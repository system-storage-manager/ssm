.. _for-developers:

For developers
==============

We are accepting patches! If you're interested in contributing to the System
Storage Manager code, just checkout the git repository located on
SourceForge. Please, base all of your work on the ``devel`` branch since
it is more up-to-date and it will save us some work when merging your
patches::

    git clone --branch devel git@github.com:system-storage-manager/ssm.git storagemanager-code

Any form of contribution - patches, documentation, reviews or rants are
appreciated. See :ref:`Mailing list section <mailing-list>` section.

.. _test-section:

Env Variables
-------------
There are multiple environment variables that might be useful. If the variable
is a flag, the safest way to use them is to use 'true' or '1' to enable it,
and unset the flag to disable it. Values like 'false' doesn't guarantee that
the flag will be really disabled.

Variables affecting default names for storage objects::

    export SSM_BTRFS_DEFAULT_POOL="btrfs_pool"
    export SSM_CRYPT_DEFAULT_POOL="crypt_pool"
    export SSM_CRYPT_DEFAULT_VOL_PREFIX="enc_vol"
    export SSM_DM_DEFAULT_POOL="md_pool"
    export SSM_LVM_DEFAULT_POOL="lvm_pool"

Variable changing what backend is used as default for creating pools, same as
the -b flag::

    export SSM_DEFAULT_BACKEND="lvm"

Enforce non-interactive run of ssm (always select default answer)::

    export SSM_NONINTERACTIVE="true"

Only storage objects starting with given prefix will be visible in SSM::

    export SSM_PREFIX_FILTER="SSMPREFIX"

Print out a full backtrace on errors. Without it, only a user-friendly message
is printed out::

    export SSM_PRINT_BACKTRACE="true"

Directory in which bash tests are run and fake /dev/ dir is created::

    export SSM_TEST_DIR="/path/to/ssm/tests/"

Whether bash tests should be run against system installation instead of the local
developmental version::

    export SSM_TEST_SYSTEM="true"


Tests
-----

System Storage Manager contains a regression testing suite to make sure that we
do not break things that should already work. We recommend that every developer
run these tests before sending patches::

    python test.py

Tests in System Storage Manager are divided into four levels.

#. First the doctest is executed.

#. Then we have unittests in ``tests/unittests/test_ssm.py`` which is testing
   the core of ssm ``ssmlib/main.py``. It is checking for basic things like
   required backend methods and variables, flag propagations, proper class
   initialization and finally whether commands actually result in the proper
   backend callbacks. It does not require root permissions and it does not
   touch your system configuration in any way. It actually should not invoke
   any shell command, and if it does it's a bug.

#. Second part of unittests is backend testing. We are mainly testing whether
   ssm commands result in proper backend operations. It does not require root
   permissions and it does not touch your system configuration in any way. It
   actually should not invoke any shell command and if it does it's a bug.

#. And finally there are real bash tests located in ``tests/bashtests``. Bash
   tests are divided into files. Each file tests one command for one backend
   and it contains a series of test cases followed by checks as to whether the
   command created the expected result. In order to test real system commands we
   have to create a system device to test on and not touch the existing system
   configuration.

   Before each test a number of devices are created using *dmsetup* in the
   test directory. These devices will be used in test cases instead of real
   devices.  Real operations are performed in those devices as they would be on
   the real system devices. This phase requires root privileges and it will not
   be run otherwise. In order to make sure that **ssm** does not touch any
   existing system configuration, each device, pool and volume name includes a
   special prefix, and the SSM_PREFIX_FILTER environment variable is set to make
   **ssm** to exclude all items which does not match this special prefix.

   The standard place for temporary files is within SSM tests directory.
   However, if for some reason you don't want/can't use this location, set
   the SSM_TEST_DIR environment variable to any other path.

   Even though we tried hard to make sure that the bash tests do not change
   your system configuration, we recommend you **not** to run tests with root
   privileges on your work or production system, but rather to run them on your
   testing machine.

If you change or create new functionality, please make sure that it is covered
by the System Storage Manager regression test suite to make sure that we do not
break it unintentionally.

.. important::
    Please, make sure to run full tests before you send a patch to the
    mailing list. To do so, simply run ``python test.py`` as root on
    your test machine.

.. _documentation-section:

Documentation
-------------

System Storage Manager documentation is stored in the ``doc/`` directory. The
documentation is built using **sphinx** software which helps us not to
duplicate text for different types of documentation (man page, html pages,
readme). If you are going to modify documentation, please make sure not to
modify manual page, html pages or README directly, but rather modify the
``doc/*.rst`` and ``doc/src/*.rst`` files accordingly so that the change is
propagated to all documents.

Moreover, parts of the documentation such as *synopsis* or ssm command
*options* are parsed directly from the ssm help output. This means that when
you're going to add or change arguments into **ssm** the only thing you have
to do is to add or change it in the ``ssmlib/main.py`` source code and then
run ``make dist`` in the ``doc/`` directory and all the documents should be
updated automatically.

.. important::
    Please make sure you update the documentation when you add or change
    **ssm** functionality if the format of the change requires it. Then
    regenerate all the documents using ``make dist`` and include changes
    in the patch.

.. _mailing-list:

Mailing list
------------

System Storage Manager developers communicate via the mailing list. The
address of our mailing list is storagemanager-devel@lists.sourceforge.net and
you can subscribe on the SourceForge project page
https://lists.sourceforge.net/lists/listinfo/storagemanager-devel. Mailing
list archives can be found here
http://sourceforge.net/mailarchive/forum.php?forum_name=storagemanager-devel.

This is also the list where patches are sent and where the review process is
happening. We do not have a separate *user* mailing list, so feel free to drop
your questions there as well.

Posting patches
---------------

As already mentioned, we are accepting patches! And we are very happy for every
contribution. If you're going to send a patch in, please make sure to follow
some simple rules:

#. Before you're going to post a patch, please run our regression testing suite
   to make sure that your change does not break someone else's work. See
   :ref:`Tests section <test-section>`

#. If you're making a change that might require documentation update, please
   update the documentation as well. See :ref:`Documentation section
   <documentation-section>`

#. Make sure your patch has all the requisites such as a *short description*
   preferably 50 characters long at max describing the main idea of the change.
   *Long description* describing what was changed with and why and finally
   Signed-off-by tag.

#. The preferred way of accepting patches is through pull requests on GitHub,
   but it is possible to send them to the mailing list if you don't have GitHub
   account.

#. If you're going to send a patch to the mailing list, please send the patch
   inlined in the email body. It is much better for review process.

.. hint::
    You can use **git** to do all the work for you. ``git format-patch`` and
    ``git send-email`` will help you with creating and sending the patch to the
    mailing list.
