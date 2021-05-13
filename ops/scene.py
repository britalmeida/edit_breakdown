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

import uuid

import bpy
from bpy.props import EnumProperty
from bpy.types import Operator, Menu

from .. import utils
from .. import view


class SEQUENCER_OT_add_scene(Operator):
    bl_idname = "edit_breakdown.add_scene"
    bl_label = "Add Scene"
    bl_description = "Create a new scene for grouping shots"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        """Called to finish this operator's action."""

        edit_breakdown = context.scene.edit_breakdown
        edit_scenes = edit_breakdown.scenes

        # Create the new scene with a unique ID
        new_scene = edit_scenes.add()
        new_scene.uuid = uuid.uuid4().hex
        new_scene.name = utils.create_unique_name("Scene", edit_scenes)

        # Generate a random color
        new_scene.color = utils.get_random_pastel_color_rgb()

        # Select it.
        edit_breakdown.active_scene_idx = len(edit_scenes) - 1

        return {'FINISHED'}


class SEQUENCER_OT_del_scene(Operator):
    bl_idname = "edit_breakdown.del_scene"
    bl_label = "Delete Scene"
    bl_description = "Delete the scene from the edit breakdown, but not its associated shots"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        edit_breakdown = context.scene.edit_breakdown
        return 0 <= edit_breakdown.active_scene_idx < len(edit_breakdown.scenes)

    def execute(self, context):
        """Called to finish this operator's action."""

        edit_breakdown = context.scene.edit_breakdown
        edit_scenes = edit_breakdown.scenes

        # Unlink the scene.
        edit_scenes.remove(edit_breakdown.active_scene_idx)

        # Ensure the selected scene is within range.
        num_scenes = len(edit_scenes)
        if edit_breakdown.active_scene_idx > (num_scenes - 1) and num_scenes > 0:
            edit_breakdown.active_scene_idx = num_scenes - 1

        return {'FINISHED'}


class SEQUENCER_OT_del_scene_all(Operator):
    bl_idname = "edit_breakdown.del_scene_all"
    bl_label = "Delete All Scenes"
    bl_description = "Deletes all scenes from the edit breakdown, but not the associated shots"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.scene.edit_breakdown.scenes) > 1

    def execute(self, context):
        edit_breakdown = context.scene.edit_breakdown
        # Unlink the scene from all shots
        for shot in edit_breakdown.shots:
            shot.scene_uuid = ''
        # Delete all edit scenes
        edit_breakdown.scenes.clear()
        # Refresh the view in case it was grouped by scene
        view.fit_thumbnails_in_region()
        return {'FINISHED'}


class SEQUENCER_OT_move_scene(Operator):
    bl_idname = "edit_breakdown.scene_move"
    bl_label = "Move Scene in List"
    bl_description = "Move the active Edit Scene up/down the list"
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name="Move Direction",
        description="Direction to move the active scene: UP (default) or DOWN",
        items=[
            ('UP', "Up", "", -1),
            ('DOWN', "Down", "", 1),
        ],
        default='UP',
        options={'HIDDEN'},
    )

    @classmethod
    def poll(cls, context):
        return len(context.scene.edit_breakdown.scenes) > 1

    def execute(self, context):
        edit_breakdown = context.scene.edit_breakdown

        eb_scenes = edit_breakdown.scenes
        active_idx = edit_breakdown.active_scene_idx
        new_idx = active_idx + (-1 if self.direction == 'UP' else 1)

        if new_idx < 0 or new_idx >= len(eb_scenes):
            return {'FINISHED'}

        eb_scenes.move(active_idx, new_idx)
        edit_breakdown.active_scene_idx = new_idx

        return {'FINISHED'}


class SEQUENCER_MT_scenes_context_menu(Menu):
    bl_label = "Edit Scenes Specials"

    def draw(self, context):
        layout = self.layout
        layout.operator("edit_breakdown.del_scene_all", icon='X')
        layout.operator("edit_breakdown.assign_shots_to_scene", text="Assign Scene to Shots")


classes = (
    SEQUENCER_OT_add_scene,
    SEQUENCER_OT_del_scene,
    SEQUENCER_OT_del_scene_all,
    SEQUENCER_OT_move_scene,
    SEQUENCER_MT_scenes_context_menu,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
