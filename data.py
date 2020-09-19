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

import datetime
import logging

import bpy
from bpy.types import (
    AddonPreferences,
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

from . import view

log = logging.getLogger(__name__)


# Settings ########################################################################################


class SEQUENCER_EditBreakdown_Preferences(AddonPreferences):
    bl_idname = "edit_breakdown"

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



# Data ############################################################################################

characters = [
    ("a", "Alice", ""),
    ("b", "Bob", ""),
]


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
    frame_count: IntProperty(
        name="Frame Count",
        description="Number of frames in this shot",
        default=0,
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
    has_character: EnumProperty(
        name="Characters",
        description="Which characters are present in this shot",
        items=characters,
        options={'ENUM_FLAG'},
    )

    @property
    def duration_seconds(self):
        """The duration of this shot, in seconds"""
        fps = bpy.context.scene.render.fps
        return round(self.frame_count/fps, 1)

    @property
    def timestamp(self):
        """The time at which this shot starts in the edit"""
        fps = bpy.context.scene.render.fps
        start_frame = max(0, self.frame_start - bpy.context.scene.frame_start)
        seconds_to_start = round(start_frame/fps)
        return str(datetime.timedelta(seconds=seconds_to_start))

    @property
    def character_count(self):
        """The total number of characters present on this shot"""
        count = 0
        characters = self.has_character
        prop_rna = self.rna_type.properties['has_character']

        for item in prop_rna.enum_items:
            if item.identifier in characters:
                count += 1

        return count


    @classmethod
    def get_attributes(cls):
        # TODO Figure out how to get attributes from the class
        return ['shot_name', 'frame_start', 'timestamp', 'duration_seconds' ,'character_count',
                'animation_complexity', 'has_fx', 'has_crowd']

    def as_list(self):
        # TODO Generate this list based on get_attributes(). Using getattr does not work.
        return [self.shot_name, self.frame_start, self.timestamp, self.duration_seconds,
                self.character_count, self.animation_complexity,
                int(self.has_fx), int(self.has_crowd)]


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
        col.label(text=f"Frames: {total_frames}")
        fps = context.scene.render.fps
        total_seconds = round(total_frames/fps)
        duration_str = str(datetime.timedelta(seconds=total_seconds))
        col.label(text=f"Duration: {duration_str}")


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

        col.label(text=f"Timestamp: {selected_shot.timestamp}")
        total_seconds = round(selected_shot.duration_seconds)
        m, s = divmod(total_seconds, 60)
        col.label(text=f"Duration: {m:02d}:{s:02d}")

        col.prop(selected_shot, "animation_complexity")
        col.prop(selected_shot, "has_crowd")
        col.prop(selected_shot, "has_fx")
        col.prop(selected_shot, "has_character")
        col.label(text=f"Character Count: {selected_shot.character_count}")



# Add-on Registration #############################################################################

classes = (
    SEQUENCER_EditBreakdown_Preferences,
    SEQUENCER_EditBreakdown_Shot,
    SEQUENCER_EditBreakdown_Data,
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


def unregister():

    del bpy.types.TimelineMarker.use_for_edit_breakdown
    del bpy.types.Scene.edit_breakdown

    for cls in classes:
        bpy.utils.unregister_class(cls)
