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

import csv
import io
import logging

import bpy
from bpy.types import Operator

from . import view

log = logging.getLogger(__name__)


# Operators #######################################################################################

class SEQUENCER_OT_sync_edit_breakdown(Operator):
    bl_idname = "sequencer.sync_edit_breakdown"
    bl_label = "Sync Edit Breakdown"
    bl_description = "Ensure the edit breakdown is up-to-date with the edit"
    bl_options = {'REGISTER'}

    def calculate_shots_duration(self, context):
        shots = context.scene.edit_breakdown.shots

        accumulated_total_frames = 0
        last_frame = max(context.scene.frame_end, shots[-1].frame_start)
        for shot in reversed(shots):
            shot.duration = last_frame - shot.frame_start
            last_frame = shot.frame_start
            accumulated_total_frames += shot.duration

        scene = context.scene
        scene_total_frames = scene.frame_end - scene.frame_start
        if scene_total_frames != accumulated_total_frames:
            self.report({'WARNING'},
                "The frame range does not match the sequencer strips. Edit Breakdown will report incorrect duration")

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action.

        Recreate the edit breakdown data based on the current edit.
        """

        log.debug("sync_edit_breakdown: execute")

        sequence_ed = context.scene.sequence_editor
        shots = context.scene.edit_breakdown.shots

        # Clear the previous breakdown data
        view.thumbnail_images.clear()
        shots.clear()

        # Load data from the sequence markers marked for use in the edit breakdown
        def WIP_fake_behaviour():
            view.load_edit_thumbnails()
            for img in view.thumbnail_images:
                new_shot = shots.add()
                new_shot.shot_name = str(img.name)
                new_shot.frame_start = img.name
        WIP_fake_behaviour()

        self.calculate_shots_duration(context)

        # Position the images according to the available space.
        view.fit_thumbnails_in_region()

        return {'FINISHED'}


class SEQUENCER_OT_copy_edit_breakdown_as_csv(Operator):
    bl_idname = "sequencer.copy_edit_breakdown_as_csv"
    bl_label = "Copy Edit Breakdown as CSV"
    bl_description = "Copy Edit Breakdown data as CSV in the clipboard"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action."""

        log.debug("copy_edit_breakdown_as_csv: execute")

        sequence_ed = context.scene.sequence_editor
        shots = context.scene.edit_breakdown.shots
        log.info('Saving CSV to clipboard')

        # Create shot list that becomes a CSV, starting with the header
        shots_for_csv = [SEQUENCER_EditBreakdown_Shot.get_attributes()]
        # Push each shot in the list
        for shot in shots:
            shots_for_csv.append(shot.as_list())

        # Write the CSV in memory
        outbuf = io.StringIO()
        outcsv = csv.writer(outbuf)
        outcsv.writerows(shots_for_csv)

        # Push the CSV to the clipboard
        bpy.context.window_manager.clipboard = outbuf.getvalue()

        return {'FINISHED'}



# UI ##############################################################################################

def draw_sequencer_header_extension(self, context):
    layout = self.layout
    layout.operator("sequencer.sync_edit_breakdown", icon='SEQ_SPLITVIEW') #FILE_REFRESH
    layout.operator("sequencer.copy_edit_breakdown_as_csv", icon='FILE')



# Add-on Registration #############################################################################

classes = (
    SEQUENCER_OT_sync_edit_breakdown,
    SEQUENCER_OT_copy_edit_breakdown_as_csv,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.SEQUENCER_HT_header.append(draw_sequencer_header_extension)


def unregister():

    bpy.types.SEQUENCER_HT_header.remove(draw_sequencer_header_extension)

    for cls in classes:
        bpy.utils.unregister_class(cls)
