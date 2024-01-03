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

import contextlib
import csv
import io
import logging
import math
import pathlib
import time

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty

from .. import data
from .. import tools
from .. import view

package_name = pathlib.Path(__file__).parent.parent.name
log = logging.getLogger(__name__)


def get_thumbnail_frame(strip):
    strip_mid_frame = math.floor(strip.frame_final_duration / 2)
    return strip.frame_final_start + strip_mid_frame


class SEQUENCER_OT_generate_edit_breakdown_thumbnails(Operator):
    bl_idname = "edit_breakdown.generate_edit_breakdown_thumbnails"
    bl_label = "Generate Edit Breakdown Thumbnails"
    bl_description = "Refresh thumbnail images on disk"
    bl_options = {'REGISTER'}

    @contextlib.contextmanager
    def override_render_settings(self, context, thumbnail_width=256):
        """Overrides the render settings for thumbnail size in a 'with' block scope."""

        rd = context.scene.render

        # Remember current render settings in order to restore them later.
        orig_percentage = rd.resolution_percentage
        orig_file_format = rd.image_settings.file_format
        orig_quality = rd.image_settings.quality

        try:
            # Set the render settings to thumbnail size.
            # Update resolution % instead of the actual resolution to scale text strips properly.
            rd.resolution_percentage = round(thumbnail_width * 100 / rd.resolution_x)
            rd.image_settings.file_format = 'JPEG'
            rd.image_settings.quality = 80
            yield
        finally:
            # Return the render settings to normal.
            rd.resolution_percentage = orig_percentage
            rd.image_settings.file_format = orig_file_format
            rd.image_settings.quality = orig_quality

    def save_render(self, datablock, file_name):
        """Save the current render image to disk"""

        addon_prefs = bpy.context.preferences.addons[package_name].preferences
        folder_name = addon_prefs.edit_shots_folder

        # Ensure folder exists
        folder_path = pathlib.Path(folder_name)
        folder_path.mkdir(parents=True, exist_ok=True)

        path = folder_path.joinpath(file_name)
        datablock.save_render(str(path))

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action.

        (Re)create the thumbnail images from the current edit strips.
        """

        log.info("Creating thumbnails...")
        time_start = time.time()

        scene = context.scene
        strips = scene.sequence_editor.sequences
        eb_strips = [s for s in strips if s.use_for_edit_breakdown]

        # Clear the previous runtime data.
        view.thumbnail_images.clear()
        view.thumbnail_size = (0, 0)
        view.hovered_thumbnail_idx = -1

        # Ensure the thumbnails folder exists and clear old thumbnails.
        addon_prefs = bpy.context.preferences.addons[package_name].preferences
        folder_name = addon_prefs.edit_shots_folder
        folder_path = pathlib.Path(folder_name)
        folder_path.mkdir(parents=True, exist_ok=True)
        for path in folder_path.iterdir():
            if path.suffix == ".jpg":
                path.unlink()

        # Render a thumbnail to disk per shot.
        with self.override_render_settings(context):
            for strip in eb_strips:
                scene.frame_current = get_thumbnail_frame(strip)
                bpy.ops.render.render()
                file_name = f'{str(scene.frame_current)}.jpg'
                self.save_render(bpy.data.images['Render Result'], file_name)
        log.info(f"Thumbnails generated in {(time.time() - time_start):.2f}s")

        # Update the thumbnails view
        view.load_edit_thumbnails()

        # Position the images according to the available space.
        view.fit_thumbnails_in_region()

        return {'FINISHED'}


class SEQUENCER_OT_sync_edit_breakdown(Operator):
    bl_idname = "edit_breakdown.sync_edit_breakdown"
    bl_label = "Sync Edit Breakdown"
    bl_description = "Ensure the edit breakdown is up-to-date with the edit"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action.

        Recreate the edit breakdown data based on the current edit.
        """

        log.info("Syncing sequencer strips to thumbnails and shot data...")

        scene = context.scene
        sequence_ed = scene.sequence_editor
        strips = sequence_ed.sequences
        eb_strips = [s for s in strips if s.use_for_edit_breakdown]
        shots = scene.edit_breakdown.shots

        # Load data from the sequence strips marked for use in the edit breakdown
        # Match existing strips and existing shots
        log.debug(f"Syncing {len(eb_strips)} strips -> {len(shots)} shots")

        # Ensure every strip has a shot
        for strip in eb_strips:
            associated_shot = next((s for s in shots if strip.name == s.strip_name), None)
            if not associated_shot:
                # Found a strip without associated shot? Create shot!
                log.debug(f"Creating new shot for strip {strip.name}")
                new_shot = shots.add()

                new_shot.name = strip.name
                new_shot.frame_start = int(strip.frame_final_start)
                new_shot.frame_count = int(strip.frame_final_end - strip.frame_final_start)

                # Associate the shot with the sequence by name
                new_shot.strip_name = strip.name

        # Update all shots with the associated strip data.
        # Delete shots that no longer match a strip.
        i = len(shots)
        for shot in reversed(shots):
            i -= 1
            strip_match = next((strip for strip in eb_strips if strip.name == shot.strip_name), None)
            if strip_match:
                # Update data.
                log.debug(f"Update shot info {i} - {shot.name}")
                shot.frame_start = int(strip_match.frame_final_start)
                shot.frame_count = int(strip_match.frame_final_end - strip_match.frame_final_start)
                shot.thumbnail_file = f'{str(get_thumbnail_frame(strip_match))}.jpg'
            else:
                log.debug(f"Deleting shot {i} - {shot.name}")
                shots.remove(i)

        # Sort shots per frame number. (Insertion Sort)
        for i in range(1, len(shots)):  # Start at 1, because 0 is trivially sorted.
            value_being_sorted = shots[i].frame_start
            # Shuffle 'value_being_sorted' from right-to-left on the sorted part
            # of the array, until it reaches its place
            insert_pos = i - 1
            while insert_pos >= 0 and shots[insert_pos].frame_start > value_being_sorted:
                shots.move(insert_pos, insert_pos + 1)
                insert_pos -= 1

        # Update the thumbnails.
        bpy.ops.edit_breakdown.generate_edit_breakdown_thumbnails()
        tools.update_selected_shot(scene)

        return {'FINISHED'}


class SEQUENCER_OT_copy_edit_breakdown_as_csv(Operator):
    bl_idname = "edit_breakdown.copy_edit_breakdown_as_csv"
    bl_label = "Copy Edit Breakdown as CSV"
    bl_description = "Copy Edit Breakdown data as CSV to the clipboard"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action."""

        log.info('Saving CSV to clipboard')
        shots = context.scene.edit_breakdown.shots

        # Create shot list that becomes a CSV, starting with the header
        shots_for_csv = [data.SEQUENCER_EditBreakdown_Shot.get_csv_export_header()]
        # Push each shot in the list
        for shot in shots:
            shots_for_csv.append(shot.get_csv_export_values())

        # Write the CSV in memory
        outbuf = io.StringIO()
        outcsv = csv.writer(outbuf)
        outcsv.writerows(shots_for_csv)

        # Push the CSV to the clipboard
        bpy.context.window_manager.clipboard = outbuf.getvalue()

        return {'FINISHED'}


class SEQUENCER_OT_use_strip_in_edit_breakdown(Operator):
    bl_idname = "edit_breakdown.use_strip_in_edit_breakdown"
    bl_label = "Use Strip in Edit Breakdown"
    bl_description = "Register the currently selected strip(s) for use in the Edit Breakdown"
    bl_options = {'REGISTER', 'UNDO'}

    should_add: BoolProperty(
        name="Add",
        description="Add the strip(s) to the Edit Breakdown if true, otherwise remove",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        # This operator is available only in the sequencer area of the sequence editor.
        is_sequence_strips_area = (
            context.space_data.type == 'SEQUENCE_EDITOR'
            and (context.space_data.view_type == 'SEQUENCER' or
                 context.space_data.view_type == 'SEQUENCER_PREVIEW')
        )
        active_strip = context.scene.sequence_editor.active_strip
        has_at_least_one_selected_strip = active_strip and active_strip.select
        return is_sequence_strips_area and has_at_least_one_selected_strip

    def execute(self, context):
        """Called to finish this operator's action."""

        strips = context.scene.sequence_editor.sequences

        for s in strips:
            if s.select:
                s.use_for_edit_breakdown = self.should_add
                # Assign a new color to clearly signal a change in the strip.
                s.color = (0.43, 0.30, 0.55)
                # Set as fully transparent/opaque to not interfere with the edit.
                s.blend_type = 'ALPHA_OVER'
                s.blend_alpha = float(not self.should_add)

        return {'FINISHED'}


def strip_menu_draw(self, context):
    if context.space_data.view_type == 'PREVIEW':
        return

    layout = self.layout
    layout.separator()
    layout.operator("edit_breakdown.use_strip_in_edit_breakdown", text="Add to Edit Breakdown")
    layout.operator("edit_breakdown.use_strip_in_edit_breakdown",
                    text="Remove from Edit Breakdown").should_add = False


classes = (
    SEQUENCER_OT_generate_edit_breakdown_thumbnails,
    SEQUENCER_OT_sync_edit_breakdown,
    SEQUENCER_OT_copy_edit_breakdown_as_csv,
    SEQUENCER_OT_use_strip_in_edit_breakdown,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.SEQUENCER_MT_strip.append(strip_menu_draw)


def unregister():

    bpy.types.SEQUENCER_MT_strip.remove(strip_menu_draw)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
