import ast
import copy
import difflib

import astor
import astoptimizer
import operator


DEFAULT_ASTOPTIMIZER_CONFIG = astoptimizer.Config('builtin_funcs',)  # Might need to do away with builtin_funcs if we're writing back to file...

class OPTIMIZATIONS:
    ATTRIBUTE_ACCESS_LIFTING = "Lifts repeated attribute accesses out of for loop bodies and into the outer scope."


def compare_optimized(code, config=DEFAULT_ASTOPTIMIZER_CONFIG, show_ast=True):
    """
    Compare astoptimizer version of code against unoptimized.
    """
    print_fn = astor.dump if show_ast else astor.codegen.to_source
    m = ast.parse(code)
    a = print_fn(m)
    m_opt = optimize(m, config=config)
    b = print_fn(m_opt)
    print '\n'.join(difflib.context_diff(a.splitlines(), b.splitlines()))


class ForTransformer(ast.NodeTransformer):
    """
    Transform Fors in body.
    """
    @staticmethod
    def _tidy_prepends(assignments):
        """
        Ensure uniqueness of and sort prepend assignments.
        """
        str_reps = {assignment: astor.dump(assignment) for assignment in assignments}
        ass_str_rep_set = set()
        final_assignments = []
        for assignment, str_rep in str_reps.iteritems():
            if str_rep in ass_str_rep_set:
                continue
            final_assignments.append(assignment)
            ass_str_rep_set.add(str_rep)
        return sorted(final_assignments, key=str_reps.get)

    @staticmethod
    def _target_names(target):
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, (ast.Attribute, ast.Subscript)):
            return ForTransformer._target_names(target.value)
        return [
            name 
            for elt in target.elts 
            for name in ForTransformer._target_names(elt)
        ]

    @staticmethod
    def _get_body_locals(node):
        assignments = set(
            name
            for subnode in node.body
            if isinstance(subnode, ast.Assign)
            for target in subnode.targets
            for name in ForTransformer._target_names(target)
        )
        if isinstance(node, ast.With) and node.optional_vars:
            assignments |= {node.optional_vars.id}
        body_subnode_asignments = (
            ForTransformer._get_body_locals(subnode) 
            for subnode in node.body 
            if hasattr(subnode, 'body') 
            and not isinstance(subnode, ast.For)
        )
        return reduce(operator.or_, body_subnode_asignments, assignments)

    @staticmethod
    def _get_for_locals(for_node):
        """
        Get the local-scope variables from for node.
        """
        target_vars = frozenset(ForTransformer._target_names(for_node.target))
        assignments = ForTransformer._get_body_locals(for_node)
        return target_vars | assignments

    def visit_For(self, node):
        node.body = [ForTransformer().visit(subnode) for subnode in node.body]
        transformer = ForAttrTransformer(self._get_for_locals(node))
        new_for = transformer.visit(node)
        return ast.If(
            test=ast.Num(n=1),  # astoptimizer will get rid of this for us!
            body=self._tidy_prepends(transformer.prepend_assignments) + [new_for],
            orelse=[],
        )


class ForAttrTransformer(ast.NodeTransformer):
    """
    Transform body of For based on known locals.
    """
    def __init__(self, known_locals, *args, **kwargs):
        self.known_locals = known_locals
        self.prepend_assignments = []
        return super(ForAttrTransformer, self).__init__(*args, **kwargs)

    @staticmethod
    def _is_nested_attr(node):
        if isinstance(node.value, ast.Name):
            return node.value.id  # so we can check for locality
        elif isinstance(node.value, ast.Attribute):
            return ForAttrTransformer._is_nested_attr(node.value)
        return None

    @staticmethod
    def _get_attr_varname(node):
        if isinstance(node, ast.Name):
            return node.id
        return ForAttrTransformer._get_attr_varname(node.value) + '_' + node.attr

    def visit_Assign(self, node):
        return ast.Assign(
            targets=node.targets,  # We may want to break out sections of deeply-nested attributes... actually, do visit on all but outermost layer.
            value=self.visit(node.value)
        )

    def visit_AugAssign(self, node):
        return ast.AugAssign(
            target=node.target,  # see visit_Assign
            op=node.op,
            value=self.visit(node.value)
        )

    def visit_Attribute(self, node):
        base_name = self._is_nested_attr(node)
        if base_name in self.known_locals:
            return node
        if base_name is None:
            transformer = ForAttrTransformer(self.known_locals)
            transformer.visit(node.value)
            self.prepend_assignments.extend(transformer.prepend_assignments)
            return node
        var_name = '__{}'.format(self._get_attr_varname(node))
        new_assignment = ast.Assign(
            targets=[ast.Name(id=var_name)],
            value=node,
        )
        self.prepend_assignments.append(new_assignment)
        return ast.Name(id=var_name)


class ForAssignmentTransformer(ast.NodeTransformer):
    """Transformer to remove identity assignments introduced by ForTransformer."""
    def visit_Assign(self, node):
        if len(node.targets) == 1:
            target, = node.targets
            value = node.value
            if isinstance(target, ast.Name) and isinstance(value, ast.Name):
                if target.id == value.id:
                    return ast.Pass()
        return node


def optimize(module, allowed_optimizations=None, config=DEFAULT_ASTOPTIMIZER_CONFIG,):
    """
    Restructure AST as best as possible for speed improvements.
    """
    if allowed_optimizations is None:
        allowed_optimizations = frozenset(OPTIMIZATIONS.__dict__.itervalues())
    else:
        allowed_optimizations = frozenset(allowed_optimizations)

    if OPTIMIZATIONS.ATTRIBUTE_ACCESS_LIFTING in allowed_optimizations:
        # Drag attribute accesses on items from outer scope in for-loops to outer scope
        ForTransformer().visit(module)
        ForAssignmentTransformer().visit(module)

    # Final pass: use astoptimizer
    return astoptimizer.optimize_ast(module, config)
