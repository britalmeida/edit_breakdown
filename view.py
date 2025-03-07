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

import blf
import bpy
from bpy_extras.image_utils import load_image

from . import draw_utils

package_name = pathlib.Path(__file__).parent.name
log = logging.getLogger(__name__)


# Thumbnail and Groups UI Data ####################################################################

class ThumbnailImage:
    """UI data necessary to render a thumbnail instance.

    A single shot may have its thumbnail rendered more than once on screen or not at all (e.g. due
    to grouping). Therefore, a shot has 0-many ThumbnailImages.
    """
    def __init__(self):
        # Image Display
        self.id_image = None  # A Blender ID Image, which can be rendered by bgl.
        self.pos = (0, 0)  # Position in px where the image should be displayed within a region.
        # Represented Object (shot/asset)
        self.shot_idx = -1
        # Grouped View
        self.group_idx = -1
        self.pos_in_group = -1
        # ??
        self.name = ""


class ThumbnailGroup:
    """UI data for a container of thumbnails, with a drawable name and a colorful rectangle."""
    def __init__(self):
        # Group Title
        self.name = ""
        self.name_pos = (0, 0)
        # Colorful Rectangle
        self.color = (0, 0, 0, 1)
        self.color_rect = (0, 0, 0, 0)
        # Contained Thumbnails
        self.shot_ids = []
        self.shot_rows = 0
        # Represented Object (grouping criteria)
        self.scene_uuid = ""


# View Data #######################################################################################

# Thumbnail Rendering
thumbnail_images = []  # All the loaded thumbnails for an edit.
thumbnail_size = (0, 0)  # The size in px at which the thumbnails should be displayed.
original_image_size = (0, 0)
thumbnail_draw_region = (0, 0, 0, 0)  # Rectangle inside a Blender region where the thumbnails draw

# Grouped View
thumbnail_groups = []
summary_text = ""

# State
hovered_thumbnail_idx = -1
group_by_scene_prev = False


# Drawing Thumbnail Images ########################################################################

def calculate_thumbnail_draw_region():

    # Get size of the region containing the thumbnails.
    region = bpy.context.region
    total_available_w = region.width
    total_available_h = region.height

    start_w = 0  # If the tools side panel is open, the thumbnails must be shifted to the right

    # If the header and side panels render on top of the region, discount their size.
    # The thumbnails should not be occluded by the UI, even if set to transparent.
    system_prefs = bpy.context.preferences.system
    transparent_regions = False  # system_prefs.use_region_overlap
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

    # Ensure there are no cached thumbnails
    thumbnail_images.clear()

    addon_prefs = bpy.context.preferences.addons[package_name].preferences
    folder_name = addon_prefs.edit_shots_folder

    try:
        for filename in os.listdir(folder_name):
            file_basename = filename.split('.')[0]
            # Avoid names that don't have the naming convention '123.jpg', with 123 = frame number.
            # This is likely to happen with .DS_Store files.
            if not file_basename.isdigit():
                continue

            img = ThumbnailImage()
            img.id_image = load_image(
                filename,
                dirname=folder_name,
                place_holder=False,
                recursive=False,
                ncase_cmp=True,
                convert_callback=None,
                verbose=False,
                relpath=None,
                check_existing=True,
                force_reload=False,
            )
            thumbnail_images.append(img)
            img.name = int(file_basename)
    except FileNotFoundError:
        # self.report({'ERROR'}, # Need an operator
        log.warning(f"Reading thumbnail images from '{folder_name}' failed: folder does not exist.")

    thumbnail_images.sort(key=lambda x: x.name, reverse=False)

    for i, img in enumerate(thumbnail_images):
        img.shot_idx = i
        if img.id_image.gl_load():
            raise Exception()

    # Cache the thumbnails resolution on disk, which should be the same for all of them.
    global original_image_size
    try:
        original_image_size = thumbnail_images[0].id_image.size
    except (ValueError, IndexError):
        original_image_size = (100, 100)

    log.info(f"(Re)loaded {len(thumbnail_images)} thumbnail images from disk.")


def fit_thumbnails_in_region():
    """Calculate the thumbnails' size and where to render each one, so they fit the given region"""

    # If there are no images to fit, we're done!
    edit_breakdown = bpy.context.scene.edit_breakdown
    shots = edit_breakdown.shots
    if not shots or not thumbnail_images:
        return

    log.debug("------Fit Images-------------------")

    if edit_breakdown.view_grouped_by_scene and edit_breakdown.scenes:
        fit_thumbnails_in_group()
    else:
        thumbnail_groups.clear()
        fit_thumbnails_in_grid()


def fit_thumbnails_in_grid():
    """Calculate the thumbnails' size and where to render each one so that they fit the given region

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
    min_margin = 40  # Arbitrary 20px minimum for the top,bottom,left and right margins
    available_w = total_available_w - total_spacing[0]
    available_h = total_available_h - total_spacing[1]
    max_thumb_size = (total_available_w - min_margin, total_available_h - min_margin)

    # Get the original size and aspect ratio of the images.
    # Assume all images in the edit have the same aspect ratio.
    original_image_w = original_image_size[0]
    original_image_h = original_image_size[1]
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
    log.debug(f"Scale factor: {scale_factor:.3f}")

    thumbnail_size = (
        original_image_w * scale_factor,
        original_image_h * scale_factor,
    )

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
    log.debug(f"Reduced scale factor: {scale_factor:.3f}")

    thumbnail_size = (
        original_image_w * scale_factor,
        original_image_h * scale_factor,
    )

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

        return margin, spacing

    log.debug(f"X")
    space_w = calculate_spacing(total_available_w, thumbnail_size[0], num_images_per_row)
    log.debug(f"Y")
    space_h = calculate_spacing(total_available_h, thumbnail_size[1], num_images_per_col)

    margins = (space_w[0], space_h[0])
    spacing = (space_w[1], space_h[1])

    # Set the position of each thumbnail
    start_pos_x = start_w + margins[0]
    start_pos_y = total_available_h - thumbnail_size[1] - margins[1]
    last_start_pos_x = start_w + math.ceil(
        margins[0] + (num_images_per_row - 1) * (thumbnail_size[0] + spacing[0])
    )

    for img in thumbnail_images:
        img.pos = (start_pos_x, start_pos_y)
        start_pos_x += thumbnail_size[0] + spacing[0]
        # Next row
        if start_pos_x > last_start_pos_x:
            start_pos_x = start_w + margins[0]
            start_pos_y -= thumbnail_size[1] + spacing[1]


def fit_thumbnails_in_group():
    """ """

    edit_breakdown = bpy.context.scene.edit_breakdown
    shots = edit_breakdown.shots
    edit_scenes = edit_breakdown.scenes
    num_images = len(thumbnail_images)

    thumbnail_groups.clear()

    # Create the thumbnail groups
    for i, eb_scene in enumerate(edit_scenes):
        group = ThumbnailGroup()
        group.name = eb_scene.name
        group.scene_uuid = eb_scene.uuid
        group.color = eb_scene.color
        thumbnail_groups.append(group)

    # Assign shots to groups
    for shot_idx, shot in enumerate(shots):

        scene_idx = 0
        for i, eb_scene in enumerate(edit_scenes):
            if eb_scene.uuid == shot.scene_uuid:
                scene_idx = i
                break
        group = thumbnail_groups[scene_idx]
        if group:
            group.shot_ids.append(shot_idx)
            thumbnail_images[shot_idx].group_idx = scene_idx
            thumbnail_images[shot_idx].pos_in_group = len(group.shot_ids) - 1

    # Determine positions based on numbers

    global thumbnail_size

    # Get scalable constants, based on interface scale and dpi.
    system_prefs = bpy.context.preferences.system
    font_size = 12 * system_prefs.ui_scale
    bar_width = 12 * system_prefs.ui_scale

    # Get size of the region containing the thumbnails.
    total_available_w = thumbnail_draw_region[2]
    total_available_h = thumbnail_draw_region[3]
    start_w = thumbnail_draw_region[0]

    log.debug(f"Region w:{total_available_w} h:{total_available_h}")

    # Get the available size, discounting white space size.
    group_titles_height = round(22 * system_prefs.ui_scale)
    min_margin = round(40 * system_prefs.ui_scale)  # Arbitrary 20px minimum for the top,bottom,left and right margins.
    total_spacing = (round(150 * system_prefs.ui_scale), round(40 * system_prefs.ui_scale))
    available_w = total_available_w - total_spacing[0]
    available_h = total_available_h - total_spacing[1] - group_titles_height * len(thumbnail_groups)
    max_thumb_size = (
        total_available_w - min_margin,
        total_available_h - min_margin,
    )

    # Get the original size and aspect ratio of the images.
    # Assume all images in the edit have the same aspect ratio.
    original_image_w = original_image_size[0]
    original_image_h = original_image_size[1]
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
    log.debug(f"Scale factor: {scale_factor:.3f}")
    thumbnail_size = (
        original_image_w * scale_factor,
        original_image_h * scale_factor,
    )

    num_images_per_row = math.ceil(available_w / thumbnail_size[0])
    num_images_per_col = math.ceil(num_images / num_images_per_row)
    log.debug(f"Thumbnail width  {thumbnail_size[0]:.3f}px, # per row: {num_images_per_row:.3f}")
    log.debug(f"Thumbnail height {thumbnail_size[1]:.3f}px, # per col: {num_images_per_col:.3f}")

    num_images_per_col = 0
    for group in thumbnail_groups:
        rows = math.ceil(len(group.shot_ids) / num_images_per_row)
        group.shot_rows = rows
        num_images_per_col += rows
    log.debug(
        f"num_images_per_col {num_images_per_col} space "
        f"{num_images_per_col * thumbnail_size[1]} > available space {available_h} ? "
    )

    l = 0
    while num_images_per_col * thumbnail_size[1] > available_h and l < 10:
        l += 1
        num_images_per_row += 1

        num_images_per_col = 0
        for group in thumbnail_groups:
            rows = math.ceil(len(group.shot_ids) / num_images_per_row)
            group.shot_rows = rows
            num_images_per_col += rows

        log.debug(f"[row/col] {num_images_per_row} {num_images_per_col} ? ")
        log.debug(
            f"num_images_per_col {num_images_per_col} space "
            f"{num_images_per_col * thumbnail_size[1]} > available space {available_h} ? "
        )

    log.debug(f"Thumbnail width  {thumbnail_size[0]:.3f}px, # per row: {num_images_per_row:.3f}")
    log.debug(f"Thumbnail height {thumbnail_size[1]:.3f}px, # per col: {num_images_per_col:.3f}")

    # Make sure that both a row and a column of images at the current scale will fit.
    # It is possible that, with few images and a region aspect ratio that is very different from
    # the images', there is enough area, but not enough length in one direction.
    # In that case, reduce the thumbnail size further.
    if original_image_w * scale_factor * num_images_per_row > max_thumb_size[0]:
        scale_factor = max_thumb_size[0] / (original_image_w * num_images_per_row)
    # if original_image_h * scale_factor * num_images_per_col > max_thumb_size[1]:
    #    scale_factor = max_thumb_size[1] / (original_image_h * num_images_per_col)
    log.debug(f"Reduced scale factor: {scale_factor:.3f}")

    thumbnail_size = (
        original_image_w * scale_factor,
        original_image_h * scale_factor,
    )

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

        return margin, spacing

    log.debug(f"X")
    available_space = total_available_w - thumbnail_size[0] * num_images_per_row
    space_w = calculate_spacing(total_available_w, available_space, num_images_per_row)
    log.debug(f"Y")
    available_space = (
        total_available_h
        - thumbnail_size[1] * num_images_per_col
        - group_titles_height * len(thumbnail_groups)
    )
    space_h = calculate_spacing(total_available_h, available_space, num_images_per_col)

    margins = (space_w[0], space_h[0])
    spacing = (space_w[1], space_h[1])

    start_pos_x = start_w + margins[0]
    start_pos_y_title = total_available_h - margins[1] - group_titles_height
    start_pos_y_thumb = thumbnail_size[1] + 6 * system_prefs.ui_scale
    thumbnail_step_x = thumbnail_size[0] + spacing[0]
    thumbnail_step_y = thumbnail_size[1] + spacing[1]
    last_start_pos_x = start_w + math.ceil(
        margins[0] + (num_images_per_row - 1) * (thumbnail_size[0] + spacing[0])
    )

    # Set the position of each group title
    for group_idx, group in enumerate(thumbnail_groups):
        group.name_pos = (start_pos_x, start_pos_y_title)
        start_pos_y_title -= group_titles_height + thumbnail_step_y * group.shot_rows

        duration_s = 0
        for shot_id in group.shot_ids:
            duration_s += shots[shot_id].duration_seconds
        group.name += f" (shots: {len(group.shot_ids)}, {duration_s:.1f}s)"

        title_font_size = font_size
        bar_height = thumbnail_step_y * group.shot_rows - spacing[1]/2 + title_font_size
        title_top = group.name_pos[1] + font_size
        group.color_rect = (start_pos_x-bar_width, title_top - bar_height, bar_width*0.5, bar_height)

    # Set the position of each thumbnail
    for img in thumbnail_images:
        row = int(img.pos_in_group / num_images_per_row)
        col = img.pos_in_group % num_images_per_row
        group_y = thumbnail_groups[img.group_idx].name_pos[1]
        img.pos = (
            start_pos_x + thumbnail_step_x * col,
            group_y - start_pos_y_thumb - thumbnail_step_y * row,
        )
        # print(f"{img.name} : [group/pos]({img.group_idx},{img.pos_in_group})
        # [row/col]({row},{col}) pos({img.pos[0]:.2f},{img.pos[1]:.2f})")


def is_thumbnail_view():
    """True if the current space has the edit breakdown view enabled.

    Note: I found no way of making a new space or mode toggle for this
    add-on, therefore, I'm hijacking the Display Frames toggle as it only
    seems to be used in Sequencer view (not Preview view).
    This is less than ideal as it takes existing data to have additional meaning.
    TODO: whenever possible, switch the thumbnail view to its own editor
    space or add a toggle to the region/area/space if they get support
    for ID properties."""
    return bpy.context.space_data.show_frames


def draw_edit_thumbnails():
    """Render the edit thumbnails"""

    if not is_thumbnail_view():
        return

    # Early out: nothing to render on an empty edit.
    # Users need to press 'Sync' to generate EB shots and thumbnails.
    shots = bpy.context.scene.edit_breakdown.shots
    if not shots:
        return

    # Load the images the first time they're needed.
    if not thumbnail_images:
        load_edit_thumbnails()

    # Detect if Blender deleted the thumbnail images, which seems to happen at random during undo.
    if thumbnail_images:  # There might be no images in an empty edit.
        # Access a Blender image, which will trigger an exception if Blender deleted it.
        try:
            # noinspection PyStatementEffect
            thumbnail_images[0].id_image.bindcode
        except ReferenceError:  # StructRNA of type Image has been removed
            # Reload the images from disk and layout the new instances in the current space.
            load_edit_thumbnails()
            fit_thumbnails_in_region()

    # Recalculate the thumbnail positions when the available drawing space changes.
    prev_draw_region = thumbnail_draw_region
    calculate_thumbnail_draw_region()
    if prev_draw_region != thumbnail_draw_region:
        fit_thumbnails_in_region()

    # Recalculate thumbnail positions if the grouping setting changes
    global group_by_scene_prev
    group_by_scene = bpy.context.scene.edit_breakdown.view_grouped_by_scene
    if group_by_scene_prev != group_by_scene:
        group_by_scene_prev = group_by_scene
        fit_thumbnails_in_region()

    # If the resulting layout makes the images too small, skip rendering.
    if thumbnail_size[0] <= 5 or thumbnail_size[1] <= 5:
        return

    if group_by_scene:
        font_id = 0  # Default font.
        system_prefs = bpy.context.preferences.system
        font_size = 12 * system_prefs.ui_scale
        blf.size(font_id, font_size)
        blf.color(font_id, 0.9, 0.9, 0.9, 1.0)
        for group in thumbnail_groups:
            blf.position(font_id, group.name_pos[0], group.name_pos[1], 0)
            blf.draw(font_id, group.name)
            draw_utils.draw_boolean_tag(group.color_rect[0:2], group.color_rect[2:4], group.color)

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

        return base_color[0], base_color[1], base_color[2], alpha

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
                    operator_props = active_tool.operator_properties("edit_breakdown.thumbnail_tag")
                    active_enum_item = int(operator_props.tag_enum_option)
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

    # Early out in case of an empty edit, or if the thumbnails failed to generate.
    # Thumbnails should match the existing shots edit breakdown data from the last sync,
    # but if for some reason they don't (e.g. blend file came from another workstation and this one
    # doesn't have disk space / permissions / wtv to render the thumbnails), then it doesn't
    # help to have additional errors trying to draw overlays for the thumbnails.
    if not thumbnail_images:
        return

    # Draw property values from the Tag Tool on top of each thumbnail.
    draw_tool_active_tag()

    # Draw mouseover highlight.
    if hovered_thumbnail_idx != -1:
        hovered_thumbnail = thumbnail_images[hovered_thumbnail_idx]
        draw_utils.draw_hover_highlight(hovered_thumbnail.pos, thumbnail_size)

    # Draw selection highlight.
    active_selected_thumbnail_idx = bpy.context.scene.edit_breakdown.selected_shot_idx
    if active_selected_thumbnail_idx != -1:
        active_selected_thumbnail = thumbnail_images[active_selected_thumbnail_idx]
        size = (thumbnail_size[0] + 2, thumbnail_size[1] + 2)
        pos = (
            active_selected_thumbnail.pos[0] - 1,
            active_selected_thumbnail.pos[1] - 1,
        )
        draw_utils.draw_selected_frame(pos, size)


# Add-on Registration #############################################################################

draw_handles = []
space = bpy.types.SpaceSequenceEditor


def register():

    draw_handles.append(space.draw_handler_add(draw_background, (), 'PREVIEW', 'POST_PIXEL'))
    draw_handles.append(space.draw_handler_add(draw_edit_thumbnails, (), 'PREVIEW', 'POST_PIXEL'))
    draw_handles.append(space.draw_handler_add(draw_overlay, (), 'PREVIEW', 'POST_PIXEL'))


def unregister():

    for handle in reversed(draw_handles):
        space.draw_handler_remove(handle, 'PREVIEW')
