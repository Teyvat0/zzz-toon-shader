"""Own outline: hull shader (palette colour as emission) and the geometry-nodes hull.

The hull width is a fraction of the frame, so the line keeps its screen width for any
camera distance or focal length. Colours are final linear values (no hidden gain).
"""
import bpy
from .toon_lib import G

SHADER = 'ZZZ_Toon_Outline'
SHELL_ATTRIBUTE = 'ZZZ_OutlineShell'   # face bool, True on hull faces (read by the bridge's shell mask)
WIDTH_K = 0.0007    # frame fraction per addon width unit: 0.34 -> 0.0015 of the long frame side
WELD = 1e-5          # hull vertices closer than this are welded so the hull does not tear at split normals
SMALL_ISLAND = 0.0055 # connected pieces smaller than (this x frame size)^2 get no hull (stitches, tiny buttons)
DARK_K = 0.35        # the line is never brighter than DARK_K x the surface brightness (dark cloth keeps a darker line)
VERSION = '3'
C, I = 'NodeSocketColor', 'NodeSocketInt'
INS = [('Domain', I, 3), ('OtherDataTex', C, (1, 0, 0, 1))] + [
    ('OutlineColor' + (str(k) if k > 1 else ''), C, (0.05, 0.05, 0.05, 1)) for k in range(1, 6)]
INS_EXTRA = [('Base Color', C, (1, 1, 1, 1))]


def shader_group(owner):
    """Hull colour = palette entry of the material id. Domain 3 (body) picks the entry from
    OtherData.R (same id decode as ZZZ_Toon_Maps), every other domain uses OutlineColor."""
    ng = bpy.data.node_groups.get(SHADER)
    if ng is not None and ng.get('zzz_toon_version') == VERSION and ng.get('zzz_owner') == owner:
        return ng
    ng = ng or bpy.data.node_groups.new(SHADER, 'ShaderNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    ng.interface.new_socket('Shader', in_out='OUTPUT', socket_type='NodeSocketShader')
    for name, kind, default in INS + INS_EXTRA:
        ng.interface.new_socket(name, in_out='INPUT', socket_type=kind).default_value = default
    g = G(ng)
    gi, go = g.n('NodeGroupInput', -900, 0), g.n('NodeGroupOutput', 700, 0)
    i = gi.outputs
    sp = g.n('ShaderNodeSeparateColor', -700, 300)
    g.L(i['OtherDataTex'], sp.inputs[0])
    f = g.math('MINIMUM', g.math('FLOOR', g.math('MULTIPLY', sp.outputs[0], 5.0, x=-550, y=300), 0.0, x=-450, y=300), 4.0, x=-350, y=300)
    palette = None
    for k, (name, _, _) in enumerate(INS[2:]):
        w = g.math('COMPARE', f, float(5 - (k + 1)), 0.1, x=-200, y=200 - 120 * k)
        part = g.vmath('SCALE', i[name], w, x=-50, y=200 - 120 * k).outputs[0]
        palette = part if palette is None else g.vmath('ADD', palette, part, x=100, y=200 - 120 * k).outputs[0]
    body = g.math('COMPARE', i['Domain'], 3.0, 0.1, x=-200, y=-450)
    em = g.n('ShaderNodeEmission', 600, 0)
    picked = g.mix(body, i['OutlineColor'], palette, x=250, y=0)
    # Keep the palette hue; only scale it down when the surface is darker than DARK_K x palette brightness.
    luma = (0.2126, 0.7152, 0.0722)
    base_l = g.math('MULTIPLY', g.vmath('DOT_PRODUCT', i['Base Color'], luma, x=250, y=-150).outputs['Value'], DARK_K, x=400, y=-150)
    pal_l = g.math('ADD', g.vmath('DOT_PRODUCT', picked, luma, x=250, y=-300).outputs['Value'], 1e-4, x=400, y=-300)
    ratio = g.math('MINIMUM', g.math('DIVIDE', base_l, pal_l, x=550, y=-200), 1.0, x=700, y=-200)
    g.L(g.vmath('SCALE', picked, ratio, x=850, y=0).outputs[0], em.inputs['Color'])
    g.L(em.outputs[0], go.inputs['Shader'])
    ng['zzz_toon_version'], ng['zzz_owner'] = VERSION, owner
    ng.use_fake_user = True
    return ng
