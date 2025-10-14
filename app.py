# app.py
# -*- coding: utf-8 -*-
import os
import math
import random
import fractions
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
            "小数第1位の2項の和差算", "小数第2位の2項の和差算",
            "小数第1位の2項の積商算", "小数第2位の2項の積商算",
            "小数第1位の3項の和差積商混合算"
        ],
        "約数・倍数（計算）": [
            "30〜100くらいの小さい整数の公約数", "50〜200の整数の公約数",
            "素因数分解を意識した数（2桁〜3桁）", "3つの数の公倍数", "3つの数の公約数"
        ],
        "分数のたし算・ひき算": [
            "分母1桁・2項の和差算", "分母2桁・2項の和差算",
            "分母1桁・3項の和差算", "分母2桁・3項の和差算", "文章題"
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
        "最大公約数・最小公倍数": ["簡単", "同上", "同上", "高難度", "高難度"],
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
def find_japanese_font() -> Tuple[Union[str, None], int]:
    candidates = [
        ("assets/NotoSansJP-Regular.ttf", 0),
        ("assets/NotoSansJP-Regular.otf", 0),
        ("fonts/NotoSansJP-Regular.ttf", 0),
        ("fonts/NotoSansJP-Regular.otf", 0),
        ("/usr/share/fonts/truetype/noto/NotoSansJP-Regular.ttf", 0),
        ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
        ("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
    ]
    for path, idx in candidates:
        if os.path.exists(path):
            return path, idx
    return None, 0

def ascii_safe(text: str) -> str:
    # 日本語フォントが無いときは '?' 置換でASCII化（落ちないことを最優先）
    return text.encode("latin-1", "replace").decode("latin-1")

def to_bytes(x) -> bytes:
    """
    fpdf2>=2.5 では output(dest="S") は bytes/bytearray を返す。
    古い互換では str の場合もあるので吸収する。
    """
    if isinstance(x, (bytes, bytearray)):
        return bytes(x)
    # 万一 str の場合のみエンコード
    return x.encode("latin-1", "ignore")

def build_pdf(title: str, header_meta: Dict[str, str], problems: List[Dict]) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    font_path, ttc_index = find_japanese_font()
    use_unicode = font_path is not None

    if use_unicode:
        pdf.add_font("JP", "", font_path, uni=True, ttc_index=ttc_index)
        pdf.set_font("JP", size=16)
        write = lambda s: s
    else:
        pdf.set_font("Helvetica", size=16)
        write = ascii_safe

    # タイトル
    pdf.cell(0, 10, text=write(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font_size(11)
    for k, v in header_meta.items():
        pdf.cell(0, 7, text=write(f"{k}: {v}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(2)
    pdf.set_font_size(12)

    # 問題
    for i, p in enumerate(problems, 1):
        q = p["question"]; a = p["answer"]; meta = p.get("meta", "")
        pdf.multi_cell(0, 7, text=write(f"Q{i}. {q}"))
        pdf.cell(0, 6, text=write(f"答え: {a}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if meta:
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, text=write(f"（プリセット: {meta}）"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    # ★ ここが修正ポイント：bytes/bytearray/str を全部吸収
    return to_bytes(pdf.output(dest="S"))

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
    def r(): return round(random.uniform(1, 100), places)
    a, b = r(), r()
    op = random.choice(["+", "-"])
    val = round(a + b, places + 1) if op == "+" else round(a - b, places + 1)
    return f"{a:.{places}f} {op} {b:.{places}f} =", f"{val}"

def gen_decimal_muldiv(places: int) -> Tuple[str, str]:
    def r(): return round(random.uniform(1, 50), places)
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
# カリキュラム → 実際のジェネレータにマッピング
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
            q, a = gen_sum_diff(digits, terms); add(q, a, preset)

        elif grade == "小3" and field == "かけ算の筆算":
            pairs = [(2,1),(3,1),(2,2),(3,2),(3,3)]
            a_d, b_d = pairs[level - 1]
            q, a = gen_mul(a_d, b_d); add(q, a, preset)

        elif grade == "小3" and field == "わり算（あまりあり）":
            rngs = [(2,50),(10,200),(50,1000),(200,5000),(1000,20000)]
            lo, hi = rngs[level - 1]
            q, a = gen_div_with_remainder(lo, hi); add(q, a, preset)

        elif grade == "小4" and field == "大きな数と筆算":
            if level in (1,2,3):
                digits = [4,5,6][level - 1]
                q, a = gen_large_sumdiff(digits)
            else:
                pairs = [(3,3),(4,4)]
                q, a = gen_mul(*pairs[level - 4])
            add(q, a, preset)

        elif grade == "小4" and field == "小数の四則":
            if level == 1:
                q, a = gen_decimal_addsub(1)
            elif level == 2:
                q, a = gen_decimal_addsub(2)
            elif level == 3:
                q, a = gen_decimal_muldiv(1)
            elif level == 4:
                q, a = gen_decimal_muldiv(2)
            else:
                q1, a1 = gen_decimal_addsub(1)
                q2, a2 = gen_decimal_muldiv(1)
                q = q1.replace("=", "") + " と " + q2
                a = f"{a1} / {a2}"
            add(q, a, preset)

        elif grade == "小4" and field == "約数・倍数（計算）":
            if level == 1:
                q, a = gen_gcd_range(30, 100, 2)
            elif level == 2:
                q, a = gen_gcd_range(50, 200, 2)
            elif level == 3:
                q, a = gen_gcd_range(10, 999, 2)
            elif level == 4:
                q, a = gen_lcm_range(10, 50, 3)
            else:
                q, a = gen_gcd_range(10, 200, 3)
            add(q, a, preset)

        elif grade == "小4" and field == "分数のたし算・ひき算":
            if level == 1:
                q, a = gen_fraction_addsub(1, 2)
            elif level == 2:
                q, a = gen_fraction_addsub(2, 2)
            elif level == 3:
                q, a = gen_fraction_addsub(1, 3)
            elif level == 4:
                q, a = gen_fraction_addsub(2, 3)
            else:
                q0, a0 = gen_fraction_addsub(1, 2)
                q = f"りんごの重さは {q0.replace(' =','')} とします。合計の重さは？"
                a = a0
            add(q, a, preset)

        elif grade == "小5" and field == "分数の四則混合":
            terms = 2 if level == 1 else 3
            q, a = gen_frac_mixed_ops(terms); add(q, a, preset)

        elif grade == "小5" and field == "小数×分数・分数×分数":
            q, a = gen_fraction_mixed(); add(q, a, preset)

        elif grade == "小5" and field == "割合の基本計算":
            mode_map = {1: "of/up/down", 2: "of/up/down", 3: "reverse", 4: "chain", 5: "chain"}
            m = mode_map[level]
            if m == "of/up/down":
                q, a = gen_percent_basic(random.choice(["of", "up", "down"]))
            else:
                q, a = gen_percent_basic(m)
            add(q, a, preset)

        elif grade == "小5" and field == "比の基本計算":
            hard = level >= 4
            q, a = gen_ratio_basic(hard=hard); add(q, a, preset)

        elif grade == "小6" and field == "分数・小数の複合計算":
            q, a = gen_frac_decimal_combo(); add(q, a, preset)

        elif grade == "小6" and field == "逆算（□を求める）":
            q, a = gen_inverse_basic(); add(q, a, preset)

        elif grade == "小6" and field == "最大公約数・最小公倍数":
            if level <= 3:
                q, a = gen_gcd_range(10, 200, random.choice([2,3]))
            else:
                q, a = gen_lcm_range(10, 60, random.choice([2,3]))
            add(q, a, preset)

        elif grade == "小6" and field == "比例・反比例の基本計算":
            hard = level >= 4
            q, a = gen_prop_basic(hard=hard); add(q, a, preset)

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
    grade = st.selectbox("学年", list(PRESET_TABLE.keys()), index=list(PRESET_TABLE.keys()).index(default_grade))
    field_list = list(PRESET_TABLE[grade].keys())
    field = st.selectbox("分野", field_list, index=field_list.index(default_field) if default_field in field_list else 0)
    level = st.slider("難度", 1, 5, value=default_level)
    n = st.number_input("出題数", min_value=1, max_value=200, value=default_n, step=1)
    seed = st.number_input("乱数シード（再現用）", min_value=0, max_value=10_000_000, value=default_seed, step=1)
    go = st.button("🧪 生成する", type="primary")

    font_path, _ = find_japanese_font()
    if not font_path:
        st.warning("PDFで日本語を表示するには、日本語フォント（例: assets/NotoSansJP-Regular.ttf）を配置してください。現状は '?' 置換のフォールバックです。")

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
    st.info("左のサイドバーで条件を選んで「生成する」を押してください。")
