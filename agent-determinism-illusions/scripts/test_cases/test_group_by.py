# 测试: group_by_first_letter(strings) - 人工预先编写
import sys
sys.path.insert(0, '.')
from code_solution import group_by_first_letter

r = group_by_first_letter(["apple","banana","avocado","cherry","blueberry"])
assert 'a' in r
assert 'b' in r
assert 'c' in r
assert 'apple' in r['a']
assert 'avocado' in r['a']
assert set(r['a']) == {'apple', 'avocado'}
assert set(r['b']) == {'banana', 'blueberry'}
assert set(r['c']) == {'cherry'}

# 空列表
assert group_by_first_letter([]) == {}

# 单元素
r2 = group_by_first_letter(["hello"])
assert r2 == {'h': ['hello']}

print("ALL PASSED")
