Crypt backend
=============

The crypt backend in **ssm** uses cryptsetup and dm-crypt target to manage
encrypted volumes. The crypt backend can be used as a regular backend for
creating encrypted volumes on top of regular block devices, or even other
volumes (lvm or md volumes for example). Or it can be used to create
encrypted lvm volumes right away in a single step.

Only volumes can be created with crypt backend. This backend does not
support pooling and does not require special devices.


pool
    The crypt backend does not support pooling, and it is not possible to
    create crypt pool or add a device into a pool.

volume
    A volume in the crypt backend is the volume created by dm-crypt which
    represents the data on the original encrypted device in unencrypted form.
    The crypt backend does not support pooling, so only one device can be used
    to create crypt volume. It also does not support raid or any device
    concatenation.

    Currently two modes, or extensions are supported: luks and plain. Luks
    is used by default. For more information about the extensions, please see
    **cryptsetup** manual page.

snapshot
    The crypt backend does not support snapshotting, however if the encrypted
    volume is created on top of an lvm volume, the lvm volume itself can
    be snapshotted. The snapshot can be then opened by using **cryptsetup**.
    It is possible that this might change in the future so that **ssm** will
    be able to activate the volume directly without the extra step.

device
    The crypt backend does not require a special device to be created on.
