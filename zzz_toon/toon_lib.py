"""Small helpers for building node groups by script (Goo Engine 4.4)."""
import bpy


class G:
    """Thin wrapper over a node tree: add nodes, link by socket or value."""

    def __init__(self, nt):
        self.nt = nt
        self.x = 0

    def n(self, idname, x=0, y=0, label=None, **props):
        node = self.nt.nodes.new(idname)
        node.location = (x, y)
        if label:
            node.label = label
        for k, v in props.items():
            setattr(node, k, v)
        return node

    def L(self, a, b):
        """Link output socket `a` to input socket `b`."""
        self.nt.links.new(a, b)

    def set(self, sock, v):
        """Set a socket constant or link a socket."""
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=None, c=None, x=0, y=0, clamp=False, label=None):
        m = self.n('ShaderNodeMath', x, y, label=label, operation=op,
                   use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.set(m.inputs[i], v)
        return m.outputs[0]

    def vmath(self, op, a, b=None, c=None, x=0, y=0, label=None):
        m = self.n('ShaderNodeVectorMath', x, y, label=label, operation=op)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.set(m.inputs[3 if (op == 'SCALE' and i == 1) else i], v)
        return m

    def mix(self, fac, a, b, x=0, y=0, kind='RGBA'):
        m = self.n('ShaderNodeMix', x, y, data_type=kind)
        i = {'RGBA': (6, 7, 2), 'FLOAT': (2, 3, 0), 'VECTOR': (4, 5, 1)}[kind]
        self.set(m.inputs[0], fac)
        self.set(m.inputs[i[0]], a)
        self.set(m.inputs[i[1]], b)
        return m.outputs[i[2]]

    def smooth(self, v, lo, hi, x=0, y=0, label=None):
        """smoothstep(lo, hi, v) via Map Range (float)."""
        m = self.n('ShaderNodeMapRange', x, y, label=label,
                   interpolation_type='SMOOTHSTEP', data_type='FLOAT',
                   clamp=True)
        self.set(m.inputs[0], v)
        self.set(m.inputs[1], lo)
        self.set(m.inputs[2], hi)
        return m.outputs[0]
