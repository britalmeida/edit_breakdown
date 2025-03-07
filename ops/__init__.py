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

def draw_sequencer_header_extension_right(self, context):
    """Draw controls at the right end of the Sequence Preview Editor"""
    editor = context.space_data
    if not (editor.type == 'SEQUENCE_EDITOR' and editor.view_type == 'PREVIEW'):
        return

    layout = self.layout
    row = layout.row(align=True)
    row.prop(editor, "show_frames", text="", icon='SEQ_SPLITVIEW')

    sub = row.row(align=True)
    sub.active = view.is_thumbnail_view()
    sub.popover(panel="SEQUENCER_PT_edit_breakdown_view_settings", text="")
    sub.operator("edit_breakdown.sync_edit_breakdown", icon='FILE_REFRESH', text="")


# Add-on Registration #############################################################################

def register():
    scene.register()
    shot.register()
    sync.register()

    bpy.types.SEQUENCER_HT_header.append(draw_sequencer_header_extension_right)


def unregister():
    bpy.types.SEQUENCER_HT_header.remove(draw_sequencer_header_extension_right)

    sync.unregister()
    shot.unregister()
    scene.unregister()
