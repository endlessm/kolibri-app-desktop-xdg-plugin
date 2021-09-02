from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import base64
import configparser
import logging
import os
import re
import shutil
import subprocess

from kolibri.core.content.models import ChannelMetadata
from kolibri.dist.django.utils.functional import cached_property
from kolibri.dist.django.utils.six import BytesIO
from PIL import Image
from PIL import ImageDraw

from .path_utils import ensure_dir
from .path_utils import get_content_share_dir_path
from .path_utils import try_remove
from .pillow_utils import center_xy
from .pillow_utils import crop_image_to_square
from .pillow_utils import image_is_square
from .pillow_utils import paste_center
from .pillow_utils import resize_preserving_aspect_ratio

logger = logging.getLogger(__name__)

DATA_URI_PATTERN = re.compile(
    "^(data:)(?P<mimetype>[\\w\\/\\+-]*)(;base64),(?P<data_b64>.*)"
)

LAUNCHER_CATEGORIES = ("Education", "X-Kolibri-Channel")
LAUNCHER_PREFIX = "org.learningequality.Kolibri.Channel."


def update_channel_launchers(force=False):
    context = ChannelLaunchersContext()

    launchers_from_db = list(ChannelLauncher_FromDatabase.load_all(context))
    launchers_from_disk = list(ChannelLauncher_FromDisk.load_all(context))

    did_icons_change = False

    for launcher in launchers_from_disk:
        if not any(map(launcher.is_same_channel, launchers_from_db)):
            logger.info("Removing desktop launcher %s", launcher)
            launcher.delete()
            did_icons_change = True

    for launcher in launchers_from_db:
        if not any(map(launcher.is_same_channel, launchers_from_disk)):
            logger.info("Creating desktop launcher %s", launcher)
            launcher.save()
            did_icons_change = True
        elif force or any(map(launcher.compare, launchers_from_disk)):
            logger.info("Updating desktop launcher %s", launcher)
            launcher.save()
            did_icons_change = True

    if did_icons_change:
        update_icon_cache_params = [context.icon_theme_dir]

        try:
            system_theme_index = "/usr/share/icons/hicolor/index.theme"
            theme_index = os.path.join(context.icon_theme_dir, "index.theme")
            shutil.copyfile(system_theme_index, theme_index)
        except OSError:
            update_icon_cache_params += ["--ignore-theme-index"]

        try:
            subprocess.run(["gtk-update-icon-cache", *update_icon_cache_params])
        except OSError as error:
            logger.info("Error running gtk-update-icon-cache: %s", error)


class ChannelLaunchersContext(object):
    @property
    def applications_dir(self):
        return os.path.join(get_content_share_dir_path(), "applications")

    @property
    def icon_theme_dir(self):
        return os.path.join(get_content_share_dir_path(), "icons", "hicolor")


class ChannelLauncher(object):
    def __init__(self, context):
        self.__context = context

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
        return os.path.join(self.__context.applications_dir, self.desktop_file_name)

    @property
    def desktop_file_name(self):
        return "{prefix}{channel}.desktop".format(
            prefix=LAUNCHER_PREFIX, channel=self.channel_id
        )

    def get_icon_file_path(self, file_name, size="256x256"):
        return os.path.join(self.__context.icon_theme_dir, size, "apps", file_name)

    def compare(self, other):
        if not self.is_same_channel(other):
            return None
        self_channel, self_format = map(int, self.channel_version.split("~"))
        other_channel, other_format = map(int, other.channel_version.split("~"))
        return (self_channel - other_channel) or (self_format - other_format)

    def is_same_channel(self, other):
        return self.channel_id == other.channel_id

    def save(self):
        try:
            icon_name = self.write_channel_icon()
        except Exception as error:
            logger.warning(
                "Error writing icon file for channel %s: %s", self.channel_id, error
            )
            icon_name = None

        try:
            self.write_desktop_file(icon_name)
        except Exception as error:
            logger.warning(
                "Error writing desktop file for channel %s: %s", self.channel_id, error
            )

    def delete(self):
        self.delete_desktop_file()
        self.delete_channel_icon()

    def write_desktop_file(self, icon_name):
        raise NotImplementedError()

    def delete_desktop_file(self):
        os.remove(self.desktop_file_path)

    def write_channel_icon(self):
        raise NotImplementedError()

    def delete_channel_icon(self):
        raise NotImplementedError()


class ChannelLauncher_FromDatabase(ChannelLauncher):
    FORMAT_VERSION = 5

    def __init__(self, context, channelmetadata):
        super().__init__(context)
        self.__channelmetadata = channelmetadata

    @classmethod
    def load_all(cls, context):
        for channelmetadata in ChannelMetadata.objects.filter(root__available=True):
            yield cls(context, channelmetadata)

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

    def write_desktop_file(self, icon_name):
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
            "Desktop Entry",
            "Exec",
            f"flatpak run org.learningequality.Kolibri --channel-id {self.channel_id}",
        )
        desktop_file_parser.set("Desktop Entry", "X-Endless-LaunchMaximized", "True")
        desktop_file_parser.set(
            "Desktop Entry", "X-Kolibri-Channel-Id", self.channel_id
        )
        desktop_file_parser.set(
            "Desktop Entry", "X-Kolibri-Channel-Version", self.channel_version
        )
        desktop_file_parser.set(
            "Desktop Entry", "Categories", ";".join(LAUNCHER_CATEGORIES) + ";"
        )

        if icon_name:
            desktop_file_parser.set("Desktop Entry", "Icon", icon_name)

        ensure_dir(self.desktop_file_path)
        with open(self.desktop_file_path, "w") as desktop_entry_file:
            desktop_file_parser.write(desktop_entry_file, space_around_delimiters=False)

    def write_channel_icon(self):
        if not self.__channel_icon:
            return

        icon_name = "{prefix}{channel}".format(
            prefix=LAUNCHER_PREFIX, channel=self.channel_id
        )
        icon_file_path = self.get_icon_file_path(
            icon_name + self.__channel_icon.file_extension
        )

        ensure_dir(icon_file_path)
        with open(icon_file_path, "wb") as icon_file:
            self.__channel_icon.write(icon_file)

        return icon_name


class ChannelLauncher_FromDisk(ChannelLauncher):
    def __init__(self, context, desktop_file_path, desktop_entry_data):
        super().__init__(context)
        self.__desktop_file_path = desktop_file_path
        self.__desktop_entry_data = desktop_entry_data

    @classmethod
    def load_all(cls, context):
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
                yield cls(context, file_path, desktop_entry_data)

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
        # We can crudely guess the channel's icon file path

        icon_name = "{prefix}{channel}".format(
            prefix=LAUNCHER_PREFIX, channel=self.channel_id
        )
        icon_file_path = self.get_icon_file_path(icon_name + ".png")

        if os.path.isfile(icon_file_path):
            try_remove(icon_file_path)


class ChannelIcon(object):
    MIMETYPES_MAP = {"image/jpg": "image/jpeg"}

    icon_size = (256, 256)
    icon_inner_size = (256 - 48, 256 - 48)

    def __init__(self, thumbnail_data_uri):
        match = DATA_URI_PATTERN.match(thumbnail_data_uri)
        if not match:
            raise ValueError("Invalid data URI")
        self.__thumbnail_info = match.groupdict()

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

    @cached_property
    def thumbnail_image(self):
        thumbnail_io = BytesIO(self.thumbnail_data)
        return Image.open(thumbnail_io)

    @cached_property
    def icon_image(self):
        return self.__apply_icon_mask(self.__icon_inner_default_image)

    def write(self, icon_file):
        self.icon_image.save(icon_file)

    @cached_property
    def __icon_source_image(self):
        # The icon source image is the thumbnail, cropped to remove its own
        # padding, and cropped again to square if the icon is close to square
        # already.

        bbox = self.thumbnail_image.getbbox()
        image_cropped = self.thumbnail_image.crop(bbox)
        return crop_image_to_square(image_cropped, cut_area=0.04)

    @cached_property
    def __icon_inner_fill_image(self):
        # The "fill" icon variant resizes the source image to icon_inner_size.
        # The corners will be rounded, later, by __apply_icon_mask.

        base_image = Image.new("RGBA", self.icon_inner_size, (0, 0, 0, 0))
        thumbnail_image = resize_preserving_aspect_ratio(
            self.__icon_source_image, self.icon_inner_size, resample=Image.BICUBIC
        )
        paste_center(base_image, thumbnail_image)
        return base_image

    @cached_property
    def __icon_inner_tile_image(self):
        # The "tile" icon variant resizes the source image to a smaller space
        # inside icon_inner_size. The remaining space is filled with a white
        # background.

        thumbnail_size = (256 - 80, 256 - 80)

        base_image = Image.new("RGBA", self.icon_inner_size, (255, 255, 255, 255))
        thumbnail_image = resize_preserving_aspect_ratio(
            self.__icon_source_image, thumbnail_size, resample=Image.BICUBIC
        )
        paste_center(base_image, thumbnail_image)
        return base_image

    @cached_property
    def __icon_inner_default_image(self):
        # The default icon variant is the "fill" variant if it is exactly
        # square with no transparent pixels. Otherwise, it is the "tile"
        # variant.

        if image_is_square(self.__icon_inner_fill_image):
            return self.__icon_inner_fill_image
        else:
            return self.__icon_inner_tile_image

    def __apply_icon_mask(self, icon_image):
        # The icon mask is a rounded rectangle matching the GNOME icon set.

        shadow_size = (256 - 50, 256 - 50)
        plate_size = (256 - 52, 256 - 52)

        base_mask = Image.new("L", self.icon_size, (0,))
        base_mask_draw = ImageDraw.Draw(base_mask)
        base_mask_draw.rounded_rectangle(
            center_xy(base_mask.size, shadow_size),
            14,
            fill=(200,),
            width=1,
        )
        base_mask_draw.rounded_rectangle(
            center_xy(base_mask.size, plate_size),
            14,
            fill=(255,),
            outline=(255,),
            width=1,
        )

        base_image = Image.new("RGBA", self.icon_size, (0, 0, 0, 0))
        paste_center(base_image, icon_image)
        base_image.putalpha(base_mask)

        return base_image
