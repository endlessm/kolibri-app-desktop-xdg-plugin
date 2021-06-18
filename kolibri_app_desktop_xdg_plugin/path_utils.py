from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import os

from kolibri.core.content.utils.paths import get_content_dir_path


def get_content_share_dir_path():
    """
    Returns the path to the directory where XDG files, like .desktop launchers
    and AppData, are located. By default, this is $KOLIBRI_HOME/content/xdg/share.
    """
    return os.path.join(get_content_dir_path(), "xdg", "share")


def ensure_dir(file_path):
    dir_path = os.path.dirname(file_path)
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path)
    return file_path


def try_remove(file_path):
    try:
        os.remove(file_path)
    except Exception:
        pass
