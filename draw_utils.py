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

import bgl
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

log = logging.getLogger(__name__)


# Color constants

background_color = (0.18, 0.18, 0.18, 1.0)
hover_effect_color = (1.0, 1.0, 1.0, 0.05)
theme_selected_object = bpy.context.preferences.themes['Default'].view_3d.object_selected
theme_active_object = bpy.context.preferences.themes['Default'].view_3d.object_active
selection_color = (theme_active_object[0], theme_active_object[1], theme_active_object[2], 1.0)

# Shaders and batches


line_indices = ((0, 1), (1, 2), (2, 3), (3, 0))
rect_indices = ((0, 1, 2), (2, 1, 3))
rect_coords = ((0, 0), (1, 0), (1, 1), (0, 1))

ucolor_2d_shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
ucolor_2d_rect_batch = batch_for_shader(ucolor_2d_shader, 'TRI_FAN', {"pos": rect_coords})

ucolor_lines_rect_batch = batch_for_shader(
    ucolor_2d_shader, 'LINES', {"pos": rect_coords}, indices=line_indices
)

image_2d_shader = gpu.shader.from_builtin('2D_IMAGE')
image_2d_batch = batch_for_shader(
    image_2d_shader, 'TRI_FAN', {"pos": rect_coords, "texCoord": rect_coords}
)


def draw_background(size):
    """Draw a solid rectangle with the background color with the given size"""

    with gpu.matrix.push_pop():
        gpu.matrix.translate([0, 0])
        gpu.matrix.scale(size)

        ucolor_2d_shader.bind()
        ucolor_2d_shader.uniform_float("color", background_color)
        ucolor_2d_rect_batch.draw(ucolor_2d_shader)


def draw_hover_highlight(position, size):
    """Draw a rectangular highlight"""

    bgl.glEnable(bgl.GL_BLEND)

    with gpu.matrix.push_pop():
        gpu.matrix.translate(position)
        gpu.matrix.scale(size)

        ucolor_2d_shader.bind()
        ucolor_2d_shader.uniform_float("color", hover_effect_color)
        ucolor_2d_rect_batch.draw(ucolor_2d_shader)

    bgl.glDisable(bgl.GL_BLEND)


def draw_selected_frame(position, size):
    """Draw a rectangular frame"""

    with gpu.matrix.push_pop():
        gpu.matrix.translate(position)
        gpu.matrix.scale(size)

        ucolor_2d_shader.bind()
        ucolor_2d_shader.uniform_float("color", selection_color)
        ucolor_lines_rect_batch.draw(ucolor_2d_shader)


def draw_boolean_tag(position, size, color):

    bgl.glEnable(bgl.GL_BLEND)

    with gpu.matrix.push_pop():
        gpu.matrix.translate(position)
        gpu.matrix.scale(size)

        # Render a colored rectangle
        ucolor_2d_shader.bind()
        ucolor_2d_shader.uniform_float("color", color)
        ucolor_2d_rect_batch.draw(ucolor_2d_shader)

    bgl.glDisable(bgl.GL_BLEND)


def draw_thumbnails(thumbnail_images, size):

    bgl.glActiveTexture(bgl.GL_TEXTURE0)

    for img in thumbnail_images:
        # Bind the image texture.
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, img.id_image.bindcode)

        # Push the position and image size (pop when out of scope).
        with gpu.matrix.push_pop():
            gpu.matrix.translate(img.pos)
            gpu.matrix.scale(size)

            # Bind the image shader and render
            image_2d_shader.bind()
            image_2d_shader.uniform_int("image", 0)
            image_2d_batch.draw(image_2d_shader)
