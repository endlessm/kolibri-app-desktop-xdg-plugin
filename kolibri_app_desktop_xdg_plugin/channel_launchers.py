from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import base64
import configparser
import logging
import os
import re

from kolibri.core.content.models import ChannelMetadata
from kolibri.dist.django.utils.functional import cached_property
from kolibri.dist.django.utils.six import BytesIO
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFilter

from .pillow_utils import center_xy
from .pillow_utils import draw_rounded_rectangle
from .pillow_utils import paste_center
from .pillow_utils import pil_formats_for_mimetype
from .pillow_utils import resize_preserving_aspect_ratio
from .path_utils import ensure_dir
from .path_utils import get_content_share_dir_path
from .path_utils import is_subdir
from .path_utils import try_remove

logger = logging.getLogger(__name__)

DATA_URI_PATTERN = re.compile(
    "^(data:)(?P<mimetype>[\\w\\/\\+-]*)(;base64),(?P<data_b64>.*)"
)
LAUNCHER_PREFIX = "org.learningequality.Kolibri.Channel."


def update_channel_launchers(force=False):
    launchers_from_db = list(ChannelLauncher_FromDatabase.load_all())
    launchers_from_disk = list(ChannelLauncher_FromDisk.load_all())

    for launcher in launchers_from_disk:
        if not any(map(launcher.is_same_channel, launchers_from_db)):
            logger.info("Removing desktop launcher %s", launcher)
            launcher.delete()

    for launcher in launchers_from_db:
        if not any(map(launcher.is_same_channel, launchers_from_disk)):
            logger.info("Creating desktop launcher %s", launcher)
            launcher.save()
        elif force or any(map(launcher.compare, launchers_from_disk)):
            logger.info("Updating desktop launcher %s", launcher)
            launcher.save()


class ChannelLauncher(object):
    def __str__(self):
        return self.desktop_file_name

    @property
    def channel_id(self):
        raise NotImplementedError()

    @property
    def channel_version(self):
        raise NotImplementedError()

    @property
    def desktop_file_path(self):
        return os.path.join(self.applications_dir, self.desktop_file_name)

    @property
    def desktop_file_name(self):
        return "{prefix}{channel}.desktop".format(
            prefix=LAUNCHER_PREFIX, channel=self.channel_id
        )

    @property
    def applications_dir(self):
        return os.path.join(get_content_share_dir_path(), "applications")

    @property
    def icons_dir(self):
        return os.path.join(get_content_share_dir_path(), "icons")

    def compare(self, other):
        if not self.is_same_channel(other):
            return None
        self_channel, self_format = map(int, self.channel_version.split("~"))
        other_channel, other_format = map(int, other.channel_version.split("~"))
        return (self_channel - other_channel) or (self_format - other_format)

    def is_same_channel(self, other):
        return self.channel_id == other.channel_id

    def save(self):
        self.write_desktop_file()
        self.write_channel_icon()

    def delete(self):
        self.delete_desktop_file()
        self.delete_channel_icon()

    def write_desktop_file(self):
        raise NotImplementedError()

    def delete_desktop_file(self):
        os.remove(self.desktop_file_path)

    def write_channel_icon(self):
        raise NotImplementedError()

    def delete_channel_icon(self):
        raise NotImplementedError()


class ChannelLauncher_FromDatabase(ChannelLauncher):
    FORMAT_VERSION = 2

    def __init__(self, channelmetadata):
        self.__channelmetadata = channelmetadata

    @classmethod
    def load_all(cls):
        for channelmetadata in ChannelMetadata.objects.all():
            yield cls(channelmetadata)

    @property
    def channel_id(self):
        return self.__channelmetadata.id

    @property
    def channel_version(self):
        return "{}~{}".format(self.__channelmetadata.version, self.FORMAT_VERSION)

    @cached_property
    def __channel_icon(self):
        try:
            return ChannelIcon(self.__channelmetadata.thumbnail)
        except ValueError:
            return None

    @property
    def __icon_file_path(self):
        if not self.__channel_icon:
            return None

        icon_file_name = "{prefix}{channel}{extension}".format(
            prefix=LAUNCHER_PREFIX,
            channel=self.channel_id,
            extension=self.__channel_icon.file_extension,
        )
        return os.path.join(self.icons_dir, icon_file_name)

    def write_desktop_file(self):
        desktop_file_parser = configparser.ConfigParser()
        desktop_file_parser.optionxform = str
        desktop_file_parser.add_section("Desktop Entry")
        desktop_file_parser.set("Desktop Entry", "Version", "1.0")
        desktop_file_parser.set("Desktop Entry", "Type", "Application")
        desktop_file_parser.set("Desktop Entry", "Name", self.__channelmetadata.name)
        desktop_file_parser.set(
            "Desktop Entry", "Comment", self.__channelmetadata.tagline or ""
        )
        desktop_file_parser.set(
            "Desktop Entry", "Exec", 'gio open "kolibri:{}?standalone"'.format(self.channel_id)
        )
        desktop_file_parser.set("Desktop Entry", "X-Endless-LaunchMaximized", "True")
        desktop_file_parser.set(
            "Desktop Entry", "X-Kolibri-Channel-Id", self.channel_id
        )
        desktop_file_parser.set(
            "Desktop Entry", "X-Kolibri-Channel-Version", self.channel_version
        )
        desktop_file_parser.set("Desktop Entry", "Categories", "Education;")

        desktop_file_parser.set("Desktop Entry", "Icon", self.__icon_file_path or "")

        ensure_dir(self.desktop_file_path)
        with open(self.desktop_file_path, "w") as desktop_entry_file:
            desktop_file_parser.write(desktop_entry_file, space_around_delimiters=False)

    def write_channel_icon(self):
        if not self.__channel_icon:
            return

        ensure_dir(self.__icon_file_path)
        with open(self.__icon_file_path, "wb") as icon_file:
            self.__channel_icon.write(icon_file)


class ChannelLauncher_FromDisk(ChannelLauncher):
    def __init__(self, desktop_file_path, desktop_entry_data):
        self.__desktop_file_path = desktop_file_path
        self.__desktop_entry_data = desktop_entry_data

    @classmethod
    def load_all(cls):
        applications_dir = os.path.join(get_content_share_dir_path(), "applications")
        if not os.path.isdir(applications_dir):
            return
        for file_name in os.listdir(applications_dir):
            file_path = os.path.join(applications_dir, file_name)
            desktop_file_parser = configparser.ConfigParser()
            desktop_file_parser.optionxform = str
            desktop_file_parser.read(file_path)
            if desktop_file_parser.has_section("Desktop Entry"):
                desktop_entry_data = dict(
                    desktop_file_parser.items(section="Desktop Entry")
                )
                yield cls(file_path, desktop_entry_data)

    @property
    def channel_id(self):
        return self.__desktop_entry_data.get("X-Kolibri-Channel-Id")

    @property
    def channel_version(self):
        return self.__desktop_entry_data.get("X-Kolibri-Channel-Version")

    @property
    def desktop_file_path(self):
        return self.__desktop_file_path

    @property
    def desktop_file_name(self):
        return os.path.basename(self.desktop_file_path)

    def write_channel_icon(self):
        pass

    def delete_channel_icon(self):
        icon_path = self.__desktop_entry_data.get("Icon")
        if os.path.isabs(icon_path) and is_subdir(icon_path, self.icons_dir):
            try_remove(icon_path)
        else:
            # Icon is referred to by name, which we do not expect here.
            pass


class ChannelIcon(object):
    MIMETYPES_MAP = {"image/jpg": "image/jpeg"}

    def __init__(self, thumbnail_data_uri):
        match = DATA_URI_PATTERN.match(thumbnail_data_uri)
        self.__thumbnail_info = match.groupdict()
        if not self.file_extension or not self.thumbnail_data:
            raise ValueError("Invalid data URI")

    @property
    def mimetype(self):
        result = self.__thumbnail_info.get("mimetype")
        return self.MIMETYPES_MAP.get(result, result)

    @cached_property
    def thumbnail_data(self):
        return base64.b64decode(self.__thumbnail_info.get("data_b64"))

    @cached_property
    def file_extension(self):
        return ".png"

    def write(self, icon_file):
        icon_size = (256, 256)
        shadow_size = (256 - 50, 256 - 50)
        plate_size = (256 - 52, 256 - 52)
        thumbnail_size = (256 - 80, 256 - 80)

        plate_shadow_rgba = (200, 200, 200, 150)
        plate_stroke_rgba = (200, 200, 200, 255)
        plate_fill_rgba = (255, 255, 255, 255)

        base_image = Image.new("RGBA", icon_size, (255, 255, 255, 0))

        plate_image = Image.new("RGBA", base_image.size, (0,))
        plate_draw = ImageDraw.Draw(plate_image)
        draw_rounded_rectangle(
            plate_draw,
            center_xy(base_image.size, shadow_size),
            14,
            fill=plate_shadow_rgba,
            width=1,
        )
        draw_rounded_rectangle(
            plate_draw,
            center_xy(base_image.size, plate_size),
            14,
            fill=plate_fill_rgba,
            outline=plate_stroke_rgba,
            width=1,
        )

        thumbnail_io = BytesIO(self.thumbnail_data)
        thumbnail_image = Image.open(
            thumbnail_io, formats=pil_formats_for_mimetype(self.mimetype)
        )
        thumbnail_image.thumbnail(thumbnail_size, resample=Image.BICUBIC)

        thumbnail_image = resize_preserving_aspect_ratio(
            thumbnail_image, thumbnail_size, resample=Image.BICUBIC
        )

        paste_center(base_image, plate_image)
        paste_center(base_image, thumbnail_image)

        base_image.save(icon_file)
