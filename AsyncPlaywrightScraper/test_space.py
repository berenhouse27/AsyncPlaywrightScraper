import re




pattern1 = r'/\d{4}(/|-)?\d{2}((/|-)?\d{2})?(/|-)?'
pattern2 = r'/\d{2}([/-])?\d{2}(([/-])?\d{4})?([/-])?'

tests = ['/20250715', '/2025/07/15', '20250715', '2025 07 15', '2025-07-15', '/2025-07-15', '/07-15-2025', '/07/15/2025',
         '07/15/2025', '/07152025', '07-15-2025', '/07 15 2025']

for test in tests:
    print(f"pat1 {test}: {bool(re.match(pattern1, test))}")
    print(f"pat2 {test}: {bool(re.match(pattern2, test))}")
