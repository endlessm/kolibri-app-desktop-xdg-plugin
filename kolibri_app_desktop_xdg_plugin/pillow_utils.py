from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from PIL import Image


def pil_formats_for_mimetype(mimetype):
    return [fmt for fmt, fmt_mime in Image.MIME.items() if fmt_mime == mimetype]


def paste_center(base_image, paste_image, **kwargs):
    center = [int((a - b) / 2) for a, b in zip(base_image.size, paste_image.size)]
    base_image.paste(paste_image, center, **kwargs)


def resize_preserving_aspect_ratio(source_image, target_size, **kwargs):
    source_size_square = (max(source_image.size),) * 2
    frame_image = Image.new("RGBA", source_size_square, (255, 255, 255, 0))
    paste_center(frame_image, source_image)
    return frame_image.resize(target_size, **kwargs)
