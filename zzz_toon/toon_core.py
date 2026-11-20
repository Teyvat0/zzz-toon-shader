"""ZZZ-style toon core node group for Goo Engine 4.4 (own design).

Run inside Blender: creates node group 'ZZZ_Toon_Core'.
Light model: scalar N.L from Goo ShaderInfo (any light/shadow works),
3-band toon, optional face SDF, toon spec, screen-space rim, tone curve.
"""
import bpy, math
from .toon_lib import G

NAME = 'ZZZ_Toon_Core'
F, C, V, I = 'NodeSocketFloat', 'NodeSocketColor', 'NodeSocketVector', 'NodeSocketInt'

# (panel, name, type, default, min, max)
INPUTS = [
    ('Surface', 'Base Color', C, (0.8, 0.8, 0.8, 1), 0, 1),
    ('Surface', 'Alpha', F, 1.0, 0, 1),
    ('Surface', 'Domain', I, 3, 1, 3),          # 1 face, 2 eye, 3 body
    ('Surface', 'Model Scale', F, 1.0, 0.1, 10),  # 1 = metres; scales contact-shadow / rim reach
    ('Surface', 'Multiply Mode', F, 0.0, 0, 1),  # 1: darken the backdrop (eye shadow overlay)
    ('Surface', 'Normal', V, (0, 0, 0), -1, 1),
    ('Surface', 'Normal Blend', F, 1.0, 0, 1),  # lightmap normal vs geometry normal
    ('Shade', 'Shade Bias', F, 0.0, -1, 1),
    ('Shade', 'AO', F, 1.0, 0, 1),
    ('Shade', 'Receive Shadow', F, 1.0, 0, 1),
    ('Shade', 'Light Edge', F, 0.665, 0, 1),
    ('Shade', 'Softness', F, 0.03, 0.001, 0.5),
    ('Shade', 'Shadow Depth', F, 0.33, 0.02, 1),
    ('Shade', 'Lit Bleed', F, 0.0, 0, 1),
    ('Shade', 'Shade Gain', F, 1.0, 0, 3),
    ('Shade', 'Shallow Tint', C, (0.78, 0.66, 0.72, 1), 0, 1),
    ('Shade', 'Deep Tint', C, (0.52, 0.42, 0.55, 1), 0, 1),
    ('Shade', 'Terminator Glow', C, (1.0, 0.88, 0.8, 1), 0, 1),
    ('Shade', 'Detail Dark', F, 0.15, 0, 2),
    ('Shade', 'Glow Amount', F, 1.0, 0, 1),
    ('Shade', 'Skin Mask', F, 0.0, 0, 1),        # 1 on skin (face / material id 0): shade colours get a little more saturation
    ('Specular', 'Spec Mask', F, 0.0, 0, 1),
    ('Specular', 'Spec Size', F, 0.6, 0, 1),
    ('Specular', 'Spec Color', C, (1, 1, 1, 1), 0, 1),
    ('Specular', 'Chrome', F, 1.0, 0, 2),        # metal looks like its matcap (studio reflection) instead of grey diffuse
    ('Specular', 'Chrome Tint', F, 1.0, 0, 1),   # 1: reflection takes the albedo hue at full brightness (gold stays gold)
    ('Specular', 'Metal', F, 0.0, 0, 1),
    ('Specular', 'Hair Spec', F, 0.0, 0, 1),    # >0 switches to the hair highlight model; value = strength
    ('Specular', 'Hair Soft', F, 0.5, 0.01, 0.5),
    ('Specular', 'Head Sphere', F, 0.1, 0, 1),  # metres (x Model Scale): head-sphere normals inside this radius
    ('Rim', 'Rim Strength', F, 0.18, 0, 2),
    ('Rim', 'Rim Width', F, 0.6, 0, 5),
    ('Rim', 'Rim Color', C, (1, 1, 1, 1), 0, 1),
    ('Rim', 'Rim AOV Strength', F, 0.18, 0, 4),   # colour handed to the compositor's screen-space rim (soft, lit side only); 0 = off
    ('Face', 'Face SDF', F, 0.5, 0, 1),
    ('Face', 'Face SDF Mirror', F, 0.5, 0, 1),
    ('Face', 'Light Dir', V, (0.3, -0.6, 0.7), -1, 1),
    ('Face', 'Face Soft', F, 0.05, 0.01, 0.5),   # edge softness of the face shadow
    ('Face', 'Face Edge Mirror', F, 0.0, 0, 1),
    ('Face', 'Nose Shade', F, 1.0, 0, 2),        # strength of the painted nose shadow (SDF green blob), only when the light is off to the side
    ('Face', 'Face Edge', F, 0.0, 0, 1),         # SDF green: high = crisp shadow edge (nose, lip) instead of the soft cheek gradient
    ('Face', 'Face Mask', F, 1.0, 0, 1),        # SDF alpha: 0 outside the lit face area (jaw, neck) -> body lighting
    ('Face', 'Face Bias', F, 0.0, -0.5, 0.5),
    ('Face', 'Face Shadow', F, 1.0, 0, 1),      # scales the game's face threshold 1-|light angle|
    ('Face', 'Head Forward', V, (0, -1, 0), -1, 1),
    ('Face', 'Head Right', V, (-1, 0, 0), -1, 1),
    ('Face', 'Head Center', V, (0, 0, 1.4), -100, 100),
    ('Face', 'Nose Line', F, 1.0, 0, 1),         # strength of the nose-tip line (0 = off)
    ('Face', 'Nose Alpha', F, 1.0, 0, 1),        # face texture alpha: <1 marks the painted nose-tip texels
    ('Face', 'Nose Front', F, 0.92, 0, 1),       # view must be this close to head-forward (looking level)
    ('Face', 'Nose Down', F, 0.62, 0, 1),        # same threshold when looking down on the face
    ('Face', 'Nose Color', C, (0.22, 0.08, 0.07, 1), 0, 1),
    ('MatCap', 'MatCap', C, (0, 0, 0, 1), 0, 1),
    ('MatCap', 'MatCap Alpha', F, 0.0, 0, 1),   # amount (alpha burst x mask)
    ('MatCap', 'MatCap Mode', F, 2.0, 0, 2),    # 0 lerp, 1 add, 2 overlay
    ('Grade', 'Eye Saturation', F, 1.0, 0, 2),
    ('Grade', 'Tone Curve', F, 0.15, 0, 1),
    ('Grade', 'Saturation', F, 1.0, 0, 2),
    ('Grade', 'Exposure', F, 0.93, 0, 4),
]
OUTPUTS = [('Shader', 'NodeSocketShader'), ('Color', C), ('Avatar', F), ('AOV Normal', C), ('AOV Rim', C)]


def make_interface(ng):
    ng.interface.clear()
    panels = {}
    for pn, name, st, dv, lo, hi in INPUTS:
        if pn not in panels:
            panels[pn] = ng.interface.new_panel(pn, default_closed=pn != 'Surface')
        s = ng.interface.new_socket(name, in_out='INPUT', socket_type=st,
                                    parent=panels[pn])
        s.default_value = dv
        if st in (F, I):
            s.min_value, s.max_value = lo, hi
        if name == 'Normal':
            s.hide_value = True   # unlinked = zero vector -> geometry normal
    for name, st in OUTPUTS:
        ng.interface.new_socket(name, in_out='OUTPUT', socket_type=st)
