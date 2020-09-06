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

bl_info = {
    "name": "Edit Breakdown",
    "author": "Inês Almeida, Francesco Siddi",
    "version": (0, 1, 0),
    "blender": (2, 90, 0),
    "location": "Video Sequence Editor",
    "description": "Get insight on the complexity of an edit",
    "doc_url": "https://github.com/britalmeida/blender_addon_edit_breakdown",
    "category": "Sequencer",
}

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
    EnumProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

if "view" in locals():
    import importlib
    importlib.reload(draw_utils)
    importlib.reload(tools)
    importlib.reload(view)
else:
    from . import draw_utils
    from . import tools
    from . import view

log = logging.getLogger(__name__)


# Data ############################################################################################

class SEQUENCER_EditBreakdown_Shot(PropertyGroup):
    """Properties of a shot."""

    shot_name: StringProperty(name="Shot Name")
    frame_start: IntProperty(name="Frame")
    duration: IntProperty(name="Duration", description="Number of frames in this shot")
    character_count: IntProperty(name="Character Count")
    animation_complexity: EnumProperty(name="Anim Complexity",
        items=[('1', '1', '1'), ('2', '2', '2'), ('3', '3', '3'), ('4', '4', '4'), ('5', '5', '5')])
    has_fx: BoolProperty(name="Has Effects")
    has_crowd: BoolProperty(name="Has Crowd")


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

    total_shot_duration = 0


# Operators #######################################################################################

class SEQUENCER_OT_sync_edit_breakdown(Operator):
    bl_idname = "sequencer.sync_edit_breakdown"
    bl_label = "Sync Edit Breakdown"
    bl_description = "Ensure the edit breakdown is up-to-date with the edit"
    bl_options = {'REGISTER'}

    def calculate_shots_duration(self, context):
        shots = context.scene.edit_breakdown.shots

        total_duration_frames = 0
        last_frame = max(context.scene.frame_end, shots[-1].frame_start)
        for shot in reversed(shots):
            shot.duration = last_frame - shot.frame_start
            last_frame = shot.frame_start
            total_duration_frames += shot.duration

        context.scene.edit_breakdown.total_shot_duration = total_duration_frames
        # WIP
        fps = 30
        total_seconds = total_duration_frames/fps
        log.info(f"Edit has {total_seconds:.1f} seconds, with a total of {total_duration_frames} frames")

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action.

        Recreate the edit breakdown data based on the current edit.
        """

        log.debug("sync_edit_breakdown: execute")

        sequence_ed = context.scene.sequence_editor
        addon_prefs = context.preferences.addons[__name__].preferences
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

        total_duration_frames = edit_breakdown.total_shot_duration
        total_duration_frames = 14189
        # WIP
        fps = 30
        total_seconds = total_duration_frames/fps
        col.label(text=f"Frames: {total_duration_frames}")
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
        sub.prop(selected_shot, "duration", text="Num Frames")
        # WIP
        fps = 30
        total_seconds = selected_shot.duration/fps
        col.label(text=f"Duration: {total_seconds/60:.1f} min ({total_seconds:.0f} seconds)")
        col.prop(selected_shot, "animation_complexity")
        col.prop(selected_shot, "character_count")
        col.prop(selected_shot, "has_crowd")
        col.prop(selected_shot, "has_fx")


def draw_sequencer_header_extension(self, context):
    layout = self.layout
    layout.operator("sequencer.sync_edit_breakdown", icon='SEQ_SPLITVIEW') #FILE_REFRESH



# Add-on Registration #############################################################################

classes = (
    SEQUENCER_EditBreakdown_Shot,
    SEQUENCER_EditBreakdown_Data,
    SEQUENCER_OT_sync_edit_breakdown,
    SEQUENCER_PT_edit_breakdown_overview,
    SEQUENCER_PT_edit_breakdown_shot,
)

draw_handles = []


def register():
    log.info("------Registering Edit Breakdown-------------------")

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

    tools.register()
    view.register()

    log.info("------Done Registering-----------------------------")


def unregister():

    log.info("------Unregistering Edit Breakdown-----------------")

    tools.unregister()
    view.unregister()

    bpy.types.SEQUENCER_HT_header.remove(draw_sequencer_header_extension)

    del bpy.types.TimelineMarker.use_for_edit_breakdown
    del bpy.types.Scene.edit_breakdown

    for cls in classes:
        bpy.utils.unregister_class(cls)

    log.info("------Done Unregistering---------------------------")


if __name__ == "__main__":
    register()
