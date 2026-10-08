"""
Windows compatibility shim for genlayer-test's direct-mode stdin injection.

``gltest.direct.loader._inject_message_to_fd0`` duplicates a temp file onto fd 0 and then
immediately tries to ``os.unlink`` the original path. On Windows this raises
``PermissionError`` because the duplicated handle still holds the file open. We patch the
function to tolerate that one failure mode rather than modifying the installed package.
Unrelated to CharterGate contract logic; harmless on POSIX.
"""

import os
import tempfile

from gltest.direct import loader as _gltest_loader


def _inject_message_to_fd0_windows_safe(vm) -> None:
    from genlayer.py import calldata
    from genlayer.py.types import Address

    def as_address(value):
        return Address(value) if isinstance(value, bytes) else value

    message_data = {
        "contract_address": as_address(vm._contract_address),
        "sender_address": as_address(vm.sender),
        "origin_address": as_address(vm.origin),
        "stack": [],
        "value": vm._value,
        "datetime": vm._datetime,
        "is_init": False,
        "chain_id": vm._chain_id,
        "entry_kind": 0,
        "entry_data": b"",
        "entry_stage_data": None,
    }

    fd, path = tempfile.mkstemp()
    try:
        os.write(fd, calldata.encode(message_data))
        os.lseek(fd, 0, os.SEEK_SET)
        vm._original_stdin_fd = os.dup(0)
        os.dup2(fd, 0)
    finally:
        os.close(fd)
        try:
            os.unlink(path)
        except PermissionError:
            pass  # Windows keeps the duplicated fd 0 handle open; the OS temp dir reclaims it.


_gltest_loader._inject_message_to_fd0 = _inject_message_to_fd0_windows_safe


# genlayer-test 0.29.2 direct mode reads ``gl.message_raw`` once at import and its
# ``_refresh_gl_message`` updates sender/origin but never the datetime, so ``warp()`` would not
# reach a contract that reads ``gl.message_raw["datetime"]``. Real GenVM builds a fresh message
# (with that transaction's datetime) for every transaction; this shim reproduces that here.
import sys

from gltest.direct import vm as _gltest_vm

_original_refresh = _gltest_vm.VMContext._refresh_gl_message


def _refresh_with_datetime(self) -> None:
    _original_refresh(self)
    gl = sys.modules.get("genlayer.gl")
    if gl is not None and getattr(gl, "message_raw", None) is not None:
        gl.message_raw["datetime"] = self._datetime


_gltest_vm.VMContext._refresh_gl_message = _refresh_with_datetime
