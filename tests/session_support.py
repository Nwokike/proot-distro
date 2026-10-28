"""Captured upstream command output shared by session contract tests."""

GOLDEN_CMD = (
    'env -i TERM="xterm-256color" HOME="/root" PATH="/usr/bin:/bin" '
    'LD_LIBRARY_PATH="/data/data/ng.kiri.prootdistro/files/usr/lib" '
    '"/data/data/ng.kiri.prootdistro/files/usr/lib/libproot.so" '
    "--change-id=0:0 --rootfs=. --cwd=/root --bind=/dev --bind=/proc "
    "--bind=/sys /bin/bash -l"
)

GOLDEN_CMD_WRAPPED = (
    'env -i TERM="xterm-256color" HOME="/root" '
    + chr(92)
    + chr(10)
    + '  "/data/data/ng.kiri.prootdistro/files/usr/lib/libproot.so" '
    + chr(92)
    + chr(10)
    + "  --change-id=0:0 --rootfs=. /bin/bash -l"
    + chr(10)
)
