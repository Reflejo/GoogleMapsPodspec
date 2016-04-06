#!/usr/bin/env python

import StringIO
import glob
import itertools
import json
import shutil
import subprocess
import sys, os
import tarfile
import tempfile
import urllib2

POD_NAME = "GoogleMaps"
SYSLIB_ROOT = {
    "iOS": "/Applications/Xcode.app/Contents/Developer/Platforms/"
           "iPhoneOS.platform/Developer/SDKs/iPhoneOS.sdk",
    "Simulator": "/Applications/Xcode.app/Contents/Developer/Platforms/"
                 "iPhoneSimulator.platform/Developer/SDKs/iPhoneSimulator.sdk",
}
BUILD_DIR = tempfile.mkdtemp()
BINARY = "{build}/Frameworks/{name}.framework/Versions/A/{name}"\
    .format(name=POD_NAME, build=BUILD_DIR)
LIBTOOL_CMD = ["libtool", "-dynamic", BINARY, "-weak_framework",
               "UIKit", "-weak_framework", "Foundation", "-ObjC"]


def color(string, color="cyan"):
    """
    Returns the given string surrounded by the ansi escape symbols.
    """
    string = string.encode("utf-8")
    colors = {"red": 91, "green": 92, "purple": 94, "cyan": 96, "gray": 98}
    return "\033[{}m{}\033[00m".format(colors[color], string)


def execute(cmd):
    """
    Executes the given command. It prints it first and the result.

    - parameter cmd: The command to execute
    """
    print color("$ {}".format(" ".join(cmd)), color="gray")
    print color(subprocess.check_output(cmd), color="red")


def parse_pod(name):
    """
    Returns the archive url, linked frameworks and libraries from a given pod

    - parameter name: The cocoapods name
    """
    pods_json = subprocess.check_output(["pod", "spec", "cat", name])
    pod = json.loads(pods_json)

    file_url = pod["source"]["http"]
    frameworks = set(pod["frameworks"])
    libraries = set(pod["libraries"]) | set(['objc', 'System'])
    return (file_url, frameworks, libraries)


def link(target="x86_64", frameworks=[], libraries=[]):
    """
    Creates a dynamic library for a given arch, linked to the given
    frameworks/libraries.

    - parameter target:     The architecture (x86_64, i386, armv7, etc)
    - parameter frameworks: The needed linked frameworks
    - parameter libraries:  The needed linked libraries
    """
    is_simulator = target in ("x86_64", "i386")
    platform = "Simulator" if is_simulator else "iOS"

    # Linking dependencies
    frameworks = reduce(lambda x, y: x + ['-framework'] + [y], frameworks, [])
    libraries = map(lambda x: "-l{}".format(x), libraries)
    fpath = "-F{}/System/Library/Frameworks/".format(SYSLIB_ROOT[platform])
    lpath = "-L{}/usr/lib/".format(SYSLIB_ROOT[platform])
    syslibroot = ["-syslibroot", SYSLIB_ROOT[platform]] if is_simulator else []

    output = tempfile.mktemp()
    version = "-{}_version_min".format(
        "ios_simulator" if is_simulator else "ios"
    )

    print color(u"\u26a1\ufe0f Linking for {} {}".format(platform, target))
    extra_args = ["-o", output, fpath, lpath, "-arch_only", target,
                  version, "8.0"]
    cmd = LIBTOOL_CMD + frameworks + syslibroot + extra_args + libraries
    execute(cmd)
    return output


def main():
    file_url, frameworks, libs = parse_pod(POD_NAME)

    print color("Downloading file ...", color="purple")
    compressed = urllib2.urlopen(file_url).read()
    tar = tarfile.open(fileobj=StringIO.StringIO(compressed))

    print color("Extracting tar.gz ...\n", color="purple")
    tar.extractall(BUILD_DIR)

    output = "{}/{}_dynamic.dylib".format(BUILD_DIR, POD_NAME)
    targets = ["x86_64", "i386", "armv7", "armv7s", "arm64"]
    dylibs = [link(target, frameworks, libs) for target in targets]

    print color(u"\u2600\ufe0f Creating dynamic library ...")
    cmd = ["lipo", "-output", output, "-create"] + dylibs
    execute(cmd)

    framework = "{build}/Frameworks/{name}.framework".format(name=POD_NAME,
                                                             build=BUILD_DIR)
    print color(u"\U0001f680  Copying Info.plist ...")
    shutil.copy("./Info.plist", framework)

    print color(u"\U0001f680  Replacing binary and creating tar.gz ...")
    shutil.move(output, BINARY)

    tarfile_name = file_url.rsplit("/", 1)[-1]
    targz = tarfile.open(tarfile_name, "w:gz")
    os.chdir(BUILD_DIR)
    for file in glob.glob("./*"):
        targz.add(file)

    print color(u"\U0001f44d  File {} created!".format(targz.name),
                color="green")


if __name__ == "__main__":
    main()
