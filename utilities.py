import unicodedata


def get_display_rows_num(s: str) -> int:
    '''估算在手机上显示的纵向行数'''
    return sum((get_width(line)-1)//28+1 for line in s.splitlines())

def get_width(s: str) -> int:
    """估算 unicode 文本的显示宽度，英文字母 1 个单位，汉字 2 个单位"""
    widths = [
        (126,    1), (159,    0), (687,     1), (710,   0), (711,   1), 
        (727,    0), (733,    1), (879,     0), (1154,  1), (1161,  0), 
        (4347,   1), (4447,   2), (7467,    1), (7521,  0), (8369,  1), 
        (8426,   0), (9000,   1), (9002,    2), (11021, 1), (12350, 2), 
        (12351,  1), (12438,  2), (12442,   0), (19893, 2), (19967, 1),
        (55203,  2), (63743,  1), (64106,   2), (65039, 1), (65059, 0),
        (65131,  2), (65279,  1), (65376,   2), (65500, 1), (65510, 2),
        (120831, 1), (262141, 2), (1114109, 1),
    ]
    width = 0
    for c in s:
        o = ord(c)
        if o == 0xe or o == 0xf:
            width += 0
            continue
        for num, wid in widths:
            if o <= num:
                width += wid
                break
        if o > num:
            width += 1
    return width

def fuzzy_equal(a: str, b: str) -> bool:
    '''判断文本模糊相等，对大小写、全半角不敏感'''
    return unicodedata.normalize('NFKC', a).lower() == unicodedata.normalize('NFKC', b).lower()

def starts_with(msg: str, prefix: str) -> bool:
    '''判断文本是否以某个前缀开头，对大小写、全半角不敏感'''
    return fuzzy_equal(msg[:len(prefix)], prefix)
