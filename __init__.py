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
    "version": (0, 2, 0),
    "blender": (2, 91, 0),
    "location": "Video Sequence Editor",
    "description": "Get insight on the complexity of an edit",
    "doc_url": "https://github.com/britalmeida/blender_addon_edit_breakdown",
    "category": "Sequencer",
}

import logging

if "draw_utils" in locals():
    import importlib

    importlib.reload(data)
    importlib.reload(draw_utils)
    importlib.reload(ops)
    importlib.reload(panels)
    importlib.reload(tools)
    importlib.reload(utils)
    importlib.reload(view)
else:
    from . import data
    from . import draw_utils
    from . import ops
    from . import panels
    from . import tools
    from . import utils
    from . import view

log = logging.getLogger(__name__)


def register():
    log.info("------Registering Add-on---------------------------")

    data.register()
    ops.register()
    panels.register()
    tools.register()
    view.register()

    log.info("------Done Registering-----------------------------")


def unregister():

    log.info("------Unregistering Add-on-------------------------")

    data.unregister()
    ops.unregister()
    panels.unregister()
    tools.unregister()
    view.unregister()

    log.info("------Done Unregistering---------------------------")


if __name__ == "__main__":
    register()
