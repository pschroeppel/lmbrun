import os
import argparse
import time
import sys
import subprocess
import unicodedata
import re
from functools import reduce


def find_smallest_next(lst):
    if not lst:
        return 1
    else:
        free = [x for x in range(1, max(lst) + 2) if x not in lst]
        return min(free)


def get_next_dir(base_path, dir_prefix):
    id_len = 6

    if not os.path.exists(base_path):
        existing_ids = None
    else:
        existing_dirs = [dir for dir in os.listdir(base_path) if dir.startswith(dir_prefix) and len(dir) == len(dir_prefix) + id_len]
        existing_ids = [int(dir[len(dir_prefix):len(dir_prefix) + id_len]) for dir in existing_dirs]

    new_id = find_smallest_next(existing_ids)

    return dir_prefix + str(new_id).zfill(id_len)


def wait_dir_exists(path):
    t = 0.
    while not os.path.isdir(path):
        time.sleep(0.1)
        t += 0.1
        if t == 10.:
            sys.exit("This will never happen, I hope")


def get_extension(path):
    return os.path.splitext(path)[1]


def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    value = re.sub(r'[-\s]+', '-', value)
    return value


def run_in_shell_and_print(command):
    try:
        p = subprocess.Popen(command, stderr=subprocess.STDOUT, shell=True, executable='/usr/bin/bash')
        p.wait()
    except subprocess.CalledProcessError as exc:
        print("ERROR running: {}".format(command))
        try:
            print(exc.output.decode("utf-8"))
        except UnicodeEncodeError:
            print(exc.output)
        exit(1)
    except KeyboardInterrupt:
        print("KeyboardInterrupt")
        p.wait()


def run_in_shell(command):
    try:
        output = subprocess.check_output([command], stderr=subprocess.STDOUT, shell=True)
        return output
    except subprocess.CalledProcessError as exc:
        print("ERROR running: {}".format(command))
        try:
            print(exc.output.decode("utf-8"))
        except UnicodeEncodeError:
            print(exc.output)
        exit(1)


def readList(filename):
    list = []
    for line in open(filename).readlines():
        if line.strip() != '':
            list.append([s.strip() for s in line.split(":")])

    return list


def insert(file, string):
    open(file, 'a').write('%s\n' % string)


def notice(str, type=None):
    if type is None:
        print(str)
    else:
        print(type.upper() + ": " + str)


def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def get_extension(path):
    return os.path.splitext(path)[1]


def find_git(path):
    path = os.path.realpath(path)

    if not os.path.exists(path):
        return None

    git_dir = None
    while True:
        oldpath = path
        path, tmp = os.path.split(path)

        if oldpath == path:
            break

        if os.path.exists(os.path.join(path, '.git')):
            git_dir = path
            break

    return git_dir


def is_int(val):
    try:
        int(val)
        return True
    except ValueError:
        return False
