"""Builds the ZZZ_Toon_Core node group. Usage: blender -b --python zt_build.py"""
import bpy
from .toon_lib import G
from .toon_core import NAME, make_interface

WHITE = (1, 1, 1, 1)


def view_pos(g):
    """Camera-space position of the shaded point (created once per group)."""
    if not hasattr(g, '_vp'):
        pos = g.n('ShaderNodeNewGeometry', -1700, -700)
        vp = g.n('ShaderNodeVectorTransform', -1550, -700, vector_type='POINT',
                 convert_from='WORLD', convert_to='CAMERA')
        g.L(pos.outputs['Position'], vp.inputs[0])
        cd = g.n('ShaderNodeCameraData', -1550, -820)
        g._vp = (vp.outputs[0], cd.outputs['View Z Depth'])
    return g._vp


def screen_shadow(g, i):
    """1 where something nearer the camera sits towards the light on screen."""
    vp, z = view_pos(g)
    lv = g.n('ShaderNodeVectorTransform', -1400, -900, vector_type='VECTOR',
             convert_from='WORLD', convert_to='CAMERA')
    g.L(i['Light Dir'], lv.inputs[0])
    sep = g.n('ShaderNodeSeparateXYZ', -1250, -900)
    g.L(lv.outputs[0], sep.inputs[0])
    flat = g.n('ShaderNodeCombineXYZ', -1120, -900)
    g.L(sep.outputs[0], flat.inputs[0])
    g.L(sep.outputs[1], flat.inputs[1])
    k = g.math('MULTIPLY', i['Model Scale'], 0.01, x=-1250, y=-1000)   # ~1 cm in view space
    off = g.vmath('MULTIPLY_ADD', flat.outputs[0], k, vp, x=-980, y=-900).outputs[0]
    ss = g.n('ShaderNodeScreenspaceInfo', -840, -900)
    g.L(off, ss.inputs['View Position'])
    gap = g.math('SUBTRACT', z, ss.outputs['Scene Depth'], x=-700, y=-900)
    return g.smooth(gap, g.math('MULTIPLY', i['Model Scale'], 0.011, x=-640, y=-960),
                    g.math('MULTIPLY', i['Model Scale'], 0.015, x=-640, y=-1000), x=-560, y=-900, label='contact shadow')


def lighting(g, i, nrm, occ):
    """Scalar light term t (body): half-lambert x cast shadow x screen shadow."""
    si = g.n('ShaderNodeShaderInfo', -1300, 300, label='Light')
    g.L(nrm, si.inputs['Normal'])
    lit = g.math('MULTIPLY', si.outputs['Cast Shadows'],
                 g.math('SUBTRACT', 1.0, occ, x=-1250, y=420), x=-1150, y=380)
    recv = g.mix(i['Receive Shadow'], 1.0, lit, kind='FLOAT', x=-1100, y=300)
    x = g.math('MULTIPLY', si.outputs['Half-lambert factor'], recv, x=-950, y=300)
    x = g.math('ADD', x, i['Shade Bias'], x=-800, y=300)
    return x, si.outputs['Half-lambert factor']   # shade term = half-lambert + lightmap bias (no AO)


def face_term(g, i):
    """Face SDF threshold in the same space as the body term."""
    L = g.vmath('NORMALIZE', i['Light Dir'], x=-1300, y=-100).outputs[0]
    dR = g.vmath('DOT_PRODUCT', L, i['Head Right'], x=-1150, y=-100).outputs['Value']
    dF = g.math('MULTIPLY', g.vmath('DOT_PRODUCT', L, i['Head Forward'], x=-1150, y=-250).outputs['Value'], -1.0, x=-1100, y=-250)   # game: dot(light, -HeadForward)
    ang = g.math('ARCTAN2', dR, dF, x=-1000, y=-150)
    ang = g.math('DIVIDE', ang, 3.14159265, x=-900, y=-150)
    # lit where the painted threshold map exceeds how far the light has swung away from the face front
    swing = g.math('MULTIPLY', g.math('ABSOLUTE', ang, x=-900, y=-250), i['Face Shadow'],
                   x=-840, y=-250, label='swing')
    side = g.math('GREATER_THAN', dR, 0.0, x=-1000, y=-350)
    sdf = g.mix(side, i['Face SDF'], i['Face SDF Mirror'], kind='FLOAT',
                x=-780, y=-350)
    gsel = g.mix(side, i['Face Edge'], i['Face Edge Mirror'], kind='FLOAT', x=-780, y=-450)
    g._dbg = {'sdf': sdf, 'ang': g.math('MULTIPLY_ADD', ang, 0.5, 0.5, x=-900, y=-200)}
    # nose/lip shadow, same mechanism as the game's face shader: where the SDF green channel is high the edge softness drops to 0.025,
    # which also shortens the divisor (4*soft+1) that compresses the painted threshold (R*1.2-0.6) -> that region gets a stronger, crisper shift
    kk = g.math('MULTIPLY', g.math('SUBTRACT', gsel, 0.5, x=-700, y=-450), 2.5, x=-640, y=-450, clamp=True)
    s_k = g.mix(kk, i['Face Soft'], 0.025, kind='FLOAT', x=-580, y=-450)
    inv_k = g.math('DIVIDE', 1.0, g.math('MULTIPLY_ADD', s_k, 4.0, 1.0, x=-520, y=-450), x=-460, y=-450)
    inv_0 = g.math('DIVIDE', 1.0, g.math('MULTIPLY_ADD', i['Face Soft'], 4.0, 1.0, x=-520, y=-500), x=-460, y=-500)
    r_c = g.math('SUBTRACT', g.math('MULTIPLY', sdf, 1.2, x=-700, y=-550), 0.6, x=-640, y=-550)
    inv = g.mix(i['Nose Shade'], inv_0, inv_k, kind='FLOAT', x=-400, y=-475)       # Nose Shade 0..1 fades between plain and nose-sharpened mapping
    thr = g.math('ADD', g.math('MULTIPLY', r_c, inv, x=-340, y=-500), 0.6, x=-280, y=-500, label='painted threshold')   # game: (R*1.2-0.6)/(4*soft+1)+0.6
    d = g.math('ADD', thr, i['Face Bias'], x=-640, y=-300)
    # game AngleThreshold = 1-|ang| (light straight ahead -> threshold 0, light from the side -> 1); Face Shadow scales it
    thr_a = g.math('MULTIPLY', g.math('SUBTRACT', 1.0, g.math('ABSOLUTE', ang, x=-900, y=-250), x=-860, y=-250), i['Face Shadow'], x=-800, y=-250)
    d = g.math('SUBTRACT', d, thr_a, x=-580, y=-250)
    return g.math('ADD', d, i['Light Edge'], x=-520, y=-250, label='t face'), gsel


def bands(g, i, t, base, face, occ, soft):
    """3-band toon colour (lit / shallow / deep) plus a warm terminator glow."""
    e, s = i['Light Edge'], soft
    lo = g.math('SUBTRACT', e, s, x=-500, y=500)
    hi = g.math('ADD', e, s, x=-500, y=440)
    s1 = g.smooth(t, lo, hi, x=-350, y=500, label='lit')
    e2 = g.math('SUBTRACT', e, i['Shadow Depth'], x=-500, y=360)
    s2 = g.smooth(t, g.math('SUBTRACT', e2, s, x=-380, y=360),
                  g.math('ADD', e2, s, x=-380, y=320), x=-250, y=360,
                  label='shallow')
    s2 = g.math('MAXIMUM', s2, g.math('MULTIPLY', face, g.math('SUBTRACT', 1.0, occ, x=-300, y=420), x=-250, y=400), x=-200, y=380, label='face: two tones, deep only under contact shadow')
    _, z = view_pos(g)
    far_k = g.math('MULTIPLY', z, 0.437, x=-420, y=120, clamp=True, label='distance')

    def hue_only(col, y):
        avg = g.vmath('DOT_PRODUCT', col, (1 / 3, 1 / 3, 1 / 3), x=-560, y=y).outputs['Value']
        inv = g.math('DIVIDE', 1.0, g.math('MAXIMUM', avg, 0.05, x=-500, y=y), x=-440, y=y)
        return g.vmath('SCALE', col, inv, x=-380, y=y).outputs[0]
    shc = g.mix(far_k, hue_only(i['Shallow Tint'], 60), i['Shallow Tint'], x=-300, y=100)
    dpc = g.mix(far_k, hue_only(i['Deep Tint'], -20), i['Deep Tint'], x=-300, y=40)
    sh = g.vmath('SCALE', shc, g.math('MULTIPLY', i['Shade Gain'], 0.791, x=-350, y=200),
                 x=-300, y=200).outputs[0]
    dp = g.vmath('SCALE', dpc, g.math('MULTIPLY', i['Shade Gain'], 0.61, x=-350, y=150),
                 x=-300, y=150).outputs[0]
    tint = g.mix(s2, dp, sh, x=-200, y=300)
    litc = g.mix(i['Lit Bleed'], WHITE, sh, x=-200, y=200)
    # thin warm line on the lit side of the terminator (sub-surface band)
    far2 = g.smooth(t, hi, g.math('ADD', hi, g.math('MULTIPLY', s, 2.0, x=-380, y=250), x=-330, y=250), x=-250, y=250)
    sss = g.math('MULTIPLY', s1, g.math('SUBTRACT', 1.0, far2, x=-120, y=250), x=0, y=250)
    sss = g.math('MULTIPLY', sss, i['Glow Amount'], x=100, y=250)
    litc = g.mix(sss, litc, i['Terminator Glow'], x=150, y=200)
    tint = g.mix(s1, tint, litc, x=200, y=300)
    lit = g.vmath('MULTIPLY', base, tint, x=300, y=300).outputs[0]
    return lit, s2


def specular(g, i, nrm, base, mask_off):
    """Two highlight models picked by Hair Spec: a thresholded glossy lobe for body/metal,
    and a hair model where the painted mask (Spec Mask) is ADDED to the geometric
    half-vector term before thresholding, so painted strands light up one by one."""
    pos = g.n('ShaderNodeNewGeometry', 0, -520)
    dh = g.vmath('SUBTRACT', pos.outputs['Position'], i['Head Center'], x=100, y=-520)
    dist = g.vmath('LENGTH', dh.outputs[0], x=200, y=-560).outputs['Value']
    dhn = g.vmath('NORMALIZE', dh.outputs[0], x=200, y=-520).outputs[0]
    rng = g.math('MULTIPLY', i['Head Sphere'], i['Model Scale'], x=200, y=-600)
    sphere = g.math('SUBTRACT', 1.0, g.math('SUBTRACT', dist, rng, x=300, y=-600), x=350, y=-600)
    sphere = g.math('MULTIPLY', sphere, 20.0, x=400, y=-600, clamp=True)    # 1 inside the head sphere, 0 beyond ~5cm
    ns = g.vmath('NORMALIZE', g.mix(g.math('MULTIPLY', sphere, g.math('GREATER_THAN', i['Hair Spec'], 0.001, x=380, y=-640),
                                           x=450, y=-620), nrm, dhn, kind='VECTOR', x=500, y=-520), x=600, y=-520).outputs[0]
    # glossy lobe (body / metal)
    gl = g.n('ShaderNodeBsdfGlossy', 100, -300, label='Gloss lobe')
    gl.inputs['Roughness'].default_value = 0.3
    g.L(ns, gl.inputs['Normal'])
    rgb = g.n('ShaderNodeShaderToRGB', 250, -300)
    g.L(gl.outputs[0], rgb.inputs[0])
    v = g.n('ShaderNodeRGBToBW', 400, -300)
    g.L(rgb.outputs[0], v.inputs[0])
    thr = g.math('SUBTRACT', 1.2, g.math('MULTIPLY', i['Spec Size'], 1.1, x=250, y=-420), x=400, y=-420)
    sp = g.smooth(v.outputs[0], thr, g.math('ADD', thr, 0.1, x=500, y=-420), x=600, y=-320)
    sp = g.math('MULTIPLY', sp, i['Spec Mask'], x=700, y=-320)
    # hair strands
    L = g.vmath('NORMALIZE', i['Light Dir'], x=300, y=-760).outputs[0]
    inc = g.n('ShaderNodeNewGeometry', 300, -820)
    H = g.vmath('NORMALIZE', g.vmath('ADD', L, inc.outputs['Incoming'], x=400, y=-780).outputs[0], x=500, y=-780).outputs[0]
    hl = g.math('MULTIPLY_ADD', g.vmath('DOT_PRODUCT', ns, H, x=600, y=-760).outputs['Value'], 0.5, 0.5, x=700, y=-760)
    nl = g.vmath('DOT_PRODUCT', ns, L, x=600, y=-840).outputs['Value']
    att = g.math('SQRT', g.math('MULTIPLY_ADD', nl, 0.5, 0.5, x=700, y=-840, clamp=True), x=780, y=-840)
    face = g.math('MULTIPLY_ADD', nl, 0.75, 0.25, x=780, y=-900, clamp=True)
    e0 = g.math('ADD', g.math('MULTIPLY', hl, att, x=850, y=-760), i['Spec Mask'], x=920, y=-760)
    st = g.smooth(e0, 1.0, g.math('ADD', 1.0, i['Hair Soft'], x=920, y=-820), x=1000, y=-760, label='painted strands')
    hs = g.math('MULTIPLY', g.math('MULTIPLY', st, face, x=1080, y=-780), i['Hair Spec'], x=1150, y=-780)
    flag = g.math('GREATER_THAN', i['Hair Spec'], 0.001, x=1080, y=-860)
    sp = g.mix(flag, sp, hs, kind='FLOAT', x=1250, y=-600)
    sp = g.math('MULTIPLY', sp, mask_off, x=1350, y=-600)
    col = g.mix(i['Metal'], i['Spec Color'], base, x=700, y=-420)
    return col, sp


def rim(g, i, nrm, mask):
    """Screen-space rim: compare scene depth a little outside the silhouette."""
    vpo, own = view_pos(g)
    vn = g.n('ShaderNodeVectorTransform', 250, -700, vector_type='NORMAL',
             convert_from='WORLD', convert_to='CAMERA')
    g.L(nrm, vn.inputs[0])
    sep = g.n('ShaderNodeSeparateXYZ', 400, -700)
    g.L(vn.outputs[0], sep.inputs[0])
    flat = g.n('ShaderNodeCombineXYZ', 520, -700)
    g.L(sep.outputs[0], flat.inputs[0])
    g.L(sep.outputs[1], flat.inputs[1])
    d = g.vmath('NORMALIZE', flat.outputs[0], x=640, y=-700).outputs[0]
    w = g.math('MULTIPLY', i['Rim Width'], 0.009, x=640, y=-800)
    off = g.vmath('MULTIPLY_ADD', d, w, vpo, x=780, y=-700).outputs[0]
    ss = g.n('ShaderNodeScreenspaceInfo', 920, -700)
    g.L(off, ss.inputs['View Position'])
    diff = g.math('SUBTRACT', ss.outputs['Scene Depth'], own, x=1060, y=-700)
    r = g.smooth(diff, 0.12, 0.3, x=1200, y=-700, label='depth edge')
    rim.diff = diff
    rim.sd = ss.outputs['Scene Depth']
    rim.own = own
    return g.math('MULTIPLY', r, mask, x=1330, y=-700)


def matcap(g, i, tot, noteye):
    """Blend a matcap colour onto the shaded colour: lerp / add / overlay (soft sheen)."""
    amt = g.math('MULTIPLY', g.math('MULTIPLY', i['MatCap Alpha'], noteye, x=1400, y=-120),
                 1.0, x=1450, y=-120, clamp=True, label='matcap amount')
    mc = i['MatCap']
    lerp = g.mix(amt, tot, mc, x=1550, y=-200)
    add = g.vmath('MULTIPLY_ADD', mc, amt, tot, x=1550, y=-300).outputs[0]
    half = g.mix(amt, (0.5, 0.5, 0.5, 1), mc, x=1550, y=-400)
    ov = g.n('ShaderNodeMix', 1700, -400, data_type='RGBA', blend_type='OVERLAY')
    ov.inputs[0].default_value = 1.0
    g.L(tot, ov.inputs[6])
    g.L(half, ov.inputs[7])
    m0 = g.math('LESS_THAN', i['MatCap Mode'], 0.5, x=1650, y=-120)
    m1 = g.math('LESS_THAN', i['MatCap Mode'], 1.5, x=1650, y=-170)
    r = g.mix(m1, ov.outputs[2], add, x=1850, y=-300)
    res = g.mix(m0, r, lerp, x=1950, y=-250)
    return g.vmath('MAXIMUM', res, g.vmath('SCALE', tot, 0.6, x=1950, y=-330).outputs[0], x=2000, y=-250).outputs[0]   # a dark matcap rim never blacks out the surface


def grade(g, i, col):
    col = g.vmath('SCALE', col, None, x=1500, y=0)
    g.L(i['Exposure'], col.inputs[3])
    x = col.outputs[0]
    a = g.vmath('MULTIPLY_ADD', x, (2.51, 2.51, 2.51), (0.03, 0.03, 0.03), x=1600, y=100).outputs[0]
    num = g.vmath('MULTIPLY', x, a, x=1700, y=100).outputs[0]
    b = g.vmath('MULTIPLY_ADD', x, (2.43, 2.43, 2.43), (0.59, 0.59, 0.59), x=1600, y=0).outputs[0]
    den = g.vmath('MULTIPLY_ADD', x, b, (0.14, 0.14, 0.14), x=1700, y=0).outputs[0]
    aces = g.vmath('DIVIDE', num, den, x=1800, y=50).outputs[0]
    col = g.mix(i['Tone Curve'], x, aces, x=1900, y=50)
    hs = g.n('ShaderNodeHueSaturation', 2000, 50)
    g.L(i['Saturation'], hs.inputs['Saturation'])
    g.L(col, hs.inputs['Color'])
    return hs.outputs[0]


def build():
    ng = bpy.data.node_groups.get(NAME) or bpy.data.node_groups.new(NAME, 'ShaderNodeTree')
    ng.nodes.clear()
    make_interface(ng)
    g = G(ng)
    gi = g.n('NodeGroupInput', -1700, 0)
    go = g.n('NodeGroupOutput', 2600, 0)
    i = gi.outputs
    face = g.math('COMPARE', i['Domain'], 1.0, 0.1, x=-1500, y=200)
    eye = g.math('COMPARE', i['Domain'], 2.0, 0.1, x=-1500, y=100)
    noteye = g.math('SUBTRACT', 1.0, eye, x=-1350, y=100)
    base = i['Base Color']
    # nose-tip line: painted into the face texture alpha, revealed only while the camera looks at the face from the front
    gv = g.n('ShaderNodeNewGeometry', -1500, -950)
    inc = gv.outputs['Incoming']
    up = g.vmath('CROSS_PRODUCT', i['Head Right'], i['Head Forward'], x=-1400, y=-1000).outputs[0]
    d_f = g.vmath('DOT_PRODUCT', inc, i['Head Forward'], x=-1300, y=-950).outputs['Value']
    d_u = g.vmath('DOT_PRODUCT', inc, up, x=-1300, y=-1050).outputs['Value']
    thr = g.mix(g.smooth(g.math('ADD', d_u, 0.85, x=-1200, y=-1050, clamp=True), 0.0, 0.75, x=-1100, y=-1050),
                i['Nose Down'], i['Nose Front'], kind='FLOAT', x=-1000, y=-1000)
    seen = g.smooth(g.math('SUBTRACT', d_f, thr, x=-900, y=-950), 0.0, 0.02, x=-800, y=-950)
    nose = g.math('MULTIPLY', g.math('SUBTRACT', seen, i['Nose Alpha'], x=-700, y=-950, clamp=True),
                  g.math('MULTIPLY', i['Nose Line'], face, x=-700, y=-1000), x=-600, y=-950, label='nose line')
    base = g.mix(nose, base, i['Nose Color'], x=-500, y=-950)
    geo = g.n('ShaderNodeNewGeometry', -1500, -300)
    has = g.math('GREATER_THAN', g.vmath('LENGTH', i['Normal'], x=-1500, y=-450).outputs['Value'], 0.5, x=-1350, y=-450)
    nb = g.math('MULTIPLY', has, i['Normal Blend'], x=-1250, y=-520)
    nrm = g.vmath('NORMALIZE', g.mix(nb, geo.outputs['Normal'], i['Normal'], kind='VECTOR',
                                     x=-1200, y=-400), x=-1100, y=-400).outputs[0]
    occ = screen_shadow(g, i)
    t, hl_pix = lighting(g, i, nrm, occ)
    # painted shade detail: albedo gets darker where the lightmap normal faces away from the light more than the mesh does
    sg = g.n('ShaderNodeShaderInfo', -1300, 560, label='Light (mesh normal)')
    d_raw = g.math('SUBTRACT', sg.outputs['Half-lambert factor'], hl_pix, x=-1150, y=560)
    dd = g.math('MULTIPLY', g.math('MULTIPLY', d_raw, 6.0, x=-1050, y=560, clamp=True), g.math('MULTIPLY', has, i['Detail Dark'], x=-1050, y=520), x=-950, y=540)
    gm = g.n('ShaderNodeGamma', -850, 540, label='detail darken')
    g.L(base, gm.inputs['Color'])
    g.L(g.math('MULTIPLY_ADD', dd, 1.5, 1.0, x=-950, y=500), gm.inputs['Gamma'])
    base = gm.outputs[0]
    tface, gsel = face_term(g, i)
    tf = g.math('SUBTRACT', tface, g.math(
        'MULTIPLY', occ, g.math('MULTIPLY', i['Receive Shadow'], 0.5, x=-560, y=-120),
        x=-460, y=-120), x=-420, y=-250, label='t face - screen shadow')
    fmask = g.math('MULTIPLY', face, i['Face Mask'], x=-450, y=150, label='face region')
    t = g.mix(eye, t, 2.0, kind='FLOAT', x=-300, y=100)
    lit_b, s2_b = bands(g, i, t, base, 0.0, occ, i['Softness'])
    soft_f = g.mix(g.math('MULTIPLY', g.math('SUBTRACT', gsel, 0.5, x=-300, y=-1100), 2.5, x=-200, y=-1100, clamp=True),
                   i['Face Soft'], 0.03, kind='FLOAT', x=-100, y=-1100)
    lit_f, s2_f = bands(g, i, tf, base, 1.0, occ, soft_f)
    # blend the two lighting results as colours (like cross-fading band weights), not as thresholds
    lit = g.mix(fmask, lit_b, lit_f, x=1000, y=400)
    s2 = g.mix(fmask, s2_b, s2_f, kind='FLOAT', x=1000, y=300)
    sc, sp = specular(g, i, nrm, base, noteye)
    spec = g.vmath('SCALE', g.vmath('MULTIPLY', sc, sp, x=1000, y=-300).outputs[0],
                   g.math('MULTIPLY_ADD', i['Metal'], 4.0, 1.0, x=1050, y=-380), x=1100, y=-300).outputs[0]   # metal: highlights run far above 1
    r = rim(g, i, nrm, g.math('MULTIPLY', s2, noteye, x=1300, y=-600))
    rimt = g.vmath('MULTIPLY', i['Rim Color'], base, x=1400, y=-780).outputs[0]   # tinted by albedo
    rimc = g.vmath('MULTIPLY', rimt, g.math('MULTIPLY', r, i['Rim Strength'], x=1400, y=-700), x=1500, y=-700).outputs[0]
    diff = g.vmath('SCALE', lit, g.math('SUBTRACT', 1.0, g.math('MULTIPLY', i['Metal'], 0.8, x=1000, y=-100), x=1100, y=-100), x=1200, y=0)
    pre = g.vmath('ADD', diff.outputs[0], spec, x=1300, y=0).outputs[0]
    scr = g.n('ShaderNodeMix', 1400, 0, data_type='RGBA', blend_type='SCREEN', label='rim screen')
    scr.inputs[0].default_value = 1.0   # screen blend: rim can never push colour past white
    g.L(pre, scr.inputs[6])
    g.L(rimc, scr.inputs[7])
    tot = scr.outputs[2]
    tot = matcap(g, i, tot, noteye)
    sepb = g.n('ShaderNodeSeparateColor', 1700, -640, label='albedo max')
    g.L(base, sepb.inputs[0])
    mxc = g.math('MAXIMUM', g.math('MAXIMUM', sepb.outputs[0], sepb.outputs[1], x=1760, y=-640), sepb.outputs[2], x=1820, y=-640)
    invm = g.math('DIVIDE', 1.0, g.math('MAXIMUM', mxc, 0.05, x=1860, y=-660), x=1900, y=-660)
    tintn = g.vmath('SCALE', base, invm, x=1950, y=-660).outputs[0]   # same hue/saturation, brightness 1
    mnc = g.math('MINIMUM', g.math('MINIMUM', sepb.outputs[0], sepb.outputs[1], x=1760, y=-700), sepb.outputs[2], x=1820, y=-700)
    sat = g.math('MULTIPLY', g.math('SUBTRACT', mxc, mnc, x=1900, y=-700), invm, x=1960, y=-700, label='albedo saturation')
    gate = g.math('MULTIPLY', g.smooth(sat, 0.3, 0.65, x=2020, y=-700), i['Chrome Tint'], x=2080, y=-700)   # only clearly coloured metal (gold) takes a hue
    bright = g.mix(0.6, 1.0, mxc, kind='FLOAT', x=2080, y=-760)                                           # dark metal reflects less
    kh = g.n('ShaderNodeHueSaturation', 2100, -820, label='gold deepen')       # coloured metal: richer and darker than its plain albedo
    kh.inputs['Saturation'].default_value = 1.45
    kh.inputs['Value'].default_value = 0.87
    kh.inputs['Hue'].default_value = 0.49   # a touch warmer: pure gold, not green-gold
    g.L(base, kh.inputs['Color'])
    keep = kh.outputs[0]
    tint_c = g.vmath('SCALE', g.mix(gate, WHITE, keep, x=2140, y=-660), bright, x=2200, y=-660).outputs[0]
    # chrome: where the surface is metal and has a matcap, show the reflection (tinted by albedo, dimmed in shade)
    shade = g.mix(s2, (0.65, 0.65, 0.65, 1), WHITE, x=1950, y=-500)
    refl = g.vmath('MULTIPLY', g.vmath('MULTIPLY', i['MatCap'], tint_c,
                                       x=1900, y=-520).outputs[0], g.vmath('SCALE', shade, 1.3, x=1960, y=-480).outputs[0], x=2000, y=-520).outputs[0]
    cw = g.math('MULTIPLY', g.math('MULTIPLY', g.smooth(i['Metal'], 0.6, 0.9, x=1850, y=-540, label='real metal only'), g.math('MINIMUM', g.math('MULTIPLY', i['MatCap Alpha'], 3.0, x=1800, y=-560), 1.0, x=1850, y=-560), x=1900, y=-560),
                g.math('MULTIPLY', i['Chrome'], noteye, x=1900, y=-600), x=1950, y=-600, clamp=True, label='chrome amount')
    refl = g.vmath('MAXIMUM', refl, g.vmath('SCALE', tot, 0.8, x=2050, y=-560).outputs[0], x=2100, y=-520).outputs[0]   # matcap rims never go darker than the plain shading
    tot = g.mix(cw, tot, refl, x=2050, y=-300)
    eyec = g.n('ShaderNodeHueSaturation', 2050, 150, label='eye saturation')
    g.L(i['Eye Saturation'], eyec.inputs['Saturation'])
    g.L(tot, eyec.inputs['Color'])
    skh = g.n('ShaderNodeHueSaturation', 2050, 300, label='skin saturation')   # skin reads a little less pink than the game's -> small saturation lift on skin only
    g.L(g.math('ADD', g.math('MULTIPLY', i['Skin Mask'], 0.09, x=1950, y=300), 1.0, x=2000, y=300), skh.inputs['Saturation'])
    g.L(grade(g, i, tot), skh.inputs['Color'])
    out = g.mix(eye, skh.outputs[0], eyec.outputs[0], x=2100, y=0)   # eyes keep their painted colours
    dbg = {'t': t, 's2': s2, 'rim': r, 'spec': sp, 'occ': occ, 'tf': tf,
           'rimc': g.math('MULTIPLY', g.vmath('LENGTH', rimc, x=2200, y=-1050).outputs['Value'], 1.0, x=2300, y=-1050),
           'lit': g.vmath('LENGTH', lit, x=2200, y=-1100).outputs['Value'],
           'sd': g.math('MULTIPLY', rim.sd, 0.2, x=2200, y=-900),
           'own': g.math('MULTIPLY', rim.own, 0.2, x=2200, y=-950),
           'diff': g.math('MULTIPLY', rim.diff, 10.0, x=2200, y=-1000),
           'nose': nose, 'seen': seen, 'nal': i['Nose Alpha'], 'gs': gsel, 'sdf': g._dbg['sdf'], 'ang': g._dbg['ang'], 'fm': fmask, 's2f': s2_f, 'metal': i['Metal'], 'mca': i['MatCap Alpha'], 'cw': cw,
           'mcl': g.vmath('LENGTH', i['MatCap'], x=2200, y=-1150).outputs['Value'],
           }.get('')
    if dbg is not None:   # developer aid: show one scalar as grey
        cc = g.n('ShaderNodeCombineColor', 2300, 300)
        for k in range(3):
            g.L(dbg, cc.inputs[k])
        out = cc.outputs[0]
    em = g.n('ShaderNodeEmission', 2200, 100)
    g.L(out, em.inputs['Color'])
    tr = g.n('ShaderNodeBsdfTransparent', 2200, -50)
    ms = g.n('ShaderNodeMixShader', 2400, 50)
    g.L(i['Alpha'], ms.inputs[0])
    g.L(tr.outputs[0], ms.inputs[1])
    g.L(em.outputs[0], ms.inputs[2])
    # multiply mode (eye shadow / tint overlays): transparent BSDF colour darkens what is behind
    mt = g.n('ShaderNodeBsdfTransparent', 2200, -150, label='multiply overlay')
    g.L(g.mix(i['Alpha'], WHITE, out, x=2100, y=-150), mt.inputs['Color'])
    mm = g.n('ShaderNodeMixShader', 2550, 50)
    g.L(i['Multiply Mode'], mm.inputs[0])
    g.L(ms.outputs[0], mm.inputs[1])
    g.L(mt.outputs[0], mm.inputs[2])
    g.L(mm.outputs[0], go.inputs['Shader'])
    g.L(out, go.inputs['Color'])
    # AOV payloads are Core outputs; the wrapper group writes (and masks) the real AOV nodes per material
    one = g.n('ShaderNodeValue', 2400, 300, label='Avatar mask')
    one.outputs[0].default_value = 1.0
    g.L(one.outputs[0], go.inputs['Avatar'])
    vt = g.n('ShaderNodeVectorTransform', 2400, 450, vector_type='VECTOR', convert_from='WORLD', convert_to='CAMERA', label='Normal AOV')
    g.L(geo.outputs['Normal'], vt.inputs[0])
    g.L(vt.outputs[0], go.inputs['AOV Normal'])
    toward = g.math('MAXIMUM', g.vmath('DOT_PRODUCT', geo.outputs['Normal'], i['Light Dir'], x=2000, y=-900).outputs['Value'], 0.0, x=2100, y=-900)
    toward = g.math('POWER', toward, 2.0, x=2200, y=-900)   # the rim only appears where the surface faces the light
    gate_l = g.math('MULTIPLY', g.math('MULTIPLY', g.math('MULTIPLY', s2, noteye, x=2300, y=-850), toward, x=2300, y=-900), i['Rim AOV Strength'], x=2350, y=-850)   # lit side only, like the template's N.L / shadow gating
    g.L(g.vmath('SCALE', rimt, gate_l, x=2400, y=-800).outputs[0], go.inputs['AOV Rim'])
    return ng


if __name__ == '__main__':
    ng = build()
    print('BUILT', len(ng.nodes), 'nodes', len(ng.interface.items_tree), 'iface items')


