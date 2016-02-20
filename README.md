OPTIPYZER
=========

Example 1
--------
**Before**:
```python
l1 = []
for j in xrange(10000):
  l2 = []
  for k in xrange(1000):
    l2.append(k)
    l1.append(None)
  l1.append(l2)
```
**After**:
```python
l1 = []
__l1_append = l1.append
for j in xrange(10000):
    l2 = []
    __l2_append = l2.append
    for k in xrange(1000):
        __l2_append(k)
        __l1_append(None)
    __l1_append(l2)
```
**27.5%** speed improvement (3.873s vs. 3.038s)

Example 2
-------

**Before**:
```python
x = obj()
l = list()
for (a, b), c in i:
  d = x.a1
  l.append(x.a2 + d)
y = obj()
for x in i2:
  l.append(x.i.j)
  for z in i3:
    l.append(y.i.j.k + x.i.j.k(z))
z = obj()
for a in b:
  print z.f().g
```
**After**:
```python
x = obj()
l = []
__l_append = l.append
__x_a1 = x.a1
__x_a2 = x.a2
for ((a, b), c) in i:
    d = __x_a1
    __l_append((__x_a2 + d))
y = obj()
__l_append = l.append
__y_i_j_k = y.i.j.k
for x in i2:
    __l_append(x.i.j)
    __x_i_j_k = x.i.j.k
    for z in i3:
        __l_append((__y_i_j_k + __x_i_j_k(z)))
z = obj()
__z_f = z.f
for a in b:
    print __z_f().g
```
