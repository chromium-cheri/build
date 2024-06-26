#!/usr/bin/env python3
# Copyright 2016 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Automates running sysroot_creator.py for each supported arch.
"""


import hashlib
import json
import multiprocessing
import os
import sys
import textwrap

import sysroot_creator

DEFAULT_URL_PREFIX = ("https://commondatastorage.googleapis.com/"
                      "chrome-linux-sysroot/toolchain")

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

def sha1sumfile(filename):
    sha1 = hashlib.sha1()
    with open(filename, "rb") as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()


def build_and_upload(arch, lock):
    sysroot_creator.build_sysroot(arch)
    sysroot_creator.upload_sysroot(arch)

    tarball = "%s_%s_%s_sysroot.tar.xz" % (
        sysroot_creator.DISTRO,
        sysroot_creator.RELEASE,
        arch.lower(),
    )
    tarxz_path = os.path.join(
        SCRIPT_DIR,
        "..",
        "..",
        "..",
        "out",
        "sysroot-build",
        sysroot_creator.RELEASE,
        tarball,
    )
    sha1sum = sha1sumfile(tarxz_path)
    sysroot_dir = "%s_%s_%s-sysroot" % (
        sysroot_creator.DISTRO,
        sysroot_creator.RELEASE,
        arch.lower(),
    )

    sysroot_metadata = {
        "Sha1Sum": sha1sum,
        "SysrootDir": sysroot_dir,
        "Tarball": tarball,
        "URL": DEFAULT_URL_PREFIX,
    }
    with lock:
        fname = os.path.join(SCRIPT_DIR, "sysroots.json")
        sysroots = json.load(open(fname))
        with open(fname, "w") as f:
            sysroots["%s_%s" % (sysroot_creator.RELEASE,
                                arch.lower())] = sysroot_metadata
            f.write(
                json.dumps(sysroots,
                           sort_keys=True,
                           indent=4,
                           separators=(",", ": ")))
            f.write("\n")


def main():
    key = "%s-%s" % (sysroot_creator.ARCHIVE_TIMESTAMP,
                     sysroot_creator.SYSROOT_RELEASE)

    procs = []
    lock = multiprocessing.Lock()
    for arch in sysroot_creator.TRIPLES:
        proc = multiprocessing.Process(
            target=build_and_upload,
            args=(arch, lock),
        )
        procs.append((
            "%s %s (%s)" %
            (sysroot_creator.DISTRO, sysroot_creator.RELEASE, arch),
            proc,
        ))
        proc.start()
    for _, proc in procs:
        proc.join()

    print("SYSROOT CREATION SUMMARY")
    failures = 0
    for name, proc in procs:
        if proc.exitcode:
            failures += 1
        status = "FAILURE" if proc.exitcode else "SUCCESS"
        print("%s sysroot creation\t%s" % (name, status))
    if not failures:
        sysroot_gni = textwrap.dedent('''\
            # Copyright 2024 The Chromium Authors
            # Use of this source code is governed by a BSD-style license that
            # can be found in the LICENSE file.

            # This file was generated by
            # build/linux/sysroot_scripts/build_and_upload.py

            cr_sysroot_key = "%s"
        ''' % key)
        fname = os.path.join(SCRIPT_DIR, "sysroot.gni")
        with open(fname, "w") as f:
            f.write(sysroot_gni)

    return failures


if __name__ == "__main__":
    sys.exit(main())
