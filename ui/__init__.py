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

log = logging.getLogger(__name__)


if "draw_utils" in locals():
    import importlib

    importlib.reload(draw_utils)
    importlib.reload(thumbnail_grid)
    importlib.reload(panels)
else:
    from . import draw_utils
    from . import thumbnail_grid
    from . import panels


def is_thumbnail_view():
    """True if the current space has the edit breakdown view enabled.

    Note: I found no way of making a new space or mode toggle for this
    add-on, therefore, I'm hijacking the Display Channels toggle as it
    seems to be a little used option with no performance impact on the
    sequencer. This is less than ideal as it breaks the Display Channels
    functionality and doesn't make for a good user experience.
    TODO: whenever possible, switch the thumbnail view to its own editor
    space or add a toggle to the region/area/space if they get support
    for ID properties."""
    return bpy.context.space_data.preview_channels == 'COLOR'


def draw_sequencer_header_extension_left(self, context):
    if not is_thumbnail_view():
        return
    layout = self.layout
    layout.prop(context.scene.edit_breakdown, "view_grouped_by_scene", text="Group by Scene")


def draw_sequencer_header_extension_right(self, context):
    if not is_thumbnail_view():
        return
    layout = self.layout
    layout.operator("edit_breakdown.sync_edit_breakdown", icon='SEQ_SPLITVIEW')  # FILE_REFRESH
    layout.operator("edit_breakdown.copy_edit_breakdown_as_csv", icon='FILE')



def register():

    draw_utils.register()
    thumbnail_grid.register()
    panels.register()

    bpy.types.SEQUENCER_HT_header.prepend(draw_sequencer_header_extension_left)
    bpy.types.SEQUENCER_HT_header.append(draw_sequencer_header_extension_right)


def unregister():

    bpy.types.SEQUENCER_HT_header.remove(draw_sequencer_header_extension_right)
    bpy.types.SEQUENCER_HT_header.remove(draw_sequencer_header_extension_left)

    panels.unregister()
    thumbnail_grid.unregister()
    draw_utils.unregister()
