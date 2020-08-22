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

# <pep8-80 compliant>

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

import os
import bpy
from bpy.types import Operator, Panel, AddonPreferences
from bpy.props import BoolProperty, StringProperty, EnumProperty

import bgl
import gpu
from gpu_extras.presets import draw_texture_2d
from gpu_extras.batch import batch_for_shader

import blf

from bpy_extras.image_utils import load_image


# Operators ###################################################################

# UI ##########################################################################

vertices = (
    (0, 0), (1900, 0),
    (0, 933), (1900, 933))

indices = ((0, 1, 2), (2, 1, 3))

shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)


def draw_background():
    shader.bind()
    shader.uniform_float("color", (0.18, 0.18, 0.18, 1.0))
    batch.draw(shader)


edit_image_size = (100, 100/1.7777)
spacing = (9, 6)
num_images_per_row = 17
class EditImage:
    id_image = None
    name = "Frog"
    pos = (0, 0)

edit_images = []

def load_edit_images():

    addon_prefs = bpy.context.preferences.addons[__name__].preferences
    folder_name = addon_prefs.edit_shots_folder

    try:
        for filename in os.listdir(folder_name):
            img = EditImage()
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
            edit_images.append(img)
            img.name = int(filename.split('.')[0])
    except FileNotFoundError:
        # self.report({'ERROR'}, # Need an operator
        print(
            f"Reading thumbnail images from '{folder_name}' failed: folder does not exist.")

    edit_images.sort(key=lambda x: x.name, reverse=False)

    for img in edit_images:
        if img.id_image.gl_load():
            raise Exception()

    # Assume all images in the edit have the same aspect ratio
    image_w = edit_images[0].id_image.size[0]
    image_h = edit_images[0].id_image.size[1]
    image_aspect_ratio = image_w / image_h

    num_images = len(edit_images)
    print(f"Loaded {num_images} images.")

    #text_info_h = 50
    #total_w = image_w*num_images
    #total_h = (image_h+text_info_h)*num_images

    region = bpy.context.region
    available_w = region.width
    available_h = region.height
    #available_aspect_ratio = available_w / available_h

    #global edit_image_size
    #if available_aspect_ratio < image_aspect_ratio:
    #    print( width bound)
    #    edit_image_size = (available_w -50, (available_w -50) / available_aspect_ratio)
    #else:
    #    edit_image_size = ((available_h -80) / available_aspect_ratio, (available_h -80))

    num_images_per_column = num_images / num_images_per_row

    start_pos_x = 25
    start_pos_y = available_h - edit_image_size[1] - 40

    c = 0
    for img in edit_images:
        img.pos = (start_pos_x, start_pos_y)
        #print(img.pos)
        start_pos_x += edit_image_size[0] + spacing[0]
        c+=1
        if c == num_images_per_row:
            c = 0
            start_pos_x = 25
            start_pos_y -= edit_image_size[1] + spacing[1] #text_info_h


def draw_edit_images():
    if not edit_images:
        load_edit_images()

    for img in edit_images:
        draw_texture_2d(img.id_image.bindcode, img.pos, edit_image_size[0], edit_image_size[1])


# Font ####################################################################

font_info = {
    "font_id": 0, # Default font.
    "handler": None,
}

def draw_text(self, context):
    font_id = font_info["font_id"]
    blf.position(font_id, 600, 80, 0)
    blf.size(font_id, 16, 72)
    blf.draw(font_id, "Frog")


# Settings ####################################################################


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


# Add-on Registration #########################################################

classes = (
    SEQUENCER_EditBreakdown_Preferences,
)

draw_handles = []
space = bpy.types.SpaceImageEditor # SpaceSequenceEditor

def register():
    print("-----------------Registering Edit Breakdown-------------------------")

    for cls in classes:
        bpy.utils.register_class(cls)

    draw_handles.append(space.draw_handler_add(draw_background, (), 'WINDOW', 'POST_PIXEL'))
    draw_handles.append(space.draw_handler_add(draw_edit_images, (), 'WINDOW', 'POST_PIXEL'))
    font_info["handler"] = space.draw_handler_add(draw_text, (None, None), 'WINDOW', 'POST_PIXEL')

    print("-----------------Done Registering---------------------------------")


def unregister():

    print("-----------------Unregistering Edit Breakdown-----------------------")

    for handle in draw_handles:
        space.draw_handler_remove(handle, 'WINDOW')

    for cls in classes:
        bpy.utils.unregister_class(cls)

    print("-----------------Done Unregistering--------------------------------")


if __name__ == "__main__":
    register()
