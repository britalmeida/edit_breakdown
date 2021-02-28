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

from dataclasses import dataclass
import logging
import math
import os

import blf
import bpy
from bpy_extras.image_utils import load_image

from . import draw_utils

log = logging.getLogger(__name__)



# Drawing Thumbnail Images ########################################################################

class ThumbnailImage:
    """Displayed thumbnail data"""

    def __init__(self):
        self.id_image = None # A Blender ID Image, which can be rendered by bgl.
        self.pos = (0, 0) # Position in px where the image should be displayed within a region.
        self.name = ""
        self.shot_idx = -1
        self.group_idx = -1
        self.pos_in_group = -1

thumbnail_images = [] # All the loaded thumbnails for an edit.
thumbnail_size = (0, 0) # The size in px at which the thumbnails should be displayed.

hovered_thumbnail = None
active_selected_thumbnail = None

thumbnail_draw_region = (0, 0, 0, 0) # Rectangle inside a Blender region where the thumbnails draw

group_by_character = True
group_by_character_prev = True

class ThumbnailGroup:

    def __init__(self):
        self.name = ""
        self.pos = (0, 0)
        self.shot_ids = []
        self.shot_rows = 0

thumbnail_groups = []


def calculate_thumbnail_draw_region():

    # Get size of the region containing the thumbnails.
    region = bpy.context.region
    total_available_w = region.width
    total_available_h = region.height

    start_w = 0 # If the tools side panel is open, the thumbnails must be shifted to the right

    # If the header and side panels render on top of the region, discount their size.
    # The thumbnails should not be occluded by the UI, even if set to transparent.
    system_prefs = bpy.context.preferences.system
    transparent_regions = False #system_prefs.use_region_overlap
    if transparent_regions:
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

    addon_prefs = bpy.context.preferences.addons['edit_breakdown'].preferences
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

    for i, img in enumerate(thumbnail_images):
        img.shot_idx = i
        if img.id_image.gl_load():
            raise Exception()

    num_images = len(thumbnail_images)
    log.info(f"Loaded {num_images} images.")


def fit_thumbnails_in_region():
    """Calculate the thumbnails' size and where to render each one so they fit the given region"""

    # If there are no images to fit, we're done!
    scene = bpy.context.scene
    shots = scene.edit_breakdown.shots
    if not shots:
        return

    log.debug("------Fit Images-------------------");

    if group_by_character:
        fit_thumbnails_in_group()
    else:
        del thumbnail_images[len(shots):-1] # Delete extra thumbnails added by grouping.
        fit_thumbnails_in_grid()


def fit_thumbnails_in_grid():
    """Calculate the thumbnails' size and where to render each one so they fit the given region

    The thumbnail size is roughly calculated by dividing the available region area by the number
    of images and preserving the image aspect ratio. However, this calculation will be off as
    soon as the images don't exactly fit a row or the last row is incomplete.
    To account for that, we take some space away from the region area, which will be used by
    margins and spacing between images. The thumbnail size is calculated to fit the smaller area.
    This way, images can be made to exactly fit a row by taking up whitespace.
    """

    num_images = len(thumbnail_images)

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


def fit_thumbnails_in_group():
    """ """

    scene = bpy.context.scene
    shots = scene.edit_breakdown.shots
    num_images = len(thumbnail_images)

    # Find the property definition.
    prop_to_group_by = 'cp_4a6872e3' # Character
    #prop_to_group_by = 'cp_14c9110f' # Sequence

    try:
        #shot_cls = data.SEQUENCER_EditBreakdown_Shot
        #prop_rna = shot_cls.bl_rna.properties[prop_to_group_by]
        prop_rna = shots[0].rna_type.properties[prop_to_group_by]
    except KeyError:
        return
    user_configured_props = scene.edit_breakdown.shot_custom_props
    prop_config = next((p for p in user_configured_props if p.identifier == prop_to_group_by), None)

    del thumbnail_images[len(shots):-1] # Delete extra thumbnails added by grouping.
    thumbnail_groups.clear()

    # Create the thumbnail groups
    if prop_rna.type == 'ENUM':
        for i, item in enumerate(prop_rna.enum_items):
            group = ThumbnailGroup()
            group.name = item.name
            thumbnail_groups.append(group)
    else:
        return

    if prop_config.data_type == 'ENUM_FLAG':
        unassigned_group = ThumbnailGroup()
        unassigned_group.name = "Unassigned"
        thumbnail_groups.append(unassigned_group)

    # Assign shots to groups
    for shot_idx, shot in enumerate(shots):
        value = shot.get_prop_value(prop_to_group_by)

        if prop_config.data_type == 'ENUM_FLAG':
            if value == 0:
                unassigned_group.shot_ids.append(shot_idx)
                thumbnail_images[shot_idx].group_idx = len(thumbnail_groups) - 1
                thumbnail_images[shot_idx].pos_in_group = len(unassigned_group.shot_ids) - 1
            else:
                usage_count = 0
                for enum_idx, item in enumerate(prop_rna.enum_items):
                    if (value & int(item.identifier)) != 0:
                        thumbnail_groups[enum_idx].shot_ids.append(shot_idx)

                        img = thumbnail_images[shot_idx]
                        usage_count += 1
                        if usage_count > 1:
                            new_img = ThumbnailImage()
                            new_img.name = str(thumbnail_images[shot_idx].name) + " (dup)"
                            new_img.id_image = thumbnail_images[shot_idx].id_image
                            thumbnail_images.append(new_img)
                            img = new_img

                        img.group_idx = enum_idx
                        img.pos_in_group = len(thumbnail_groups[enum_idx].shot_ids) - 1

        elif prop_config.data_type == 'ENUM_VAL':
            value = int(shot.get(prop_to_group_by, 0))
            active_enum_item = value
            thumbnail_groups[active_enum_item].shot_ids.append(shot_idx)
            thumbnail_images[shot_idx].group_idx = active_enum_item
            thumbnail_images[shot_idx].pos_in_group = len(thumbnail_groups[active_enum_item].shot_ids) - 1

    print(f"Assigned shots to {len(thumbnail_groups)} groups")
    for i, group in enumerate(thumbnail_groups):
        print(f"{i}: {group.name}, {len(group.shot_ids)}")

    # Determine positions based on numbers


    global thumbnail_size

    # Get size of the region containing the thumbnails.
    total_available_w = thumbnail_draw_region[2]
    total_available_h = thumbnail_draw_region[3]
    start_w = thumbnail_draw_region[0]

    log.debug(f"Region w:{total_available_w} h:{total_available_h}")

    # Get the available size, discounting white space size.
    group_titles_height = 22
    min_margin = 40 # Arbitrary 20px minimum for the top,bottom,left and right margins.
    total_spacing = (150, 40)
    available_w = total_available_w - total_spacing[0]
    available_h = total_available_h - total_spacing[1] - group_titles_height * len(thumbnail_groups)
    max_thumb_size = (total_available_w - min_margin,
                      total_available_h - min_margin)

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

    num_images_per_col = 0
    for group in thumbnail_groups:
        rows = math.ceil(len(group.shot_ids) / num_images_per_row)
        print(f"{group.name}, rows: {rows}")
        group.shot_rows = rows
        num_images_per_col += rows
    print(f"num_images_per_col {num_images_per_col} space {num_images_per_col * thumbnail_size[1]} > available space {available_h} ? ")

    l =0
    while num_images_per_col * thumbnail_size[1] > available_h and l < 10:
        l += 1
        num_images_per_row += 1

        num_images_per_col = 0
        for group in thumbnail_groups:
            rows = math.ceil(len(group.shot_ids) / num_images_per_row)
            print(f"{group.name}, rows: {rows}")
            group.shot_rows = rows
            num_images_per_col += rows

        print(f"[row/col] {num_images_per_row} {num_images_per_col} ? ")
        print(f"num_images_per_col {num_images_per_col} space {num_images_per_col * thumbnail_size[1]} > available space {available_h} ? ")

    log.debug(f"Thumbnail width  {thumbnail_size[0]:.3f}px, # per row: {num_images_per_row:.3f}")
    log.debug(f"Thumbnail height {thumbnail_size[1]:.3f}px, # per col: {num_images_per_col:.3f}")

    # Make sure that both a row and a column of images at the current scale will fit.
    # It is possible that, with few images and a region aspect ratio that is very different from
    # the images', there is enough area, but not enough length in one direction.
    # In that case, reduce the thumbnail size further.
    if original_image_w * scale_factor * num_images_per_row > max_thumb_size[0]:
        scale_factor = max_thumb_size[0] / (original_image_w * num_images_per_row)
    #if original_image_h * scale_factor * num_images_per_col > max_thumb_size[1]:
    #    scale_factor = max_thumb_size[1] / (original_image_h * num_images_per_col)
    log.debug(f"Reduced scale factor: {scale_factor:.3f}");

    thumbnail_size = (original_image_w * scale_factor,
                      original_image_h * scale_factor)

    # Get the remaining space not occupied by thumbnails and split it into margins
    # and spacing between the thumbnails.
    def calculate_spacing(total_available, available_space, num_thumbs):

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
    available_space = total_available_w - thumbnail_size[0] * num_images_per_row
    space_w = calculate_spacing(total_available_w, available_space, num_images_per_row)
    log.debug(f"Y")
    available_space = total_available_h - thumbnail_size[1] * num_images_per_col - group_titles_height * len(thumbnail_groups)
    space_h = calculate_spacing(total_available_h, available_space, num_images_per_col)

    margins = (space_w[0], space_h[0])
    spacing = (space_w[1], space_h[1] - 4)

    start_pos_x = start_w + margins[0]
    start_pos_y_title = total_available_h - margins[1] - group_titles_height
    start_pos_y_thumb = thumbnail_size[1] + 6
    thumbnail_step_x = thumbnail_size[0] + spacing[0]
    thumbnail_step_y = thumbnail_size[1] + spacing[1]
    last_start_pos_x = start_w + math.ceil(margins[0] + (num_images_per_row - 1)* (thumbnail_size[0] + spacing[0]))

    # Set the position of each group title
    for group_idx, group in enumerate(thumbnail_groups):
        group.pos = (start_pos_x, start_pos_y_title)
        start_pos_y_title -= group_titles_height + thumbnail_step_y * group.shot_rows

        duration_s = 0
        for shot_id in group.shot_ids:
            duration_s += shots[shot_id].duration_seconds
        group.name += f" (shots: {len(group.shot_ids)}, duration: {duration_s:.1f}s)"

    # Set the position of each thumbnail
    for img in thumbnail_images:
        row = int(img.pos_in_group / num_images_per_row)
        col = img.pos_in_group % num_images_per_row
        group_y = thumbnail_groups[img.group_idx].pos[1]
        img.pos = (start_pos_x + thumbnail_step_x * col,
                   group_y - start_pos_y_thumb - thumbnail_step_y * row)
        #print(f"{img.name} : [group/pos]({img.group_idx},{img.pos_in_group}) [row/col]({row},{col}) pos({img.pos[0]:.2f},{img.pos[1]:.2f})")



def is_thumbnail_view():
    """True if the current space has the edit breakdown view enabled.

    Note: I found no way of making a new space or mode toggle for this
    add-on, therefore, I'm hijacking the Display Channels toggle as it
    seems to be a little used option with no performance impact on the
    sequencer. This is less than ideal as it breaks the Display Channels
    functionality and doesn't make for a good user experience.
    TODO: whenever possible, switch the thumbnail view to its own editor
    space or add a toggle to the region/area/space if they get support
    for ID properties."""
    return bpy.context.space_data.preview_channels == 'COLOR'


def draw_edit_thumbnails():
    """Render the edit thumbnails"""

    if not is_thumbnail_view():
        return

    # Load the images the first time they're needed.
    if not thumbnail_images:
        load_edit_thumbnails()

    # Recalculate the thumbnail positions when the available drawing space changes.
    prev_draw_region = thumbnail_draw_region
    calculate_thumbnail_draw_region()
    if prev_draw_region != thumbnail_draw_region:
        fit_thumbnails_in_region()

    # Recalculate thumbnail positions if the grouping setting changes
    global group_by_character_prev
    if group_by_character_prev != group_by_character:
        group_by_character_prev = group_by_character
        fit_thumbnails_in_region()

    # If the resulting layout makes the images too small, skip rendering.
    if thumbnail_size[0] <= 5 or thumbnail_size[1] <= 5:
        return

    if group_by_character:
        font_id = 0 # Default font.
        blf.size(font_id, 12, 72)
        for group in thumbnail_groups:
            blf.position(font_id, group.pos[0], group.pos[1], 0)
            blf.draw(font_id, group.name)

    # Render each image.
    draw_utils.draw_thumbnails(thumbnail_images, thumbnail_size)


def draw_background():
    if not is_thumbnail_view():
        return
    region = bpy.context.region
    draw_utils.draw_background((region.width, region.height))


def draw_tool_active_tag():
    """Draw the value of the active tag on top of each thumbnail"""

    scene = bpy.context.scene
    shots = scene.edit_breakdown.shots
    if not shots:
        return

    def get_color_for_tag(prop_config, value):
        """Get the color to display the value of a property for the tag tool"""

        base_color = prop_config.color
        alpha = base_color[3]

        if prop_config.data_type in ['BOOLEAN', 'ENUM_FLAG', 'ENUM_VAL']:
            alpha *= 0.05 if (value == 0) else 1.0
        elif prop_config.data_type == 'INT':
            val_span = prop_config.range_max - prop_config.range_min
            alpha_span = 1.0 - 0.15
            alpha *= 0.15 + (alpha_span / val_span) * (value - prop_config.range_min)

        return (base_color[0], base_color[1], base_color[2], alpha)

    active_tool = bpy.context.workspace.tools.from_space_sequencer('PREVIEW')
    if active_tool and active_tool.idname == "edit_breakdown.thumbnail_tag_tool":

        # Tags show as full-width stripes at the bottom of thumbnails
        tag_size = (thumbnail_size[0], max(4, int(thumbnail_size[1] * 0.23)))

        tag = active_tool.operator_properties("edit_breakdown.thumbnail_tag").tag
        try:
            tag_rna = shots[0].rna_type.properties[tag]
        except KeyError:
            return

        user_configured_props = scene.edit_breakdown.shot_custom_props
        prop_config = next((p for p in user_configured_props if p.identifier == tag), None)
        if prop_config:
            tag_default_value = 0
            # Get the active enum item as an integer value
            if prop_config.data_type in ['ENUM_FLAG', 'ENUM_VAL']:
                try:
                    active_enum_item = int(active_tool.operator_properties("edit_breakdown.thumbnail_tag").tag_enum_option)
                    # Convert power of 2 value to a sequential index
                    if prop_config.data_type == 'ENUM_VAL':
                        active_enum_item = active_enum_item.bit_length() - 1
                except ValueError:
                    log.warning("Active tag enum value is invalid")
                    return

            for img in thumbnail_images:
                value = int(shots[img.shot_idx].get(tag, tag_default_value))
                if prop_config.data_type == 'ENUM_FLAG':
                    value = int(value & active_enum_item != 0)
                elif prop_config.data_type == 'ENUM_VAL':
                    value = int(value == active_enum_item)
                tag_color = get_color_for_tag(prop_config, value)
                draw_utils.draw_boolean_tag(img.pos, tag_size, tag_color)


def draw_overlay():
    """Draw overlay effects on top of the thumbnails"""

    if not is_thumbnail_view():
        return

    draw_tool_active_tag()

    if hovered_thumbnail:
        draw_utils.draw_hover_highlight(hovered_thumbnail.pos, thumbnail_size)

    if active_selected_thumbnail:
        size = (thumbnail_size[0] + 2, thumbnail_size[1] + 2)
        pos = (active_selected_thumbnail.pos[0] - 1,
               active_selected_thumbnail.pos[1] - 1)
        draw_utils.draw_selected_frame(pos, size)



# Add-on Registration #############################################################################

draw_handles = []
space = bpy.types.SpaceSequenceEditor


def register():

    draw_handles.append(space.draw_handler_add(draw_background, (), 'PREVIEW', 'POST_PIXEL'))
    draw_handles.append(space.draw_handler_add(draw_edit_thumbnails, (), 'PREVIEW', 'POST_PIXEL'))
    draw_handles.append(space.draw_handler_add(draw_overlay, (), 'PREVIEW', 'POST_PIXEL'))
    #draw_handles.append(space.draw_handler_add(draw_text, (), 'PREVIEW', 'POST_PIXEL'))


def unregister():

    for handle in reversed(draw_handles):
        space.draw_handler_remove(handle, 'PREVIEW')
