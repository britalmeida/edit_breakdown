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
import pathlib
import logging
import time
import uuid

import bpy
from bpy.types import Operator

from .. import data
from .. import tools
from .. import view

log = logging.getLogger(__name__)


class SEQUENCER_OT_sync_edit_breakdown(Operator):
    bl_idname = "edit_breakdown.sync_edit_breakdown"
    bl_label = "Sync Edit Breakdown"
    bl_description = "Ensure the edit breakdown is up-to-date with the edit"
    bl_options = {'REGISTER', 'UNDO'}

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

        addon_prefs = bpy.context.preferences.addons['edit_breakdown'].preferences
        folder_name = addon_prefs.edit_shots_folder

        # Ensure folder exists
        folder_path = pathlib.Path(folder_name)
        folder_path.mkdir(parents=True, exist_ok=True)

        path = folder_path.joinpath(file_name)
        datablock.save_render(str(path))

    def calculate_shots_duration(self, context):
        scene = context.scene
        shots = scene.edit_breakdown.shots
        if not shots:
            return

        last_frame = max(scene.frame_end, shots[-1].frame_start)
        for shot in reversed(shots):
            shot.frame_count = last_frame - shot.frame_start
            last_frame = shot.frame_start

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action.

        Recreate the edit breakdown data based on the current edit.
        """

        log.info("Syncing edit markers to thumbnails and shot data...")
        time_start = time.time()

        scene = context.scene
        sequence_ed = scene.sequence_editor
        markers = scene.timeline_markers
        shots = scene.edit_breakdown.shots

        # Clear the previous runtime data.
        view.thumbnail_images.clear()
        view.thumbnail_size = (0, 0)
        view.hovered_thumbnail = None
        view.active_selected_thumbnail = None

        # Ensure the thumbnails folder exists and clear old thumbnails.
        addon_prefs = bpy.context.preferences.addons['edit_breakdown'].preferences
        folder_name = addon_prefs.edit_shots_folder
        folder_path = pathlib.Path(folder_name)
        folder_path.mkdir(parents=True, exist_ok=True)
        for path in folder_path.iterdir():
            if path.suffix == ".jpg":
                path.unlink()

        # Render a thumbnail to disk per each frame
        log.info("Creating thumbnails...")
        with self.override_render_settings(context):
            for m in markers:
                scene.frame_current = m.frame
                bpy.ops.render.render()
                file_name = f'{str(context.scene.frame_current)}.jpg'
                self.save_render(bpy.data.images['Render Result'], file_name)
        log.info(f"Thumbnails generated in {(time.time() - time_start):.2f}s")

        # Load data from the sequence markers marked for use in the edit breakdown
        # Match existing markers and existing shots
        log.debug(f"Syncing {len(markers)} markers -> {len(shots)} shots")

        # Ensure every marker has a shot
        for m in markers:
            associated_shot = 'uuid' in m.keys() and next(
                (s for s in shots if m['uuid'] == s.timeline_marker), None
            )
            if not associated_shot:
                # Found a marker without associated shot? Create shot!
                log.debug(f"Creating new shot for marker {m.name}")
                new_shot = shots.add()

                new_shot.name = m.name
                new_shot.frame_start = m.frame

                # Create a unique identifier to associate the marker and the shot.
                uuid_str = uuid.uuid4().hex
                new_shot.timeline_marker = uuid_str
                m['uuid'] = uuid_str

        # Update all shots with the associated marker data.
        # Delete shots that no longer match a marker.
        i = len(shots)
        for shot in reversed(shots):
            i -= 1
            marker_match = next((m for m in markers if m['uuid'] == shot.timeline_marker), None)
            if marker_match:
                # Update data.
                log.debug(f"Update shot info {i} - {shot.name}")
                shot.frame_start = marker_match.frame
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

        # Calculate frame count information for each shot.
        self.calculate_shots_duration(context)

        # Update the thumbnails view
        view.load_edit_thumbnails()
        tools.update_selected_shot(scene)

        # Position the images according to the available space.
        view.fit_thumbnails_in_region()

        log.info(f"Syncing done in {(time.time() - time_start):.2f}s")
        return {'FINISHED'}


class SEQUENCER_OT_copy_edit_breakdown_as_csv(Operator):
    bl_idname = "edit_breakdown.copy_edit_breakdown_as_csv"
    bl_label = "Copy Edit Breakdown as CSV"
    bl_description = "Copy Edit Breakdown data as CSV in the clipboard"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action."""

        log.info('Saving CSV to clipboard')
        sequence_ed = context.scene.sequence_editor
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


classes = (
    SEQUENCER_OT_sync_edit_breakdown,
    SEQUENCER_OT_copy_edit_breakdown_as_csv,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
