import ast
import astor
import astoptimizer


DEFAULT_ASTOPTIMIZER_CONFIG = astoptimizer.Config('builtin_funcs', 'pythonbin')  # Might need to do away with builtin_funcs if we're writing back to file...


def compare_optimized(fname, config=DEFAULT_ASTOPTIMIZER_CONFIG, show_ast=True):
    """
    Compare astoptimizer version of code against unoptimized.
    """
    with open(fname, 'r') as f:
        contents = f.read()
    print_fn = astor.dump if show_ast else astor.codegen.to_source
    m = ast.parse(contents)
    a = print_fn(m)
    m_opt = astoptimizer.optimize_ast(m, config)
    b = print_fn(m_opt)
    print '\n'.join(difflib.context_diff(a.splitlines(), b.splitlines()))


def target_names(target):
    if isinstance(target, ast.Name):
        return [target.id]
    return [name for elt in target.elts for name in target_names(elt)]


def test_target_names():
    """
    test for target_names
    """
    f = '''\nfor (a, b, (c,)) in iterable:\n      pass'''
    assert set(target_names(ast.parse(f).body[0].target)) == {'a', 'b', 'c'}
    g = '''for x in iterable:\n      y = 0'''
    assert set(target_names(ast.parse(g).body[0].target)) == {'x'}


def get_for_locals(body):
    """
    Get the local-scope variables for each for loop in body.
    """
    for_locals = []
    for node in body:
        if not isinstance(node, ast.For):
            continue
        target_vars = frozenset(target_names(node.target))
        assignments = frozenset(
            name
            for subnode in node.body
            if isinstance(subnode, ast.Assign)
            for target in subnode.targets
            for name in target_names(target)
        )
        for_locals.append(target_vars | assignments)
    return for_locals


def test_get_for_locals():
    """
    test for get_for_locals.
    """
    d = '''x = object()\nl = list()\nfor (a, b), c in zip(zip(xrange(10), xrange(10)), xrange(10)):\n      d = x.attr1\n      l.append(x.attr2 + d)\n'''
    d_module_body = ast.parse(d).body
    assert set(get_for_locals(d_module_body)[0]) == {'a', 'b', 'c', 'd'}
    e = '''for x in y: a, (b, c) = d'''
    e_module_body = ast.parse(e).body
    assert set(get_for_locals(e_module_body)[0]) == {'x', 'a', 'b', 'c'}


class ForTransformer(ast.NodeTransformer):
    """
    Transform for based on known locals.
    """
    def __init__(self, known_locals, *args, **kwargs):
        self.known_locals = known_locals
        self.prepend_assignments = []
        return super(ForTransformer, self).__init__(*args, **kwargs)

    def _is_nested_attr(self, node):
        if isinstance(node.value, ast.Name):
            return node.value.id  # so we can check for locality
        elif isinstance(node.value, ast.Attribute):
            return self._is_nested_attr(node.value)
        return None

    def _get_attr_varname(self, node):
        if isinstance(node, ast.Name):
            return node.id
        return self._get_attr_varname(node.value) + '_' + node.attr

    def visit_Attribute(self, node):
        base_name = self._is_nested_attr(node)
        if base_name in self.known_locals:  # None should not be
            return node  # Surely we want to dig into this a bit, though...
        var_name = '__{}'.format(self._get_attr_varname(node))
        new_assignment = ast.Assign(
            targets=[ast.Name(id=var_name)],
            value=node,
        )
        self.prepend_assignments.append(new_assignment)
        return ast.Name(id=var_name)

    # Might need to override visit_For to handle nesting properly...


def optimize(module, config=DEFAULT_ASTOPTIMIZER_CONFIG):
    """
    Restructure AST as best as possible for speed improvements.
    """
    # Drag attribute accesses on items from outer scope in for-loops to outer scope
    pass

    # Final pass: use astoptimizer
    module = astoptimizer.optimize_ast(module, config)

    return module