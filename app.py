# app.py
# -------------------------------------------
# 小3〜小6 / 表準拠の 出題マスタ + 分野別ジェネレータ + PDF/CSV出力
# -------------------------------------------
import random
import math
from fractions import Fraction
from io import BytesIO
import os

import streamlit as st
import pandas as pd
from fpdf import FPDF, XPos, YPos

# ====== 出題マスタ（学年×分野×難度） ======
GRADES = ["小3", "小4", "小5", "小6"]

GRADE_UNITS = {
    "小3": [
        "整数のたし算・ひき算",
        "かけ算の筆算",
        "わり算（あまりあり）",
    ],
    "小4": [
        "大きな数と筆算",
        "小数の四則",
        "約数・倍数（計算）",
        "分数のたし算・ひき算",
    ],
    "小5": [
        "分数の四則混合",
        "小数×分数・分数×分数",
        "割合の基本計算",
        "比の基本計算",
    ],
    "小6": [
        "分数・小数の複合計算",
        "逆算（□を求める）",
        "最大公約数・最小公倍数",
        "比例・反比例の基本計算",
    ],
}

GRADE_UNIT_MATRIX = {
    "小3": {
        "整数のたし算・ひき算": [
            "2桁・2項の和差算",
            "2桁・3項の和差算",
            "3桁・3項の和差算",
            "4桁・4項の和差算",
            "5桁・5項の和差算",
        ],
        "かけ算の筆算": [
            "2桁×1桁",
            "3桁×1桁",
            "2桁×2桁",
            "3桁×2桁",
            "3桁×3桁",
        ],
        "わり算（あまりあり）": [
            "2〜50",
            "10〜200",
            "50〜1000",
            "200〜5000",
            "1000〜20000",
        ],
    },
    "小4": {
        "大きな数と筆算": [
            "4桁・2項の和差算",
            "5桁・2項の和差算",
            "6桁・2項の和差算",
            "3桁・2項の積",
            "4桁・2項の積",
        ],
        "小数の四則": [
            "小数第1位の2項の和差算",
            "小数第2位の2項の和差算",
            "小数第1位の2項の積商算",
            "小数第2位の2項の積商算",
            "小数第1位の3項の和差積商混合算",
        ],
        "約数・倍数（計算）": [
            "30〜100くらいの小さい整数の公約数",
            "50〜200の整数の公約数",
            "素因数分解を意識した数（2桁〜3桁）",
            "3つの数の公倍数",
            "3つの数の公約数",
        ],
        "分数のたし算・ひき算": [
            "分母1桁・2項の和差算",
            "分母2桁・2項の和差算",
            "分母1桁・3項の和差算",
            "分母2桁・3項の和差算",
            "文章題",
        ],
    },
    "小5": {
        "分数の四則混合": [
            "frac_terms 2〜3",
            "同上",
            "3",
            "3",
            "3",
        ],
        "小数×分数・分数×分数": [
            "frac_mixed",
            "同上",
            "同上",
            "同上",
            "同上",
        ],
        "割合の基本計算": [
            "of/up/down",
            "同上",
            "reverse",
            "chain",
            "chain",
        ],
        "比の基本計算": [
            "簡単比",
            "同上",
            "同上",
            "難易度高",
            "難易度高",
        ],
    },
    "小6": {
        "分数・小数の複合計算": [
            "frac+decimal",
            "同上",
            "同上",
            "同上",
            "同上",
        ],
        "逆算（□を求める）": [
            "基本",
            "同上",
            "同上",
            "同上",
            "同上",
        ],
        "最大公約数・最小公倍数": [
            "簡単",
            "同上",
            "同上",
            "高難度",
            "高難度",
        ],
        "比例・反比例の基本計算": [
            "基本",
            "同上",
            "同上",
            "難易度高",
            "難易度高",
        ],
    },
}

# ====== ユーティリティ ======
def rand_int(digits: int) -> int:
    a = 10 ** (digits - 1)
    b = 10 ** digits - 1
    return random.randint(a, b)

def simplify_fraction(fr: Fraction) -> Fraction:
    return Fraction(fr.numerator, fr.denominator)

def fmt_frac(fr: Fraction) -> str:
    return f"{fr.numerator}/{fr.denominator}"

def dec_round(x: float, places: int) -> float:
    return round(x, places)

# ====== 分野別ジェネレータ（(問題文, 答え)を返す） ======
def gen_es_add_sub(preset: str):
    mapping = {
        "2桁・2項の和差算": (2, 2),
        "2桁・3項の和差算": (2, 3),
        "3桁・3項の和差算": (3, 3),
        "4桁・4項の和差算": (4, 4),
        "5桁・5項の和差算": (5, 5),
    }
    digits, terms = mapping[preset]
    nums = [rand_int(digits) for _ in range(terms)]
    ops = ["+"] + [random.choice(["+", "-"]) for _ in range(terms - 1)]
    expr, total = "", 0
    for i, (op, n) in enumerate(zip(ops, nums)):
        if i == 0:
            expr += f"{n}"
            total += n
        else:
            expr += f" {op} {n}"
            total = total + n if op == "+" else total - n
    return f"{expr} を計算しなさい。", str(total)

def gen_mul_long(preset: str):
    if preset == "2桁×1桁":
        a, b = rand_int(2), random.randint(2, 9)
    elif preset == "3桁×1桁":
        a, b = rand_int(3), random.randint(2, 9)
    elif preset == "2桁×2桁":
        a, b = rand_int(2), rand_int(2)
    elif preset == "3桁×2桁":
        a, b = rand_int(3), rand_int(2)
    else:
        a, b = rand_int(3), rand_int(3)
    return f"{a} × {b} を計算しなさい。", str(a * b)

def gen_div_remainder(preset: str):
    ranges = {
        "2〜50": (2, 50),
        "10〜200": (10, 200),
        "50〜1000": (50, 1000),
        "200〜5000": (200, 5000),
        "1000〜20000": (1000, 20000),
    }
    lo, hi = ranges[preset]
    b = random.randint(2, 9)
    a = random.randint(lo, hi)
    q = f"{a} ÷ {b} を計算しなさい（あまりがあれば『あまり◯』と書く）。"
    return q, f"{a // b} あまり {a % b}"

def gen_big_and_long_calc(preset: str):
    if "和差" in preset:
        digits = int(preset[0])
        a, b = rand_int(digits), rand_int(digits)
        op = random.choice(["+", "-"])
        ans = a + b if op == "+" else a - b
        return f"{a} {op} {b} を計算しなさい。", str(ans)
    digits = int(preset[0])
    a, b = rand_int(digits), rand_int(digits)
    return f"{a} × {b} を計算しなさい。", str(a * b)

def gen_decimal_ops(preset: str):
    places = 1 if "小数第1位" in preset else 2
    def r(): return dec_round(random.uniform(1, 99), places)
    if "和差" in preset:
        a, b = r(), r()
        op = random.choice(["+", "-"])
        ans = dec_round(a + b if op == "+" else a - b, places)
        return f"{a} {op} {b} を計算しなさい。", f"{ans:.{places}f}"
    if "積商" in preset:
        a, b = r(), r()
        op = random.choice(["×", "÷"])
        if op == "×":
            ans = dec_round(a * b, places)
        else:
            if b == 0: b = 1.0
            ans = dec_round(a / b, places)
        return f"{a} {op} {b} を計算しなさい。", f"{ans:.{places}f}"
    a, b, c = r(), r(), r()
    ops = [random.choice(["+", "-", "×", "÷"]) for _ in range(2)]
    expr = f"{a} {ops[0]} {b} {ops[1]} {c}"
    val = a
    for i, x in enumerate([b, c]):
        op = ops[i]
        if op == "+": val = val + x
        elif op == "-": val = val - x
        elif op == "×": val = val * x
        else: val = val / (x if x != 0 else 1.0)
    ans = dec_round(val, places)
    return f"{expr} を計算しなさい。", f"{ans:.{places}f}"

def gen_factors_multiples(preset: str):
    if "小さい整数の公約数" in preset:
        if "30〜100" in preset:
            a, b = random.randint(30, 100), random.randint(30, 100)
        else:
            a, b = random.randint(50, 200), random.randint(50, 200)
        return f"{a} と {b} の最大公約数を求めなさい。", str(math.gcd(a, b))
    if "素因数分解" in preset:
        n = random.randint(10, 999)
        m, i, fac = n, 2, []
        while i * i <= m:
            while m % i == 0:
                fac.append(i); m //= i
            i += 1
        if m > 1: fac.append(m)
        return f"{n} を素因数分解しなさい。", "×".join(map(str, fac))
    if "3つの数の公倍数" in preset:
        a, b, c = random.randint(2, 30), random.randint(2, 30), random.randint(2, 30)
        return f"{a},{b},{c} の最小公倍数を求めなさい。", str(math.lcm(a, b, c))
    if "3つの数の公約数" in preset:
        a, b, c = random.randint(30, 200), random.randint(30, 200), random.randint(30, 200)
        return f"{a},{b},{c} の最大公約数を求めなさい。", str(math.gcd(a, math.gcd(b, c)))
    raise ValueError("未対応プリセット")

def gen_frac_add_sub(preset: str):
    def rf(max_den):
        den = random.randint(2, max_den)
        num = random.randint(1, den - 1)
        return Fraction(num, den)
    if "文章題" in preset:
        a, b = rf(9), rf(9)
        op = random.choice(["+", "-"])
        q = f"みかんを {fmt_frac(a)} だけ食べ、さらに{('食べました' if op=='+' else '残しました')}。合計（または差）は？"
        ans = simplify_fraction(a + b if op == "+" else a - b)
        return q, fmt_frac(ans)
    if "3項" in preset:
        max_den = 9 if "分母1桁" in preset else 19
        a, b, c = rf(max_den), rf(max_den), rf(max_den)
        op1, op2 = random.choice(["+", "-"]), random.choice(["+", "-"])
        expr = f"{fmt_frac(a)} {op1} {fmt_frac(b)} {op2} {fmt_frac(c)}"
        val = a; val = val + b if op1 == "+" else val - b
        val = val + c if op2 == "+" else val - c
        val = simplify_fraction(val)
        return f"{expr} を計算しなさい。", fmt_frac(val)
    max_den = 9 if "分母1桁" in preset else 19
    a, b = rf(max_den), rf(max_den)
    op = random.choice(["+", "-"])
    expr = f"{fmt_frac(a)} {op} {fmt_frac(b)}"
    val = simplify_fraction(a + b if op == "+" else a - b)
    return f"{expr} を計算しなさい。", fmt_frac(val)

def gen_frac_mixed_ops(preset: str):
    k = 3  # 表仕様に合わせ3項中心
    terms = [Fraction(random.randint(1, 9), random.randint(2, 9)) for _ in range(k)]
    ops = [random.choice(["+", "-", "×", "÷"]) for _ in range(k - 1)]
    expr = fmt_frac(terms[0]); val = terms[0]
    for i in range(1, k):
        op = ops[i - 1]; t = terms[i]
        expr += f" {op} {fmt_frac(t)}"
        if op == "+": val = val + t
        elif op == "-": val = val - t
        elif op == "×": val = val * t
        else: val = val / t
    val = simplify_fraction(val)
    return f"{expr} を計算しなさい。", fmt_frac(val)

def gen_frac_decimal_mix(_preset: str):
    if random.choice([True, False]):
        a = Fraction(random.randint(1, 9), random.randint(2, 9))
        b = Fraction(random.randint(1, 9), random.randint(2, 9))
        return f"{fmt_frac(a)} × {fmt_frac(b)} を計算しなさい。", fmt_frac(simplify_fraction(a * b))
    dec = round(random.uniform(0.1, 9.9), 1)
    fr = Fraction(random.randint(1, 9), random.randint(2, 9))
    p10 = 10
    dec_fr = Fraction(int(round(dec * p10)), p10)
    return f"{dec} × {fmt_frac(fr)} を計算しなさい。", fmt_frac(simplify_fraction(dec_fr * fr))

def gen_percent(preset: str):
    if preset in ("of/up/down", "同上"):
        a = random.randint(20, 900)
        p = random.choice([5, 10, 12, 20, 25, 30, 40, 50])
        ans = a * p / 100
        return f"{a} の {p}% はいくつ？", str(int(ans) if float(ans).is_integer() else ans)
    if preset == "reverse":
        b = random.randint(20, 500)
        p = random.choice([10, 20, 25, 50])
        ans = b * 100 / p
        return f"ある数の {p}% が {b} です。もとの数はいくつ？", str(int(ans) if float(ans).is_integer() else ans)
    a = random.randint(50, 900)
    p1 = random.choice([10, 20, 30]); p2 = random.choice([10, 20, 30])
    val = a * (1 + p1 / 100) * (1 - p2 / 100)
    return f"{a} をまず {p1}% 増やし、そのあと {p2}% 減らすといくつ？", str(int(val) if float(val).is_integer() else round(val, 2))

def gen_ratio(preset: str):
    if preset in ("簡単比", "同上"):
        a, b = random.randint(2, 30), random.randint(2, 30)
        g = math.gcd(a, b)
        return f"{a}:{b} を最も簡単な比にしなさい。", f"{a // g}:{b // g}"
    x = random.randint(2, 12)
    a = x * random.randint(2, 9)
    b = x * random.randint(2, 9)
    c = random.randint(2, 30)
    ans = a * c / b
    return f"{a}:{b} = x:{c} のとき、x の値を求めなさい。", str(int(ans) if float(ans).is_integer() else round(ans, 2))

def gen_frac_decimal_combo(_preset: str):
    f1 = Fraction(random.randint(1, 9), random.randint(2, 9))
    f2 = Fraction(random.randint(1, 9), random.randint(2, 9))
    d = round(random.uniform(0.1, 9.9), 1)
    if random.choice([True, False]):
        left_expr = f"{fmt_frac(f1)} + {d}"
        left_val = f1 + Fraction(int(round(d * 10)), 10)
    else:
        left_expr = f"{fmt_frac(f1)} - {d}"
        left_val = f1 - Fraction(int(round(d * 10)), 10)
    expr = f"({left_expr}) × {fmt_frac(f2)}"
    val = simplify_fraction(left_val * f2)
    return f"{expr} を計算しなさい。", fmt_frac(val)

def gen_inverse_basic(_preset: str):
    a = random.randint(2, 50); b = random.randint(2, 200)
    op = random.choice(["+", "-", "×", "÷"])
    if op == "+":
        return f"□ + {a} = {b} のとき、□の値を求めなさい。", str(b - a)
    if op == "-":
        return f"□ - {a} = {b} のとき、□の値を求めなさい。", str(b + a)
    if op == "×":
        return f"□ × {a} = {b} のとき、□の値を求めなさい。", str(b / a if b % a else b // a)
    return f"□ ÷ {a} = {b} のとき、□の値を求めなさい。", str(b * a)

def gen_gcd_lcm(preset: str):
    if preset in ("簡単", "同上"):
        a, b = random.randint(10, 99), random.randint(10, 99)
        if random.choice([True, False]):
            return f"{a} と {b} の最大公約数を求めなさい。", str(math.gcd(a, b))
        return f"{a} と {b} の最小公倍数を求めなさい。", str(math.lcm(a, b))
    a, b, c = random.randint(10, 200), random.randint(10, 200), random.randint(10, 200)
    if random.choice([True, False]):
        return f"{a},{b},{c} の最大公約数を求めなさい。", str(math.gcd(a, math.gcd(b, c)))
    return f"{a},{b},{c} の最小公倍数を求めなさい。", str(math.lcm(a, b, c))

def gen_proportion(preset: str):
    mode = "比例" if random.choice([True, False]) else "反比例"
    if mode == "比例":
        a = random.randint(2, 9); x = random.randint(2, 20)
        return f"比例 y = {a}x で、x={x} のときの y を求めなさい。", str(a * x)
    a = random.randint(6, 60); x = random.randint(2, 20)
    y = a / x
    return f"反比例 xy = {a} で、x={x} のときの y を求めなさい。", str(int(y) if float(y).is_integer() else y)

GENERATORS = {
    "小3": {
        "整数のたし算・ひき算": gen_es_add_sub,
        "かけ算の筆算": gen_mul_long,
        "わり算（あまりあり）": gen_div_remainder,
    },
    "小4": {
        "大きな数と筆算": gen_big_and_long_calc,
        "小数の四則": gen_decimal_ops,
        "約数・倍数（計算）": gen_factors_multiples,
        "分数のたし算・ひき算": gen_frac_add_sub,
    },
    "小5": {
        "分数の四則混合": gen_frac_mixed_ops,
        "小数×分数・分数×分数": gen_frac_decimal_mix,
        "割合の基本計算": gen_percent,
        "比の基本計算": gen_ratio,
    },
    "小6": {
        "分数・小数の複合計算": gen_frac_decimal_combo,
        "逆算（□を求める）": gen_inverse_basic,
        "最大公約数・最小公倍数": gen_gcd_lcm,
        "比例・反比例の基本計算": gen_proportion,
    },
}

def resolve_preset(grade: str, unit: str, difficulty_idx: int) -> str:
    preset = GRADE_UNIT_MATRIX[grade][unit][difficulty_idx - 1]
    if preset == "同上":
        for i in range(difficulty_idx - 2, -1, -1):
            if GRADE_UNIT_MATRIX[grade][unit][i] != "同上":
                return GRADE_UNIT_MATRIX[grade][unit][i]
    return preset

def generate_one(grade: str, unit: str, difficulty_idx: int):
    preset = resolve_preset(grade, unit, difficulty_idx)
    q, a = GENERATORS[grade][unit](preset)
    return q, a, preset

# ====== PDF 出力 ======
def find_japanese_font() -> str | None:
    candidates = [
        "assets/NotoSansJP-Regular.ttf",
        "assets/NotoSansJP-Regular.otf",
        "fonts/NotoSansJP-Regular.ttf",
        "fonts/NotoSansJP-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def build_pdf(title: str, header_meta: dict, problems: list[dict]) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # フォント設定
    font_path = find_japanese_font()
    if font_path:
        # Unicode対応
        pdf.add_font("JP", "", font_path)
        pdf.set_font("JP", size=14)
    else:
        # 代替（日本語は空白になる可能性あり）
        pdf.set_font("Helvetica", size=14)

    # タイトル
    pdf.cell(0, 10, text=title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # メタ
    for k, v in header_meta.items():
        pdf.set_font_size(11)
        pdf.cell(0, 7, text=f"{k}: {v}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(2)
    pdf.set_font_size(12)
    # 問題
    for i, p in enumerate(problems, 1):
        q = p["question"]
        a = p["answer"]
        meta = p.get("meta", "")
        pdf.multi_cell(0, 7, txt=f"Q{i}. {q}")
        pdf.cell(0, 6, text=f"答え: {a}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if meta:
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, text=f"（プリセット: {meta}）", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    return pdf.output()  # bytes を返す（fpdf2 >=2.7）

# ====== Streamlit UI ======
st.set_page_config(page_title="算数ドリルメーカー", page_icon="🧮", layout="wide")

st.title("🧮 算数ドリルメーカー（小3〜小6）")
st.caption("表に準じた『学年 × 分野 × 難度(1〜5)』の問題を自動生成します。")

# --- URLクエリ（Streamlit 1.50: st.query_params） ---
qp = st.query_params  # 直接辞書のように使える
def sync_query_params(grade: str, unit: str, diff: int, n: int):
    qp["grade"] = grade
    qp["unit"] = unit
    qp["diff"] = str(diff)
    qp["n"] = str(n)

# --- サイドバー ---
with st.sidebar:
    st.header("設定")
    default_grade = qp.get("grade", ["小4"])[0] if isinstance(qp.get("grade"), list) else qp.get("grade", "小4")
    grade = st.selectbox("学年", GRADES, index=GRADES.index(default_grade) if default_grade in GRADES else 1)

    units = GRADE_UNITS[grade]
    default_unit = qp.get("unit", [units[0]])[0] if isinstance(qp.get("unit"), list) else qp.get("unit", units[0])
    unit = st.selectbox("分野", units, index=units.index(default_unit) if default_unit in units else 0)

    default_diff = int(qp.get("diff", ["1"])[0]) if isinstance(qp.get("diff"), list) else int(qp.get("diff", 1))
    diff = st.slider("難度（1=易 → 5=難）", 1, 5, default_diff)

    default_n = int(qp.get("n", ["10"])[0]) if isinstance(qp.get("n"), list) else int(qp.get("n", 10))
    n_questions = st.number_input("出題数", min_value=1, max_value=100, value=default_n, step=1)

    seed_enable = st.checkbox("乱数シードを固定する", value=False)
    seed_val = st.number_input("シード値", min_value=0, max_value=10_000_000, value=1234, step=1, disabled=not seed_enable)

    st.divider()
    gen_btn = st.button("🎲 生成 / 更新", use_container_width=True)

# --- セッション状態 ---
if "problems" not in st.session_state:
    st.session_state.problems = []

# --- 生成処理 ---
if gen_btn:
    if seed_enable:
        random.seed(int(seed_val))
    problems = []
    for _ in range(n_questions):
        q, a, meta = generate_one(grade, unit, diff)
        problems.append({"question": q, "answer": a, "meta": meta})
    st.session_state.problems = problems
    sync_query_params(grade, unit, diff, n_questions)

# --- 出力表示 ---
st.subheader("プレビュー")
if not st.session_state.problems:
    st.info("左の設定で「生成 / 更新」を押すと、ここに問題が表示されます。")
else:
    df = pd.DataFrame(st.session_state.problems)
    # 列名を日本語化
    df = df.rename(columns={"question": "問題", "answer": "答え", "meta": "プリセット"})
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ダウンロード（CSV / PDF）
    col1, col2 = st.columns(2)
    with col1:
        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 CSVをダウンロード",
            data=csv_bytes,
            file_name=f"{grade}_{unit}_難度{diff}_全{len(df)}問.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col2:
        header_meta = {
            "学年": grade,
            "分野": unit,
            "難度": f"{diff}（{resolve_preset(grade, unit, diff)}）",
            "出題数": str(len(df)),
        }
        pdf_bytes = build_pdf(
            title="算数ドリル",
            header_meta=header_meta,
            problems=[{"question": r["問題"], "answer": r["答え"], "meta": r["プリセット"]} for _, r in df.iterrows()],
        )
        st.download_button(
            "📄 PDFをダウンロード",
            data=BytesIO(pdf_bytes),
            file_name=f"{grade}_{unit}_難度{diff}_全{len(df)}問.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

# --- フッター ---
with st.expander("動作メモ / トラブルシュート", expanded=False):
    st.markdown(
        """
- **表に準拠**して、学年・分野・難度が厳密に対応します（未定義は出ません）。
- PDF の日本語が空白になる場合は、`assets/NotoSansJP-Regular.ttf` などを配置してください。
- Streamlit 1.50 以降は `st.experimental_get_query_params` 非推奨のため、本アプリは **`st.query_params`** を使用しています。
"""
    )
