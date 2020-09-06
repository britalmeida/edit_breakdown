# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>

import logging
import math
import os

import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty
from bpy_extras.image_utils import load_image

from . import draw_utils

__name__ = "edit_breakdown" # WIP, add-on preferences will be removed

log = logging.getLogger(__name__)



# Drawing Thumbnail Images ########################################################################

class ThumbnailImage:
    """Displayed thumbnail data"""

    id_image = None # A Blender ID Image, which can be rendered by bgl.
    pos = (0, 0) # Position in px where the image should be displayed within a region.
    name = ""

thumbnail_images = [] # All the loaded thumbnails for an edit.
thumbnail_size = (0, 0) # The size in px at which the thumbnails should be displayed.

hovered_thumbnail = None
active_selected_thumbnail = None

thumbnail_draw_region = (0, 0, 0, 0) # Rectangle inside a Blender region where the thumbnails draw


def calculate_thumbnail_draw_region():

    # Get size of the region containing the thumbnails.
    region = bpy.context.region
    total_available_w = region.width
    total_available_h = region.height

    start_w = 0 # If the tools side panel is open, the thumbnails must be shifted to the right

    # If the header and side panels render on top of the region, discount their size.
    # The thumbnails should not be occluded by the UI, even if set to transparent.
    system_prefs = bpy.context.preferences.system
    if system_prefs.use_region_overlap:
        area = bpy.context.area
        for r in area.regions:
            if r.type == 'HEADER' and r.height > 1:
                total_available_h -= r.height
            if r.type == 'UI' and r.width > 1:
                total_available_w -= r.width
            if r.type == 'TOOLS' and r.width > 1:
                total_available_w -= r.width
                start_w = r.width

    global thumbnail_draw_region
    thumbnail_draw_region = (start_w, 0, total_available_w, total_available_h)


def load_edit_thumbnails():
    """Load all images from disk as resources to be rendered by the GPU"""

    addon_prefs = bpy.context.preferences.addons[__name__].preferences
    folder_name = addon_prefs.edit_shots_folder

    try:
        for filename in os.listdir(folder_name):
            img = ThumbnailImage()
            img.id_image = load_image(filename,
                dirname=folder_name,
                place_holder=False,
                recursive=False,
                ncase_cmp=True,
                convert_callback=None,
                verbose=False,
                relpath=None,
                check_existing=True,
                force_reload=False)
            thumbnail_images.append(img)
            img.name = int(filename.split('.')[0])
    except FileNotFoundError:
        # self.report({'ERROR'}, # Need an operator
        log.warning(
            f"Reading thumbnail images from '{folder_name}' failed: folder does not exist.")

    thumbnail_images.sort(key=lambda x: x.name, reverse=False)

    for img in thumbnail_images:
        if img.id_image.gl_load():
            raise Exception()

    num_images = len(thumbnail_images)
    log.info(f"Loaded {num_images} images.")


def fit_thumbnails_in_region():
    """Calculate the thumbnails' size and where to render each one so they fit the given region

    The thumbnail size is roughly calculated by dividing the available region area by the number
    of images and preserving the image aspect ratio. However, this calculation will be off as
    soon as the images don't exactly fit a row or the last row is incomplete.
    To account for that, we take some space away from the region area, which will be used by
    margins and spacing between images. The thumbnail size is calculated to fit the smaller area.
    This way, images can be made to exactly fit a row by taking up whitespace.
    """

    # If there are no images to fit, we're done!
    num_images = len(thumbnail_images)
    if num_images == 0:
        return

    log.debug("------Fit Images-------------------");

    global thumbnail_size

    # Get size of the region containing the thumbnails.
    total_available_w = thumbnail_draw_region[2]
    total_available_h = thumbnail_draw_region[3]
    start_w = thumbnail_draw_region[0]

    log.debug(f"Region w:{total_available_w} h:{total_available_h}")

    # Get the available size, discounting white space size.
    total_spacing = (150, 150) 
    min_margin = 40 # Arbitrary 20px minimum for the top,bottom,left and right margins
    available_w = total_available_w - total_spacing[0]
    available_h = total_available_h - total_spacing[1]
    max_thumb_size = (total_available_w - min_margin, total_available_h - min_margin)

    # Get the original size and aspect ratio of the images.
    # Assume all images in the edit have the same aspect ratio.
    original_image_w = thumbnail_images[0].id_image.size[0]
    original_image_h = thumbnail_images[0].id_image.size[1]
    image_aspect_ratio = original_image_w / original_image_h
    log.debug(f"Image a.ratio={image_aspect_ratio:.2f} ({original_image_w}x{original_image_h})")

    # Calculate by how much images need to be scaled in order to fit. (won't be perfect)
    available_area = available_w * available_h
    thumbnail_area = available_area / num_images
    # If the pixel area gets very small, early out, not worth rendering.
    if thumbnail_area < 20:
        thumbnail_size = (0, 0)
        return
    scale_factor = math.sqrt(thumbnail_area / (original_image_w * original_image_h))
    log.debug(f"Scale factor: {scale_factor:.3f}");
    thumbnail_size = (original_image_w * scale_factor,
                      original_image_h * scale_factor)

    num_images_per_row = math.ceil(available_w / thumbnail_size[0])
    num_images_per_col = math.ceil(num_images / num_images_per_row)
    log.debug(f"Thumbnail width  {thumbnail_size[0]:.3f}px, # per row: {num_images_per_row:.3f}")
    log.debug(f"Thumbnail height {thumbnail_size[1]:.3f}px, # per col: {num_images_per_col:.3f}")

    # Make sure that both a row and a column of images at the current scale will fit.
    # It is possible that, with few images and a region aspect ratio that is very different from
    # the images', there is enough area, but not enough length in one direction.
    # In that case, reduce the thumbnail size further.
    if original_image_w * scale_factor * num_images_per_row > max_thumb_size[0]:
        scale_factor = max_thumb_size[0] / (original_image_w * num_images_per_row)
    if original_image_h * scale_factor * num_images_per_col > max_thumb_size[1]:
        scale_factor = max_thumb_size[1] / (original_image_h * num_images_per_col)
    log.debug(f"Reduced scale factor: {scale_factor:.3f}");

    thumbnail_size = (original_image_w * scale_factor,
                      original_image_h * scale_factor)

    # Get the remaining space not occupied by thumbnails and split it into margins
    # and spacing between the thumbnails.
    def calculate_spacing(total_available, thumb_size, num_thumbs):

        available_space = total_available - thumb_size * num_thumbs
        log.debug(f"remaining space {available_space:.2f}px")

        spacing = 0
        if num_thumbs > 1:
            spacing = (available_space - min_margin) / (num_thumbs - 1)
            log.debug(f"spacing={spacing:.3f}")
            # Spacing between images should never be bigger than the margins
            spacing = min(math.ceil(spacing), min_margin)

        margin = (available_space - spacing * (num_thumbs - 1)) / 2
        log.debug(f"margins={margin:.3f}")
        margin = math.floor(margin)

        return (margin, spacing)

    log.debug(f"X")
    space_w = calculate_spacing(total_available_w, thumbnail_size[0], num_images_per_row)
    log.debug(f"Y")
    space_h = calculate_spacing(total_available_h, thumbnail_size[1], num_images_per_col)

    margins = (space_w[0], space_h[0])
    spacing = (space_w[1], space_h[1])

    # Set the position of each thumbnail
    start_pos_x = start_w + margins[0]
    start_pos_y = total_available_h - thumbnail_size[1] - margins[1]
    last_start_pos_x = start_w + math.ceil(margins[0] + (num_images_per_row - 1)* (thumbnail_size[0] + spacing[0]))

    for img in thumbnail_images:
        img.pos = (start_pos_x, start_pos_y)
        start_pos_x += thumbnail_size[0] + spacing[0]
        # Next row
        if start_pos_x > last_start_pos_x:
            start_pos_x = start_w + margins[0]
            start_pos_y -= thumbnail_size[1] + spacing[1]


def draw_edit_thumbnails():
    """Render the edit thumbnails"""

    # Load the images the first time they're needed.
    if not thumbnail_images:
        load_edit_thumbnails()

    # Recalculate the thumbnail positions when the available drawing space changes.
    prev_draw_region = thumbnail_draw_region
    calculate_thumbnail_draw_region()
    if prev_draw_region != thumbnail_draw_region:
        fit_thumbnails_in_region()

    # If the resulting layout makes the images too small, skip rendering.
    if thumbnail_size[0] <= 5 or thumbnail_size[1] <= 5:
        return

    # Render each image.
    draw_utils.draw_thumbnails(thumbnail_images, thumbnail_size)


def draw_background():
    region = bpy.context.region
    draw_utils.draw_background((region.width, region.height))


def draw_overlay():
    """Draw overlay effects on top of the thumbnails"""

    active_tool = bpy.context.workspace.tools.from_space_image_mode('UV')
    if active_tool and active_tool.idname == "edit_breakdown.tools.thumbnail_tag_tool":

        tag = active_tool.operator_properties("sequencer.thumbnail_tag").tag
        tag_color = (0.84, 0.0, 0.85, 0.9) if tag == 'has_fx' else (0.92, 0.81, 0.31, 0.9)

        tag_size = (thumbnail_size[0], max(4, thumbnail_size[1] * 0.23))

        shots = bpy.context.scene.edit_breakdown.shots
        tag_default_value = shots[0].rna_type.properties[tag].default
        for i, img in enumerate(thumbnail_images):
            if shots[i].get(tag, tag_default_value):
                draw_utils.draw_boolean_tag(img.pos, tag_size, tag_color)

    if hovered_thumbnail:
        draw_utils.draw_hover_highlight(hovered_thumbnail.pos, thumbnail_size)

    if active_selected_thumbnail:
        size = (thumbnail_size[0] + 2, thumbnail_size[1] + 2)
        pos = (active_selected_thumbnail.pos[0] - 1,
               active_selected_thumbnail.pos[1] - 1)
        draw_utils.draw_selected_frame(pos, size)



# Settings ########################################################################################


class SEQUENCER_EditBreakdown_Preferences(AddonPreferences):
    bl_idname = __name__

    edit_shots_folder: StringProperty(
        name="Edit Shots",
        description="Folder with image thumbnails for each shot",
        default="",
        subtype="FILE_PATH"
    )

    def draw(self, context):
        layout = self.layout

        col = layout.column()
        col.prop(self, "edit_shots_folder")



# Add-on Registration #############################################################################

classes = (
    SEQUENCER_EditBreakdown_Preferences,
)

draw_handles = []
space = bpy.types.SpaceImageEditor # SpaceSequenceEditor


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    draw_handles.append(space.draw_handler_add(draw_background, (), 'WINDOW', 'POST_PIXEL'))
    draw_handles.append(space.draw_handler_add(draw_edit_thumbnails, (), 'WINDOW', 'POST_PIXEL'))
    draw_handles.append(space.draw_handler_add(draw_overlay, (), 'WINDOW', 'POST_PIXEL'))


def unregister():

    for handle in draw_handles:
        space.draw_handler_remove(handle, 'WINDOW')

    for cls in classes:
        bpy.utils.unregister_class(cls)
