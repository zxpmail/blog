# 测试: is_even(n) - 人工预先编写
# 覆盖: 正常输入、边界值、特殊值
import sys
sys.path.insert(0, '.')
from code_solution import is_even

# 正常输入
assert is_even(4) == True, "偶数应返回 True"
assert is_even(3) == False, "奇数应返回 False"

# 边界值
assert is_even(0) == True, "0 是偶数"
assert is_even(1) == False, "1 是奇数"
assert is_even(-2) == True, "负偶数"
assert is_even(-1) == False, "负奇数"

# 大数
assert is_even(1000000) == True
assert is_even(1000001) == False

print("ALL PASSED")
