# 测试: fizzbuzz(n) - 人工预先编写
import sys
sys.path.insert(0, '.')
from code_solution import fizzbuzz

r5 = fizzbuzz(5)
assert r5 == [1, 2, 'Fizz', 4, 'Buzz'], f"fizzbuzz(5)={r5}"

r15 = fizzbuzz(15)
assert r15[2] == 'Fizz'  # 3
assert r15[4] == 'Buzz'  # 5
assert r15[14] == 'FizzBuzz'  # 15

r0 = fizzbuzz(0)
assert r0 == [], f"fizzbuzz(0)={r0}"

r1 = fizzbuzz(1)
assert r1 == [1], f"fizzbuzz(1)={r1}"

print("ALL PASSED")
