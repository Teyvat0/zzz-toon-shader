"""Rebuild ZZZ_Toon_Core.blend (node groups ZZZ_Toon_Core, ZZZ_Toon_Maps, ZZZ_Toon_Outline).

    blender --factory-startup -b --python export.py
"""
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from zzz_toon import toon_build, toon_maps, toon_outline

core, maps = toon_build.build(), toon_maps.build()
outline = toon_outline.shader_group('zzz_toon')
groups = {core, maps, outline}
for ng in groups:
    ng.use_fake_user = True
out = os.path.join(HERE, 'ZZZ_Toon_Core.blend')
bpy.data.libraries.write(out, groups, fake_user=True)
print('EXPORT', out, {ng.name: len(ng.nodes) for ng in groups})
