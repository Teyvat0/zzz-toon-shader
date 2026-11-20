"""ZZZ_Toon_Maps: decodes the game's data textures into plain floats/vectors
for ZZZ_Toon_Core.  (LightTex RG=tangent normal xy, B=shade bias;
OtherData R=material id, G=metal, B=spec mask; OtherData2 R=AO, G=smooth.)
"""
import bpy
from .toon_lib import G

NAME = 'ZZZ_Toon_Maps'
C, F, V = 'NodeSocketColor', 'NodeSocketFloat', 'NodeSocketVector'
INS = [('Light Tex', C, (0.5, 0.5, 0.5, 1)), ('Other Data', C, (0, 0, 0, 1)),
       ('Other Data 2', C, (1, 1, 1, 1)), ('Bump Scale', F, 1.0)]
OUTS = [('Normal', V), ('Shade Bias', F), ('AO', F), ('Metal', F),
        ('Spec Mask', F), ('Smooth', F), ('ID', F), ('MatCap Mask', F), ('MatCap UV', V)]


def build():
    ng = bpy.data.node_groups.get(NAME) or bpy.data.node_groups.new(NAME, 'ShaderNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    for n, t, d in INS:
        ng.interface.new_socket(n, in_out='INPUT', socket_type=t).default_value = d
    for n, t in OUTS:
        ng.interface.new_socket(n, in_out='OUTPUT', socket_type=t)
    g = G(ng)
    gi, go = g.n('NodeGroupInput', -900, 0), g.n('NodeGroupOutput', 700, 0)
    i, o = gi.outputs, go.inputs

    def sep(sock, y):
        s = g.n('ShaderNodeSeparateColor', -700, y)
        g.L(sock, s.inputs[0])
        return s.outputs
    L, M, A = sep(i['Light Tex'], 200), sep(i['Other Data'], 0), sep(i['Other Data 2'], -200)
    x = g.math('SUBTRACT', g.math('MULTIPLY', L[0], 2.0, x=-500, y=300), 1.0, x=-400, y=300)
    y = g.math('SUBTRACT', g.math('MULTIPLY', L[1], 2.0, x=-500, y=240), 1.0, x=-400, y=240)
    r2 = g.math('ADD', g.math('MULTIPLY', x, x, x=-300, y=300),
                g.math('MULTIPLY', y, y, x=-300, y=240), x=-200, y=270)
    z = g.math('SQRT', g.math('SUBTRACT', 1.0, r2, x=-100, y=270, clamp=True), x=0, y=270)
    comb = g.n('ShaderNodeCombineColor', 100, 270)
    g.L(L[0], comb.inputs[0])
    g.L(L[1], comb.inputs[1])
    g.L(g.math('MULTIPLY_ADD', z, 0.5, 0.5, x=0, y=200), comb.inputs[2])
    nm = g.n('ShaderNodeNormalMap', 300, 270)
    g.L(comb.outputs[0], nm.inputs['Color'])
    g.L(i['Bump Scale'], nm.inputs['Strength'])
    g.L(nm.outputs[0], o['Normal'])
    # matcap lookup coordinate (radius .46: silhouette normals stay inside the image disc, no black edge ring)
    # was: = view-space normal remapped to 0..1
    vn = g.n('ShaderNodeVectorTransform', 450, 400, vector_type='NORMAL',
             convert_from='WORLD', convert_to='CAMERA')
    g.L(nm.outputs[0], vn.inputs[0])
    uv = g.vmath('MULTIPLY_ADD', vn.outputs[0], (0.46, 0.46, 0.0), (0.5, 0.5, 0.0), x=600, y=400)
    g.L(uv.outputs[0], o['MatCap UV'])
    g.L(A[2], o['MatCap Mask'])
    g.L(g.math('MULTIPLY', g.math('SUBTRACT', L[2], 0.5, x=300, y=150), 4.0, x=450, y=150), o['Shade Bias'])   # (2B-1)*2: painted shade strength
    for name, src in (('AO', A[0]), ('Smooth', A[1]), ('ID', M[0]),
                      ('Metal', M[1]), ('Spec Mask', M[2])):
        g.L(src, o[name])
    return ng


if __name__ == '__main__':
    print('MAPS', len(build().nodes))
