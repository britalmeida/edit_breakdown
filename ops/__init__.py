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
import bpy

from .. import view

log = logging.getLogger(__name__)


if "sync" in locals():
    import importlib

    importlib.reload(scene)
    importlib.reload(shot)
    importlib.reload(sync)
else:
    from . import scene
    from . import shot
    from . import sync


# UI ##############################################################################################


def draw_sequencer_header_extension_left(self, context):
    if not view.is_thumbnail_view():
        return
    layout = self.layout
    layout.prop(context.scene.edit_breakdown, "view_grouped_by_scene", text="Group by Scene")


def draw_sequencer_header_extension_right(self, context):
    if not view.is_thumbnail_view():
        return
    layout = self.layout
    layout.operator("edit_breakdown.sync_edit_breakdown", icon='SEQ_SPLITVIEW')  # FILE_REFRESH
    layout.operator("edit_breakdown.copy_edit_breakdown_as_csv", icon='FILE')


# Add-on Registration #############################################################################


def register():
    scene.register()
    shot.register()
    sync.register()

    bpy.types.SEQUENCER_HT_header.prepend(draw_sequencer_header_extension_left)
    bpy.types.SEQUENCER_HT_header.append(draw_sequencer_header_extension_right)


def unregister():

    bpy.types.SEQUENCER_HT_header.remove(draw_sequencer_header_extension_right)
    bpy.types.SEQUENCER_HT_header.remove(draw_sequencer_header_extension_left)

    sync.unregister()
    shot.unregister()
    scene.unregister()
