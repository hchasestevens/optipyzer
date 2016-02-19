"""
Tests for optipyzer/main.py
"""

import pytest

import optipyzer


@pytest.mark.parametrize('code,expected', (
    ('x = obj()\nl = list()\nfor (a, b), c in i:\n  d = x.a1\n  l.append(x.a2 + d)\n', 'abcd'),
    ('for x in y: a, (b, c) = d', 'xabc'),
))
def test_get_for_locals(code, expected):
    """
    Test for get_for_locals.
    """
    for_node = ast.parse(code).body
    assert set(optipyzer.get_for_locals(module_body)[0]) == set(expected)


@pytest.mark.parametrize('code,expected', (
    ('for (a, b, (c,)) in iterable:\n  pass', 'abc'),
    ('for x in iterable:\n  y = 0', 'x'),
))
def test_target_names(code, expected):
    """
    Test for target_names.
    """
    for_target = ast.parse(code).body[0].target
    assert set(optipyzer.target_names(for_target)) == set(expected)
