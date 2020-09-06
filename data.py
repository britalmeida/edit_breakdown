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
from bpy.types import (
    Operator,
    Panel,
    PropertyGroup,
)
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from . import view

log = logging.getLogger(__name__)


# Data ############################################################################################

class SEQUENCER_EditBreakdown_Shot(PropertyGroup):
    """Properties of a shot."""

    shot_name: StringProperty(
        name="Shot Name",
        description="",
    )
    frame_start: IntProperty(
        name="Frame",
        description="",
    )
    duration: IntProperty(
        name="Duration",
        description="Number of frames in this shot",
        default=0,
    )
    character_count: IntProperty(
        name="Character Count",
        description="",
        default=0,
        min=0,
    )
    animation_complexity: IntProperty(
        name="Anim Complexity",
        description="",
        default=0,
        min=0,
        max=3,
    )
    has_fx: BoolProperty(
        name="Has Effects",
        description="",
        default=False,
    )
    has_crowd: BoolProperty(
        name="Has Crowd",
        description="",
        default=False,
    )

    @property
    def duration_seconds(self):
        fps = bpy.context.scene.render.fps
        return self.duration/fps

    @classmethod
    def get_attributes(cls):
        # TODO Figure out how to get attributes from the class
        return ['shot_name', 'frame_start', 'duration', 'character_count', 'animation_complexity',
                'has_fx', 'has_crowd']

    def as_list(self):
        # TODO Generate this list based on get_attributes(). Using getattr does not work.
        return [self.shot_name, self.frame_start, self.duration, self.character_count,
                self.animation_complexity, self.has_fx, self.has_crowd]


class SEQUENCER_EditBreakdown_Data(PropertyGroup):

    shots: CollectionProperty(
        type=SEQUENCER_EditBreakdown_Shot,
        name="Shots",
        description="Set of shots that form the edit",
    )

    selected_shot_idx : IntProperty(
        name="Selected Shot",
        description="The active selected shot (last selected, if any).",
        default=-1
    )

    @property
    def total_frames(self):
        """The total number of frames in the edit, according to the scene frame range."""
        scene = bpy.context.scene
        return scene.frame_end - scene.frame_start


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


class SEQUENCER_PT_edit_breakdown_overview(Panel):
    bl_label = "Overview"
    bl_category = "Edit Breakdown"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'IMAGE_EDITOR'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        edit_breakdown = context.scene.edit_breakdown

        col = layout.column()
        col.label(text=f"Shots: {len(edit_breakdown.shots)}")

        total_frames = edit_breakdown.total_frames
        fps = context.scene.render.fps
        total_seconds = total_frames/fps
        col.label(text=f"Frames: {total_frames}")
        col.label(text=f"Duration: {total_seconds/60:.1f} min ({total_seconds:.0f} seconds)")


class SEQUENCER_PT_edit_breakdown_shot(Panel):
    bl_label = "Shot"
    bl_category = "Edit Breakdown"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'IMAGE_EDITOR'

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        shots = context.scene.edit_breakdown.shots
        sel_idx = context.scene.edit_breakdown.selected_shot_idx

        if sel_idx < 0:
            col = layout.column()
            col.label(text=f"No shot selected")
            return

        selected_shot = shots[sel_idx]

        col = layout.column()
        col.prop(selected_shot, "shot_name")

        sub = col.column()
        sub.enabled = False
        sub.prop(selected_shot, "duration", text="Frame Count")
        total_seconds = selected_shot.duration_seconds
        col.label(text=f"Duration: {total_seconds:.1f} seconds")

        col.prop(selected_shot, "animation_complexity")
        col.prop(selected_shot, "character_count")
        col.prop(selected_shot, "has_crowd")
        col.prop(selected_shot, "has_fx")


def draw_sequencer_header_extension(self, context):
    layout = self.layout
    layout.operator("sequencer.sync_edit_breakdown", icon='SEQ_SPLITVIEW') #FILE_REFRESH
    layout.operator("sequencer.copy_edit_breakdown_as_csv", icon='FILE')



# Add-on Registration #############################################################################

classes = (
    SEQUENCER_EditBreakdown_Shot,
    SEQUENCER_EditBreakdown_Data,
    SEQUENCER_OT_sync_edit_breakdown,
    SEQUENCER_OT_copy_edit_breakdown_as_csv,
    SEQUENCER_PT_edit_breakdown_overview,
    SEQUENCER_PT_edit_breakdown_shot,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TimelineMarker.use_for_edit_breakdown = BoolProperty(
        name="Use For Edit Breakdown",
        default=True,
        description="If this marker should be included as a shot in the edit breakdown view",
    )

    bpy.types.Scene.edit_breakdown = PointerProperty(
        name="Edit Breakdown",
        type=SEQUENCER_EditBreakdown_Data,
        description="Shot data used by the Edit Breakdown add-on.",
    )

    bpy.types.SEQUENCER_HT_header.append(draw_sequencer_header_extension)


def unregister():

    bpy.types.SEQUENCER_HT_header.remove(draw_sequencer_header_extension)

    del bpy.types.TimelineMarker.use_for_edit_breakdown
    del bpy.types.Scene.edit_breakdown

    for cls in classes:
        bpy.utils.unregister_class(cls)
