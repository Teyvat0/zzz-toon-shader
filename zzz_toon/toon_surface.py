"""Surface wiring for ZZZ_Toon_Core: textures + JSON parameters -> core inputs.

materials.build_material creates the nodes and texture images; this module owns the
shared core/maps groups, the parameter defaults and the wiring between them.
"""
import bpy
from .toon_lib import G
from . import toon_build, toon_maps

VERSION = '4'
CORE_NODE, MAPS_NODE = 'ZZZ_Toon', 'ZZZ_Toon_Maps'
BASE_TINT, ALPHA_MUL = 'ZZZ_BaseTint', 'ZZZ_AlphaMul'   # nodes game_bridge rewires for live morphs
HAIR_SPEC, HAIR_SATURATION = 0.08, 1.15
FACE_GLOW, FACE_TERMINATOR = 0.3, (1.0, 0.78, 0.70, 1.0)
STOPS = (0.0, 0.19, 0.39, 0.59, 0.79)   # floor(R*5) = 0..4 -> id = 4 - f

# JSON-driven parameters (name = JSON key without the leading underscore) and their defaults
DEFAULTS = {'Color': (1.0, 1.0, 1.0, 1.0), 'NoseLineHoriDisp': 0.92, 'NoseLineLkDnDisp': 0.62}
COLORS = {'Color'}
for _k in range(1, 6):
    _s = '' if _k == 1 else str(_k)
    DEFAULTS.update({
        'ShallowColor' + _s: (0.610494, 0.610494, 0.610494, 1.0),
        'ShadowColor' + _s: (0.323142, 0.323142, 0.323142, 1.0),
        'OutlineColor' + _s: (1.0, 1.0, 1.0, 1.0),
        'MatCapColorTint' + _s: (1.0, 1.0, 1.0, 1.0),
        'MatCapColorBurst' + _s: 1.0, 'MatCapAlphaBurst' + _s: 1.0, 'MatCapBlendMode' + _s: 0,
    })
    COLORS.update(('ShallowColor' + _s, 'ShadowColor' + _s, 'OutlineColor' + _s, 'MatCapColorTint' + _s))


def suffix(index):
    return str(index) if index > 1 else ''


def core_groups(owner):
    """Build (or reuse) the shared ZZZ_Toon_Core / ZZZ_Toon_Maps groups for this run."""
    pair = []
    for module in (toon_build, toon_maps):
        tree = bpy.data.node_groups.get(module.NAME)
        if tree is None or tree.get('zzz_toon_version') != VERSION or tree.get('zzz_owner') != owner:
            tree = module.build()
            tree['zzz_toon_version'], tree['zzz_owner'] = VERSION, owner
            tree.use_fake_user = True
        pair.append(tree)
    return pair


def nodes(tree, owner, output, x=200, y=200):
    """Create the core + maps group nodes and connect the core to the material output."""
    core_tree, maps_tree = core_groups(owner)
    g = G(tree)
    core = g.n('ShaderNodeGroup', x, y, label='ZZZ_Toon', name=CORE_NODE, node_tree=core_tree, width=250)
    maps = g.n('ShaderNodeGroup', x - 300, y, label='Maps', name=MAPS_NODE, node_tree=maps_tree)
    g.L(core.outputs['Shader'], output.inputs['Surface'])
    return core, maps


def ramp(g, fac, p, base, x, y):
    """Per-material-id colour via a constant ColorRamp (id k <-> suffix k+1)."""
    r = g.n('ShaderNodeValToRGB', x, y)
    r.color_ramp.interpolation = 'CONSTANT'
    el = r.color_ramp.elements
    while len(el) < 5:
        el.new(0.5)
    for f, e in enumerate(el):
        e.position = STOPS[f]
        e.color = p[base + suffix(4 - f + 1)]
    g.set(r.inputs[0], fac)
    return r.outputs[0]


def live_vectors(tree, core):
    """Light and head frame come from the ZZZ_LightHead geometry attributes, so a moved Sun
    or an animated head bone reaches the shader every frame (no baked constants)."""
    g = G(tree)
    x, y = core.location.x - 900, core.location.y + 1000

    def attr(name, dy):
        a = g.n('ShaderNodeAttribute', x, y + dy, label=name, attribute_type='GEOMETRY', attribute_name=name)
        return a.outputs['Vector']
    center = attr('HeadCenter', 0)
    unit = lambda v, dy: g.vmath('NORMALIZE', v, x=x + 250, y=y + dy).outputs['Vector']
    g.L(center, core.inputs['Head Center'])
    g.L(unit(attr('LightDirectionWS', -200), -200), core.inputs['Light Dir'])
    for name, socket, dy in (('HeadForward', 'Head Forward', -400), ('HeadRight', 'Head Right', -600)):
        delta = g.vmath('SUBTRACT', attr(name, dy), center, x=x + 100, y=y + dy)
        g.L(unit(delta.outputs['Vector'], dy), core.inputs[socket])


def wire_caps(tree, c, mp, caps):
    """One image per id (already UV-mapped by Maps), picked by the id decoded from OtherData.
    caps: [(suffix_index 1..5, image node, tint rgb, alpha amount, blend mode)]"""
    if not (c and mp and caps):
        return
    g = G(tree)
    x0, y0 = c.location.x, c.location.y
    # id 1.0 would land in segment 5 and 8-bit dither flips it to 4: clamp so the top segment is stable
    f = g.math('MINIMUM', g.math('FLOOR', g.math('MULTIPLY', mp.outputs['ID'], 5.0, x=x0 - 500, y=y0 - 600), 0.0, x=x0 - 400, y=y0 - 600), 4.0, x=x0 - 350, y=y0 - 600)
    col = alp = mod = None
    for k, (suf, t, tint, a, mode) in enumerate(caps):
        y = y0 - 700 - 200 * k
        t.extension = 'EXTEND'
        sel = g.math('COMPARE', f, float(5 - suf), 0.1, x=x0 - 150, y=y)
        tc = g.vmath('MULTIPLY', t.outputs[0], (tint[0], tint[1], tint[2]), x=x0 - 100, y=y)
        cc = g.vmath('SCALE', tc.outputs[0], sel, x=x0 - 50, y=y).outputs[0]
        aa = g.math('MULTIPLY', sel, a, x=x0 - 50, y=y - 60)
        mm = g.math('MULTIPLY', sel, float(mode), x=x0 - 50, y=y - 100)
        col = cc if col is None else g.vmath('ADD', col, cc, x=x0 + 50, y=y).outputs[0]
        alp = aa if alp is None else g.math('ADD', alp, aa, x=x0 + 50, y=y - 60)
        mod = mm if mod is None else g.math('ADD', mod, mm, x=x0 + 50, y=y - 100)
    g.L(col, c.inputs['MatCap'])
    g.L(g.math('MULTIPLY', alp, mp.outputs['MatCap Mask'], x=x0 + 100, y=y0 - 800), c.inputs['MatCap Alpha'])
    g.L(mod, c.inputs['MatCap Mode'])


def _tints(g, core, maps, p, tex, dom, x, y):
    """Per-material-id shade colours (body) or the skin pair (face)."""
    has_id = dom == 3 and tex.get('data')
    idf = maps.outputs['ID'] if has_id else 0.0
    core.inputs['Shallow Tint'].default_value = p['ShallowColor5']
    core.inputs['Deep Tint'].default_value = p['ShadowColor5']
    if has_id:
        g.L(g.math('LESS_THAN', idf, 0.2, x=x - 150, y=y + 700), core.inputs['Skin Mask'])
    if dom == 3:
        g.L(ramp(g, idf, p, 'ShallowColor', x - 150, y + 300), core.inputs['Shallow Tint'])
        g.L(ramp(g, idf, p, 'ShadowColor', x - 150, y + 500), core.inputs['Deep Tint'])
    if dom == 1:
        core.inputs['Skin Mask'].default_value = 1.0
        core.inputs['Shallow Tint'].default_value = p['ShallowColor']
        core.inputs['Deep Tint'].default_value = p['ShadowColor']


def _face(g, core, p, tex, x, y):
    if tex.get('main'):
        g.L(tex['main'].outputs['Alpha'], core.inputs['Nose Alpha'])
    core.inputs['Nose Front'].default_value = p['NoseLineHoriDisp']
    core.inputs['Nose Down'].default_value = p['NoseLineLkDnDisp']
    if tex.get('light'):
        g.L(tex['light'].outputs['Alpha'], core.inputs['Face Mask'])
    edges = []
    for key, name in (('light', 'Face SDF'), ('data', 'Face SDF Mirror')):
        sp = g.n('ShaderNodeSeparateColor', x - 300, y - 300)
        g.L(tex[key].outputs['Color'], sp.inputs[0])
        g.L(sp.outputs[0], core.inputs[name])
        edges.append(sp.outputs[1])
    g.L(edges[0], core.inputs['Face Edge'])
    g.L(edges[1], core.inputs['Face Edge Mirror'])
    core.inputs['Glow Amount'].default_value = FACE_GLOW   # warmer terminator: cheeks/jaw fade pink, not grey-beige
    core.inputs['Terminator Glow'].default_value = FACE_TERMINATOR


def wire(tree, core, maps, role, tex, p, color, alpha, caps):
    """tex: image nodes by purpose (main/light/data/data2, None when absent); p: parameters;
    color: linear RGBA; alpha: float; caps: see wire_caps. Domain must already be set on core."""
    g = G(tree)
    x, y = core.location.x, core.location.y
    dom = core.inputs['Domain'].default_value
    tint = g.n('ShaderNodeMixRGB', x - 450, y - 200, blend_type='MULTIPLY', name=BASE_TINT, label=BASE_TINT)
    tint.inputs[0].default_value = 1.0
    tint.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    tint.inputs[2].default_value = color
    if tex.get('main'):
        g.L(tex['main'].outputs['Color'], tint.inputs[1])
    g.L(tint.outputs[0], core.inputs['Base Color'])
    am = g.n('ShaderNodeMath', x - 300, y - 700, operation='MULTIPLY', name=ALPHA_MUL, label=ALPHA_MUL)
    am.inputs[0].default_value = alpha
    am.inputs[1].default_value = 1.0
    if dom == 2 and role != 'eye_shadow' and tex.get('main'):   # eyes: live alpha x painted alpha
        g.L(tex['main'].outputs['Alpha'], am.inputs[1])
    g.L(am.outputs[0], core.inputs['Alpha'])
    for key, dst in (('light', 'Light Tex'), ('data', 'Other Data'), ('data2', 'Other Data 2')):
        if tex.get(key):
            g.L(tex[key].outputs['Color'], maps.inputs[dst])
    for name in ('Normal', 'Shade Bias', 'AO', 'Metal', 'Spec Mask'):
        if dom == 3 or name in ('Shade Bias', 'AO'):
            g.L(maps.outputs[name], core.inputs[name])
    _tints(g, core, maps, p, tex, dom, x, y)
    if dom == 1:
        _face(g, core, p, tex, x, y)
    live_vectors(tree, core)
    if role == 'hair' and dom == 3:
        core.inputs['Hair Spec'].default_value = HAIR_SPEC
        core.inputs['Saturation'].default_value = HAIR_SATURATION
    if dom == 3:
        wire_caps(tree, core, maps, caps)
