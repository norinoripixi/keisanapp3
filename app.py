# app.py
# -*- coding: utf-8 -*-

import os
import math
import random
import fractions
import re
from typing import List, Dict, Tuple, Union

import pandas as pd
import streamlit as st
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# ------------------------------------------------------------------------------
# ページ設定
# ------------------------------------------------------------------------------
st.set_page_config(page_title="算数ドリルジェネレータ", page_icon="🧮", layout="wide")

# ------------------------------------------------------------------------------
# 出題プリセット表
# ------------------------------------------------------------------------------
PRESET_TABLE: Dict[str, Dict[str, List[str]]] = {
    "小3": {
        "整数のたし算・ひき算": [
            "2桁・2項の和差算", "2桁・3項の和差算", "3桁・3項の和差算", "4桁・4項の和差算", "5桁・5項の和差算"
        ],
        "かけ算の筆算": [
            "2桁×1桁", "3桁×1桁", "2桁×2桁", "3桁×2桁", "3桁×3桁"
        ],
        "わり算（あまりあり）": [
            "2〜50", "10〜200", "50〜1000", "200〜5000", "1000〜20000"
        ],
    },
    "小4": {
        "大きな数と筆算": [
            "4桁・2項の和差算", "5桁・2項の和差算", "6桁・2項の和差算", "3桁・2項の積", "4桁・2項の積"
        ],
        "小数の四則": [
            "小数第1位の2項の和差算", "小数第2位の2項の和差算", "小数第1位の2項の積商算", "小数第2位の2項の積商算", "小数第1位の3項の和差積商混合算"
        ],
        "約数・倍数（計算）": [
            "30〜100くらいの小さい整数の公約数",   # L1: GCD
            "50〜200の整数の公約数",               # L2: GCD
            "素因数分解を意識した数（2桁〜3桁）",   # L3: GCD
            "3つの数の公倍数",                     # L4: LCM
            "3つの数の公約数"                      # L5: GCD
        ],
        "分数のたし算・ひき算": [
            "分母1桁・2項の和差算", "分母2桁・2項の和差算", "分母1桁・3項の和差算", "分母2桁・3項の和差算", "文章題"
        ],
    },
    "小5": {
        "分数の四則混合": ["frac_terms 2〜3", "同上", "3", "3", "3"],
        "小数×分数・分数×分数": ["frac_mixed", "同上", "同上", "同上", "同上"],
        "割合の基本計算": ["of/up/down", "同上", "reverse", "chain", "chain"],
        "比の基本計算": ["簡単比", "同上", "同上", "難易度高", "難易度高"],
    },
    "小6": {
        "分数・小数の複合計算": ["frac+decimal", "同上", "同上", "同上", "同上"],
        "逆算（□を求める）": ["基本", "同上", "同上", "同上", "同上"],
        "最大公約数・最小公倍数": ["簡単", "同上", "同上", "高難度", "高難度"],  # L1-3: GCD, L4-5: LCM
        "比例・反比例の基本計算": ["基本", "同上", "同上", "難易度高", "難易度高"],
    },
}

# ------------------------------------------------------------------------------
# ユーティリティ
# ------------------------------------------------------------------------------
def rand_int_with_digits(d: int) -> int:
    lo = 10 ** (d - 1)
    hi = 10 ** d - 1
    return random.randint(lo, hi)

def rand_nonzero(a: int, b: int) -> int:
    while True:
        x = random.randint(a, b)
        if x != 0:
            return x

def simplify_fraction(fr: fractions.Fraction) -> fractions.Fraction:
    return fractions.Fraction(fr.numerator, fr.denominator)

def format_fraction(fr: fractions.Fraction) -> str:
    if fr.denominator == 1:
        return str(fr.numerator)
    return f"{fr.numerator}/{fr.denominator}"

def lcm(a: int, b: int) -> int:
    return abs(a * b) // math.gcd(a, b)

def lcmm(*args: int) -> int:
    v = 1
    for x in args:
        v = lcm(v, x)
    return v

# ------------------------------------------------------------------------------
# PDF: 日本語フォント対応 + フォールバック
# ------------------------------------------------------------------------------
def find_japanese_font() -> Union[str, None]:
    """__file__ を基準に assets のフォントを確実に探す。無ければシステムの候補も見る。"""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "assets", "NotoSansJP-Regular.ttf"),
        os.path.join(here, "assets", "NotoSansJP-Regular.otf"),
        "assets/NotoSansJP-Regular.ttf",
        "assets/NotoSansJP-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return None

def ascii_safe(text: str) -> str:
    return text.encode("latin-1", "replace").decode("latin-1")

def to_bytes(x) -> bytes:
    if isinstance(x, (bytes, bytearray)):
        return bytes(x)
    return x.encode("latin-1", "ignore")

# ------------------------------------------------------------------------------
# PDF生成：1ページ目=問題、2ページ目=模範解答
# ------------------------------------------------------------------------------
def build_pdf(title: str, header_meta: Dict[str, str], problems: List[Dict]) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    font_path = find_japanese_font()
    use_unicode = False
    if font_path:
        try:
            pdf.add_font("JP", "", font_path, uni=True)
            pdf.set_font("JP", size=16)
            use_unicode = True
        except Exception:
            pdf.set_font("Helvetica", size=16)
    else:
        pdf.set_font("Helvetica", size=16)

    write = (lambda s: s) if use_unicode else ascii_safe

    # 1ページ目：問題
    pdf.add_page()
    pdf.cell(0, 10, text=write(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font_size(11)
    for k, v in header_meta.items():
        pdf.cell(0, 7, text=write(f"{k}: {v}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    pdf.set_font_size(12)
    for i, p in enumerate(problems, 1):
        q = p["question"]
        meta = p.get("meta", "")
        pdf.multi_cell(0, 7, text=write(f"Q{i}. {q}"))
        if meta:
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, text=write(f"（プリセット: {meta}）"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    # 2ページ目：解答
    pdf.add_page()
    pdf.set_font_size(16)
    pdf.cell(0, 10, text=write("模範解答"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font_size(12)
    for i, p in enumerate(problems, 1):
        a = p["answer"]
        pdf.cell(0, 6, text=write(f"Q{i}. {a}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return to_bytes(pdf.output(dest="S"))

# ------------------------------------------------------------------------------
# バリデーション（負数の除外、LCM=1除外、GCD=1除外）
# ------------------------------------------------------------------------------
def answer_is_negative(ans: str) -> bool:
    """負の答えかどうかを判定する。整数/小数/分数/『あまり』形式に対応。"""
    s = str(ans).strip()

    # 「q あまり r」形式（商を確認）
    if "あまり" in s:
        try:
            q_part = s.split("あまり")[0].strip()
            q_val = int(q_part)
            return q_val < 0
        except Exception:
            return s.startswith("-")

    # 比の a:b は非負のみを生成しているため除外対象外
    if ":" in s:
        return False

    # 分数
    if re.fullmatch(r"-?\d+/\d+", s):
        try:
            fr = fractions.Fraction(s)
            return fr < 0
        except Exception:
            return s.startswith("-")

    # それ以外は数値化して判定
    try:
        v = float(s)
        return v < -1e-12
    except Exception:
        return False

def is_lcm_context(grade: str, field: str, level: int) -> bool:
    """最小公倍数の文脈判定。"""
    if grade == "小4" and field == "約数・倍数（計算）" and level == 4:
        return True
    if grade == "小6" and field == "最大公約数・最小公倍数" and level >= 4:
        return True
    return False

def is_gcd_context(grade: str, field: str, level: int) -> bool:
    """最大公約数の文脈判定。"""
    if grade == "小4" and field == "約数・倍数（計算）" and level in (1, 2, 3, 5):
        return True
    if grade == "小6" and field == "最大公約数・最小公倍数" and level <= 3:
        return True
    return False

def lcm_answer_is_one(ans: str) -> bool:
    try:
        return int(str(ans).strip()) == 1
    except Exception:
        return False

def gcd_answer_is_one(ans: str) -> bool:
    try:
        return int(str(ans).strip()) == 1
    except Exception:
        return False

def generate_safe(gen_callable, *, grade: str, field: str, level: int, max_retry: int = 100) -> Tuple[str, str]:
    """ジェネレータを呼び、負の答え／LCM=1／GCD=1 を除外して再生成する。"""
    last = ("", "")
    for _ in range(max_retry):
        q, a = gen_callable()
        last = (q, a)
        # ② 負の答えの除外
        if answer_is_negative(a):
            continue
        # ① LCM=1 の除外
        if is_lcm_context(grade, field, level) and lcm_answer_is_one(a):
            continue
        # ③ GCD=1 の除外（今回の追加要件）
        if is_gcd_context(grade, field, level) and gcd_answer_is_one(a):
            continue
        return q, a
    # 最大リトライ後は最後の生成を返す（理論上ほぼ到達しない）
    return last

# ------------------------------------------------------------------------------
# 出題ジェネレータ群
# ------------------------------------------------------------------------------
def gen_sum_diff(digits: int, terms: int) -> Tuple[str, str]:
    nums = [rand_int_with_digits(digits) for _ in range(terms)]
    ops = [random.choice(["+", "-"]) for _ in range(terms - 1)]
    expr = str(nums[0])
    val = nums[0]
    for i, op in enumerate(ops, start=1):
        n = nums[i]
        if op == "+":
            val += n
        else:
            val -= n
        expr += f" {op} {n}"
    return f"{expr} =", str(val)

def gen_mul(a_digits: int, b_digits: int) -> Tuple[str, str]:
    a = rand_int_with_digits(a_digits)
    b = rand_int_with_digits(b_digits)
    return f"{a} × {b} =", str(a * b)

def gen_div_with_remainder(div_lo: int, div_hi: int) -> Tuple[str, str]:
    a = random.randint(div_lo, div_hi)
    b = rand_nonzero(2, max(2, min(9, a)))
    q, r = divmod(a, b)
    if r == 0:
        r = random.randint(1, b - 1)
        a = q * b + r
    return f"{a} ÷ {b} =", f"{q} あまり {r}"

def gen_large_sumdiff(digits: int) -> Tuple[str, str]:
    a = rand_int_with_digits(digits)
    b = rand_int_with_digits(digits)
    op = random.choice(["+", "-"])
    val = a + b if op == "+" else a - b
    return f"{a} {op} {b} =", str(val)

def gen_decimal_addsub(places: int) -> Tuple[str, str]:
    def r():
        return round(random.uniform(1, 100), places)
    a, b = r(), r()
    op = random.choice(["+", "-"])
    val = round(a + b, places + 1) if op == "+" else round(a - b, places + 1)
    return f"{a:.{places}f} {op} {b:.{places}f} =", f"{val}"

def gen_decimal_muldiv(places: int) -> Tuple[str, str]:
    def r():
        return round(random.uniform(0.5, 50), places)
    a, b = r(), r()
    op = random.choice(["×", "÷"])
    if op == "×":
        val = a * b
    else:
        b = b if b != 0 else r()
        val = a / b
    return f"{a:.{places}f} {op} {b:.{places}f} =", f"{round(val, places+2)}"

def gen_gcd_range(lo: int, hi: int, count: int = 2) -> Tuple[str, str]:
    nums = [random.randint(lo, hi) for _ in range(count)]
    g = 0
    for n in nums:
        g = math.gcd(g, n)
    return f"次の数の最大公約数を求めよ: {', '.join(map(str, nums))}", str(g)

def gen_lcm_range(lo: int, hi: int, count: int = 2) -> Tuple[str, str]:
    nums = [random.randint(lo, hi) for _ in range(count)]
    v = lcmm(*nums)
    return f"次の数の最小公倍数を求めよ: {', '.join(map(str, nums))}", str(v)

def gen_fraction_addsub(den_digits: int, terms: int) -> Tuple[str, str]:
    frs = []
    for _ in range(terms):
        den = rand_int_with_digits(den_digits)
        num = random.randint(1, den - 1)
        frs.append(fractions.Fraction(num, den))
    ops = [random.choice(["+", "-"]) for _ in range(terms - 1)]
    v = frs[0]
    expr = format_fraction(frs[0])
    for i, op in enumerate(ops, 1):
        if op == "+":
            v += frs[i]
            expr += f" + {format_fraction(frs[i])}"
        else:
            v -= frs[i]
            expr += f" - {format_fraction(frs[i])}"
    return f"{expr} =", format_fraction(simplify_fraction(v))

def gen_fraction_mixed() -> Tuple[str, str]:
    if random.choice([True, False]):
        a = round(random.uniform(0.1, 9.9), 1)
        den = random.randint(2, 12)
        num = random.randint(1, den - 1)
        val = a * (num / den)
        return f"{a} × {num}/{den} =", f"{round(val, 3)}"
    else:
        den1 = random.randint(2, 12); num1 = random.randint(1, den1 - 1)
        den2 = random.randint(2, 12); num2 = random.randint(1, den2 - 1)
        fr1 = fractions.Fraction(num1, den1)
        fr2 = fractions.Fraction(num2, den2)
        v = simplify_fraction(fr1 * fr2)
        return f"{format_fraction(fr1)} × {format_fraction(fr2)} =", format_fraction(v)

def gen_ratio_basic(hard: bool=False) -> Tuple[str, str]:
    a = random.randint(2, 30)
    b = random.randint(2, 30)
    g = math.gcd(a, b)
    if hard:
        return f"{a}:{b} を最も簡単な比に直せ。", f"{a//g}:{b//g}"
    else:
        k = random.randint(2, 9)
        return f"{a}:{b} を {k}倍した比を求めよ。", f"{a*k}:{b*k}"

def gen_percent_basic(mode: str) -> Tuple[str, str]:
    if mode in ("of", "up", "down"):
        base = random.randint(50, 500)
        p = random.choice([5, 10, 12, 20, 25, 30, 40, 50])
        if mode == "of":
            return f"{base} の {p}% は？", str(base * p / 100)
        elif mode == "up":
            return f"{base} を {p}% 増やすと？", str(round(base * (1 + p/100), 2))
        else:
            return f"{base} を {p}% 減らすと？", str(round(base * (1 - p/100), 2))
    elif mode == "reverse":
        p = random.choice([120, 150, 80, 75, 200])
        y = random.randint(100, 600)
        x = y * 100 / p
        return f"ある数の {p}% が {y}。元の数はいくつ？", f"{round(x, 2)}"
    else:  # chain
        base = random.randint(100, 800)
        p1 = random.choice([10, 20, 25]); p2 = random.choice([10, 20, 25])
        val = base * (1 + p1/100) * (1 - p2/100)
        return f"{base} を {p1}%増やし、その後 {p2}%減らすと？", f"{round(val, 2)}"

def gen_frac_mixed_ops(terms: int) -> Tuple[str, str]:
    frs = []
    for _ in range(terms):
        den = random.randint(2, 12)
        num = random.randint(1, den - 1)
        frs.append(fractions.Fraction(num, den))
    ops_all = ["+", "-", "×", "÷"]
    ops = [random.choice(ops_all) for _ in range(terms - 1)]
    v = frs[0]
    expr = format_fraction(frs[0])
    for i, op in enumerate(ops, 1):
        if op == "+":
            v = v + frs[i]
            expr += f" + {format_fraction(frs[i])}"
        elif op == "-":
            v = v - frs[i]
            expr += f" - {format_fraction(frs[i])}"
        elif op == "×":
            v = v * frs[i]
            expr += f" × {format_fraction(frs[i])}"
        else:
            v = v / frs[i]
            expr += f" ÷ {format_fraction(frs[i])}"
    return f"{expr} =", format_fraction(simplify_fraction(v))

def gen_frac_decimal_combo() -> Tuple[str, str]:
    if random.choice([True, False]):
        a = round(random.uniform(0.1, 9.9), 1)
        den = random.randint(2, 12)
        num = random.randint(1, den - 1)
        op = random.choice(["+", "-", "×", "÷"])
        val = eval(f"{a} { {'+':'+','-':'-','×':'*','÷':'/'}[op] } {num/den}")
        return f"{a} {op} {num}/{den} =", f"{round(val, 3)}"
    else:
        den = random.randint(2, 12)
        num = random.randint(1, den - 1)
        a = round(random.uniform(0.1, 9.9), 2)
        op = random.choice(["+", "-"])
        val = eval(f"{num/den} { {'+':'+','-':'-'}[op] } {a}")
        return f"{num}/{den} {op} {a} =", f"{round(val, 3)}"

def gen_inverse_basic() -> Tuple[str, str]:
    a = random.randint(2, 20)
    b = random.randint(2, 20)
    op = random.choice(["+", "-", "×", "÷"])
    if op == "+":
        x = b - a
    elif op == "-":
        x = b + a
    elif op == "×":
        x = b / a
    else:
        x = b * a
    return f"□ {op} {a} = {b} の □ を求めよ。", f"{x}"

def gen_prop_basic(hard: bool=False) -> Tuple[str, str]:
    mode = random.choice(["比例", "反比例"])
    if mode == "比例":
        k = random.randint(1, 9)
        x = random.randint(2, 20)
        y = k * x
        if hard:
            return f"y = kx。x={x} のとき y={y}。k を求めよ。", f"{k}"
        else:
            return f"y = {k}x。x={x} のとき y は？", f"{y}"
    else:
        k = random.randint(10, 200)
        x = random.randint(2, 20)
        y = k / x
        if hard:
            return f"xy = k。x={x} のとき y={round(y,2)}。k を求めよ。", f"{round(k,2)}"
        else:
            return f"xy = {k}。x={x} のとき y は？", f"{round(y,2)}"

# ------------------------------------------------------------------------------
# カリキュラム → 実際のジェネレータにマッピング（安全版）
# ------------------------------------------------------------------------------
def generate_by_preset(grade: str, field: str, level: int, n: int) -> List[Dict]:
    rows = []

    def add(q, a, preset):
        rows.append({"問題": q, "答え": a, "プリセット": preset})

    preset = PRESET_TABLE[grade][field][level - 1]
    for _ in range(n):
        if grade == "小3" and field == "整数のたし算・ひき算":
            digits = [2, 2, 3, 4, 5][level - 1]
            terms = [2, 3, 3, 4, 5][level - 1]
            q, a = generate_safe(lambda: gen_sum_diff(digits, terms), grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小3" and field == "かけ算の筆算":
            pairs = [(2,1),(3,1),(2,2),(3,2),(3,3)]
            a_d, b_d = pairs[level - 1]
            q, a = generate_safe(lambda: gen_mul(a_d, b_d), grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小3" and field == "わり算（あまりあり）":
            rngs = [(2,50),(10,200),(50,1000),(200,5000),(1000,20000)]
            lo, hi = rngs[level - 1]
            q, a = generate_safe(lambda: gen_div_with_remainder(lo, hi), grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小4" and field == "大きな数と筆算":
            if level in (1,2,3):
                digits = [4,5,6][level - 1]
                q, a = generate_safe(lambda: gen_large_sumdiff(digits), grade=grade, field=field, level=level)
            else:
                pairs = [(3,3),(4,4)]
                q, a = generate_safe(lambda: gen_mul(*pairs[level - 4]), grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小4" and field == "小数の四則":
            if level == 1:
                q, a = generate_safe(lambda: gen_decimal_addsub(1), grade=grade, field=field, level=level)
            elif level == 2:
                q, a = generate_safe(lambda: gen_decimal_addsub(2), grade=grade, field=field, level=level)
            elif level == 3:
                q, a = generate_safe(lambda: gen_decimal_muldiv(1), grade=grade, field=field, level=level)
            elif level == 4:
                q, a = generate_safe(lambda: gen_decimal_muldiv(2), grade=grade, field=field, level=level)
            else:
                def gen_mix():
                    q1, a1 = gen_decimal_addsub(1)
                    q2, a2 = gen_decimal_muldiv(1)
                    q = q1.replace("=", "") + " と " + q2
                    a = f"{a1} / {a2}"
                    return q, a
                q, a = generate_safe(gen_mix, grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小4" and field == "約数・倍数（計算）":
            if level == 1:
                q, a = generate_safe(lambda: gen_gcd_range(30, 100, 2), grade=grade, field=field, level=level)
            elif level == 2:
                q, a = generate_safe(lambda: gen_gcd_range(50, 200, 2), grade=grade, field=field, level=level)
            elif level == 3:
                q, a = generate_safe(lambda: gen_gcd_range(10, 999, 2), grade=grade, field=field, level=level)
            elif level == 4:
                q, a = generate_safe(lambda: gen_lcm_range(10, 50, 3), grade=grade, field=field, level=level)
            else:
                q, a = generate_safe(lambda: gen_gcd_range(10, 200, 3), grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小4" and field == "分数のたし算・ひき算":
            if level == 1:
                q, a = generate_safe(lambda: gen_fraction_addsub(1, 2), grade=grade, field=field, level=level)
            elif level == 2:
                q, a = generate_safe(lambda: gen_fraction_addsub(2, 2), grade=grade, field=field, level=level)
            elif level == 3:
                q, a = generate_safe(lambda: gen_fraction_addsub(1, 3), grade=grade, field=field, level=level)
            elif level == 4:
                q, a = generate_safe(lambda: gen_fraction_addsub(2, 3), grade=grade, field=field, level=level)
            else:
                def gen_story():
                    q0, a0 = gen_fraction_addsub(1, 2)
                    q = f"りんごの重さは {q0.replace(' =','')} とします。合計の重さは？"
                    a = a0
                    return q, a
                q, a = generate_safe(gen_story, grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小5" and field == "分数の四則混合":
            terms = 2 if level == 1 else 3
            q, a = generate_safe(lambda: gen_frac_mixed_ops(terms), grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小5" and field == "小数×分数・分数×分数":
            q, a = generate_safe(gen_fraction_mixed, grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小5" and field == "割合の基本計算":
            mode_map = {1: "of/up/down", 2: "of/up/down", 3: "reverse", 4: "chain", 5: "chain"}
            m = mode_map[level]
            if m == "of/up/down":
                q, a = generate_safe(lambda: gen_percent_basic(random.choice(["of", "up", "down"])),
                                     grade=grade, field=field, level=level)
            else:
                q, a = generate_safe(lambda: gen_percent_basic(m), grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小5" and field == "比の基本計算":
            hard = level >= 4
            q, a = generate_safe(lambda: gen_ratio_basic(hard=hard), grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小6" and field == "分数・小数の複合計算":
            q, a = generate_safe(gen_frac_decimal_combo, grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小6" and field == "逆算（□を求める）":
            q, a = generate_safe(gen_inverse_basic, grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小6" and field == "最大公約数・最小公倍数":
            if level <= 3:
                q, a = generate_safe(lambda: gen_gcd_range(10, 200, random.choice([2,3])),
                                     grade=grade, field=field, level=level)
            else:
                q, a = generate_safe(lambda: gen_lcm_range(10, 60, random.choice([2,3])),
                                     grade=grade, field=field, level=level)
            add(q, a, preset)

        elif grade == "小6" and field == "比例・反比例の基本計算":
            hard = level >= 4
            q, a = generate_safe(lambda: gen_prop_basic(hard=hard), grade=grade, field=field, level=level)
            add(q, a, preset)

    return rows

# ------------------------------------------------------------------------------
# UI
# ------------------------------------------------------------------------------
st.title("🧮 算数ドリルジェネレータ")

# URLクエリ（新API）
qp = st.query_params

def qp_str(key: str, default: str) -> str:
    try:
        v = qp.get(key, default)
        return v if isinstance(v, str) else default
    except Exception:
        return default

def qp_int(key: str, default: int) -> int:
    v = qp_str(key, str(default))
    try:
        return int(v)
    except Exception:
        return default

default_grade = qp_str("grade", "小3")
default_field = qp_str("field", "整数のたし算・ひき算")
default_level = qp_int("level", 1)
default_n = qp_int("n", 10)
default_seed = qp_int("seed", 0)

with st.sidebar:
    st.header("出題設定")
    grade = st.selectbox("学年", list(PRESET_TABLE.keys()),
                         index=list(PRESET_TABLE.keys()).index(default_grade))
    field_list = list(PRESET_TABLE[grade].keys())
    field = st.selectbox("分野", field_list,
                         index=field_list.index(default_field) if default_field in field_list else 0)
    level = st.slider("難度", 1, 5, value=default_level)
    n = st.number_input("出題数", min_value=1, max_value=200, value=default_n, step=1)
    seed = st.number_input("乱数シード（再現用）", min_value=0, max_value=10_000_000, value=default_seed, step=1)
    go = st.button("🧪 生成する", type="primary")

detected_font = find_japanese_font()
if detected_font:
    st.caption(f"📄 検出フォント: {detected_font}")
else:
    st.warning("PDFで日本語を表示するには、日本語フォント（例: assets/NotoSansJP-Regular.ttf）を配置すべきである。現状は '?' 置換のフォールバックである。")

# クエリ反映
try:
    st.query_params.update({
        "grade": grade,
        "field": field,
        "level": str(level),
        "n": str(n),
        "seed": str(seed),
    })
except Exception:
    pass

# 生成処理
if go:
    random.seed(seed)
    rows = generate_by_preset(grade, field, level, n)
    df = pd.DataFrame(rows, columns=["問題", "答え", "プリセット"])

    st.subheader("出題結果")
    st.dataframe(df, use_container_width=True)

    # CSV
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 CSVをダウンロード", data=csv, file_name="problems.csv", mime="text/csv")

    # PDF
    header_meta = {
        "学年": grade,
        "分野": field,
        "難度": f"レベル{level}（{PRESET_TABLE[grade][field][level-1]}）",
        "出題数": str(n),
        "乱数シード": str(seed),
    }
    pdf_bytes = build_pdf(
        title="算数ドリル",
        header_meta=header_meta,
        problems=[{"question": r["問題"], "answer": r["答え"], "meta": r["プリセット"]} for _, r in df.iterrows()],
    )
    st.download_button("📄 PDFをダウンロード", data=pdf_bytes, file_name="drill.pdf", mime="application/pdf")
else:
    st.info("左のサイドバーで条件を選んで「生成する」を押すべきである。")
