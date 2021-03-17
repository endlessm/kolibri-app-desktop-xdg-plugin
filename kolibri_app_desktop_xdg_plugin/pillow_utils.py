from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from PIL import Image


def pil_formats_for_mimetype(mimetype):
    return [fmt for fmt, fmt_mime in Image.MIME.items() if fmt_mime == mimetype]


def center_xy(base_size, paste_size):
    if len(base_size) > 2 or len(paste_size) > 2:
        raise ValueError()
    x1, y1 = [int((a - b) / 2) for a, b in zip(base_size, paste_size)]
    return [x1, y1, x1 + paste_size[0], y1 + paste_size[1]]


def paste_center(base_image, paste_image, **kwargs):
    tmp = base_image.copy()
    tmp.paste(paste_image, center_xy(base_image.size, paste_image.size), **kwargs)
    base_image.alpha_composite(tmp)


def resize_preserving_aspect_ratio(source_image, target_size, **kwargs):
    source_size_square = (max(source_image.size),) * 2
    frame_image = Image.new("RGBA", source_size_square, (255, 255, 255, 0))
    paste_center(frame_image, source_image)
    return frame_image.resize(target_size, **kwargs)


def draw_rounded_rectangle(draw, xy, radius=0, fill=None, outline=None, width=1):
    # TODO: This is from <https://github.com/python-pillow/Pillow/blob/master/src/PIL/ImageDraw.py#L260-L348>
    #       Replace this once Pillow 8.2.0 is released.

    if isinstance(xy[0], (list, tuple)):
        (x0, y0), (x1, y1) = xy
    else:
        x0, y0, x1, y1 = xy

    d = radius * 2

    full_x = d >= x1 - x0
    if full_x:
        # The two left and two right corners are joined
        d = x1 - x0
    full_y = d >= y1 - y0
    if full_y:
        # The two top and two bottom corners are joined
        d = y1 - y0
    if full_x and full_y:
        # If all corners are joined, that is a circle
        return draw.ellipse(xy, fill, outline, width)

    if d == 0:
        # If the corners have no curve, that is a rectangle
        return draw.rectangle(xy, fill, outline, width)

    ink, fill = draw._getink(outline, fill)

    def draw_corners(pieslice):
        if full_x:
            # Draw top and bottom halves
            parts = (
                ((x0, y0, x0 + d, y0 + d), 180, 360),
                ((x0, y1 - d, x0 + d, y1), 0, 180),
            )
        elif full_y:
            # Draw left and right halves
            parts = (
                ((x0, y0, x0 + d, y0 + d), 90, 270),
                ((x1 - d, y0, x1, y0 + d), 270, 90),
            )
        else:
            # Draw four separate corners
            parts = (
                ((x1 - d, y0, x1, y0 + d), 270, 360),
                ((x1 - d, y1 - d, x1, y1), 0, 90),
                ((x0, y1 - d, x0 + d, y1), 90, 180),
                ((x0, y0, x0 + d, y0 + d), 180, 270),
            )
        for part in parts:
            if pieslice:
                draw.draw.draw_pieslice(*(part + (fill, 1)))
            else:
                draw.draw.draw_arc(*(part + (ink, width)))

    if fill is not None:
        draw_corners(True)

        if full_x:
            draw.draw.draw_rectangle((x0, y0 + d / 2 + 1, x1, y1 - d / 2 - 1), fill, 1)
        else:
            draw.draw.draw_rectangle((x0 + d / 2 + 1, y0, x1 - d / 2 - 1, y1), fill, 1)
        if not full_x and not full_y:
            draw.draw.draw_rectangle(
                (x0, y0 + d / 2 + 1, x0 + d / 2, y1 - d / 2 - 1), fill, 1
            )
            draw.draw.draw_rectangle(
                (x1 - d / 2, y0 + d / 2 + 1, x1, y1 - d / 2 - 1), fill, 1
            )
    if ink is not None and ink != fill and width != 0:
        draw_corners(False)

        if not full_x:
            draw.draw.draw_rectangle(
                (x0 + d / 2 + 1, y0, x1 - d / 2 - 1, y0 + width - 1), ink, 1
            )
            draw.draw.draw_rectangle(
                (x0 + d / 2 + 1, y1 - width + 1, x1 - d / 2 - 1, y1), ink, 1
            )
        if not full_y:
            draw.draw.draw_rectangle(
                (x0, y0 + d / 2 + 1, x0 + width - 1, y1 - d / 2 - 1), ink, 1
            )
            draw.draw.draw_rectangle(
                (x1 - width + 1, y0 + d / 2 + 1, x1, y1 - d / 2 - 1), ink, 1
            )
