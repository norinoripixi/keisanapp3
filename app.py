# app.py — 中学受験 計算プリントメーカー（v0.95：プレビュー統合版）
from __future__ import annotations
import random, io
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import List

import streamlit as st
from fpdf import FPDF

APP_VERSION = "v0.95"

# ====== フォント ======
FONT_PATH = "assets/IPAexGothic.ttf"
JP_FONT_OK = True
try:
    open(FONT_PATH, "rb").close()
except Exception:
    JP_FONT_OK = False

def ascii_safe(text: str) -> str:
    table = str.maketrans({"（":"(", "）":")", "％":"%", "×":"*", "÷":"/", "：":":", "、":", ", "□":"[]"})
    s = text.translate(table)
    repl = {"問題":"Problems", "模範解答":"Answers", "商":"quot", "あまり":"rem",
            "最大公約数":"gcd", "最小公倍数":"lcm", "求めよ":"find"}
    for k,v in repl.items(): s = s.replace(k,v)
    return s.encode("ascii","ignore").decode("ascii")

def T(s: str) -> str:
    return s if JP_FONT_OK else ascii_safe(s)

# ====== モデル ======
@dataclass
class Problem:
    text: str
    answer: str
    unit: str
    difficulty: int

# ====== 学年・分野 ======
GRADE_LABELS = ["小3","小4"]
GRADE_UNITS = {
    "小3": ["整数のたし算・ひき算","かけ算の筆算","わり算（あまりあり）"],
    "小4": ["大きな数と筆算","小数の四則","約数・倍数（計算）","分数のたし算・ひき算"],
}

# 難度マトリクス（小3・小4）
GRADE_UNIT_MATRIX = {
    "小3": {
        "整数のたし算・ひき算": {1: {"digits":2,"terms":2},2:{"digits":2,"terms":3},3:{"digits":3,"terms":3},4:{"digits":4,"terms":4},5:{"digits":5,"terms":5}},
        "かけ算の筆算": {1: {"a_digits":2,"b_digits":1},2:{"a_digits":3,"b_digits":1},3:{"a_digits":2,"b_digits":2},4:{"a_digits":3,"b_digits":2},5:{"a_digits":3,"b_digits":3}},
        "わり算（あまりあり）": {1: {"range":(2,50)},2:{"range":(10,200)},3:{"range":(50,1000)},4:{"range":(200,5000)},5:{"range":(1000,20000)}},
    },
    "小4": {
        "大きな数と筆算": {1:{"type":"和差算","digits":4,"terms":2},2:{"type":"和差算","digits":5,"terms":2},3:{"type":"和差算","digits":6,"terms":2},4:{"type":"積算","digits":3,"terms":2},5:{"type":"積算","digits":4,"terms":2}},
        "小数の四則": {1:{"digits":1,"terms":2,"ops":["+","-"]},2:{"digits":2,"terms":2,"ops":["+","-"]},3:{"digits":1,"terms":2,"ops":["×","÷"]},4:{"digits":2,"terms":2,"ops":["×","÷"]},5:{"digits":1,"terms":3,"ops":["+","-","×","÷"]}},
        "約数・倍数（計算）": {1:{"type":"公約数","range":(30,100)},2:{"type":"公約数","range":(50,200)},3:{"type":"素因数分解","range":(10,200)},4:{"type":"3つの数の公倍数"},5:{"type":"3つの数の公約数"}},
        "分数のたし算・ひき算": {1:{"den_max":9,"terms":2},2:{"den_max":12,"terms":2},3:{"den_max":9,"terms":3},4:{"den_max":12,"terms":3},5:{"type":"文章題"}},
    }
}

# ====== 出題 ======
def rnd_int(r: random.Random, lo: int, hi: int) -> int: return r.randint(lo, hi)

def gen_int_add_sub(r: random.Random, grade: str, unit: str, d: int) -> Problem:
    cfg = GRADE_UNIT_MATRIX.get(grade, {}).get(unit, {}).get(d, {})
    digits = cfg.get("digits", 2); terms = cfg.get("terms", 2)
    nums = [rnd_int(r, 10**(digits-1), 10**digits-1) for _ in range(terms)]
    expr = " + ".join(map(str, nums)); val = sum(nums)
    return Problem(expr, str(val), unit, d)

def gen_mul_div(r: random.Random, grade: str, unit: str, d: int) -> Problem:
    cfg = GRADE_UNIT_MATRIX.get(grade, {}).get(unit, {}).get(d, {})
    a_digits = cfg.get("a_digits", 2); b_digits = cfg.get("b_digits", 1)
    a = rnd_int(r, 10**(a_digits-1), 10**a_digits-1)
    b = rnd_int(r, 10**(b_digits-1), 10**b_digits-1)
    return Problem(f"{a} × {b}", str(a*b), unit, d)

def gen_div_remainder(r: random.Random, grade: str, unit: str, d: int) -> Problem:
    cfg = GRADE_UNIT_MATRIX.get(grade, {}).get(unit, {}).get(d, {})
    lo, hi = cfg.get("range", (2,50))
    b = rnd_int(r, 7, 23); a = rnd_int(r, max(b+1, lo), hi)
    q, rem = divmod(a,b)
    if rem == 0: a += 1; q, rem = divmod(a,b)
    return Problem(f"{a} ÷ {b}（あまりは？）", f"商 {q}、あまり {rem}", unit, d)

UNIT_GENERATORS = {
    "整数のたし算・ひき算":[gen_int_add_sub],
    "かけ算の筆算":[gen_mul_div],
    "わり算（あまりあり）":[gen_div_remainder],
}
def pick_generators(units: List[str]):
    gens=[]; [gens.extend(UNIT_GENERATORS.get(u,[])) for u in units]; return gens or [gen_int_add_sub]

def generate_set(seed:int, grade:str, units:List[str], difficulty:int, n:int=10)->List[Problem]:
    r=random.Random(seed); gens=pick_generators(units); out=[]
    for _ in range(n):
        g=r.choice(gens); unit=random.choice(units)
        out.append(g(r, grade, unit, difficulty))
    return out

# ====== PDFユーティリティ（1ページ強制収容＋等間隔余白） ======
def _measure_total_lines(pdf:FPDF, items:list[str], epw:float, line_h:float, font_name:str, font_size:int)->int:
    pdf.set_font(font_name, size=font_size)
    total=0
    for t in items:
        lines = pdf.multi_cell(epw*0.85, line_h, txt=T(t), split_only=True)
        total += len(lines)
    return total

def _draw_hanging_item(pdf:FPDF, idx:int, text:str, line_h:float, epw:float):
    prefix=f"{idx}. "; pw=pdf.get_string_width(T(prefix))
    pdf.cell(pw, line_h, txt=T(prefix), ln=0)
    pdf.multi_cell(epw - pw, line_h, txt=T(text), ln=1)

def _draw_list_fit_one_page(pdf:FPDF, items:list[str], start_index:int, epw:float, font_name:str):
    for size in [12,11,10,9,8]:
        line_h = 8 * (size/12)
        total_lines = _measure_total_lines(pdf, items, epw, line_h, font_name, size)
        y0 = pdf.get_y(); usable_h = (pdf.h - pdf.b_margin) - y0
        content_h = total_lines * line_h
        leftover = usable_h - content_h
        if leftover >= 6:
            gap = max(1.0, leftover / max(1,len(items)-1))
            pdf.set_font(font_name, size=size)
            for i, t in enumerate(items, start=start_index):
                _draw_hanging_item(pdf, i, t, line_h, epw)
                if i < start_index + len(items) - 1:
                    pdf.ln(gap)
            return
    size=8; line_h=8*(size/12); pdf.set_font(font_name, size=size)
    for i, t in enumerate(items, start=start_index):
        _draw_hanging_item(pdf, i, t, line_h, epw)

# ====== PDF生成 ======
def make_pdf(problems: List[Problem], meta_title: str, meta_sub: str) -> io.BytesIO:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(15, 15, 15); pdf.set_auto_page_break(True, margin=15)

    if JP_FONT_OK:
        pdf.add_font("JP", style="", fname=FONT_PATH, uni=True)
        base_font="JP"
    else:
        base_font="Helvetica"

    epw = pdf.w - pdf.l_margin - pdf.r_margin

    # 1ページ目：問題
    pdf.add_page()
    pdf.set_font(base_font, size=14); pdf.cell(0,10,txt=T(f"{meta_title}（問題）"), ln=1)
    pdf.set_font(base_font, size=10); pdf.cell(0,7,txt=T(meta_sub), ln=1, align="R")
    pdf.set_y(pdf.get_y()+2)
    _draw_list_fit_one_page(pdf, [p.text for p in problems], 1, epw, base_font)

    # 2ページ目：模範解答
    pdf.add_page()
    pdf.set_font(base_font, size=14); pdf.cell(0,10,txt=T(f"{meta_title}（模範解答）"), ln=1)
    pdf.set_font(base_font, size=10); pdf.cell(0,7,txt=T(meta_sub), ln=1, align="R")
    pdf.set_y(pdf.get_y()+2)
    _draw_list_fit_one_page(pdf, [p.answer for p in problems], 1, epw, base_font)

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf

# ====== UI ======
st.set_page_config(page_title="中学受験 計算プリントメーカー", page_icon="🧮", layout="centered")
st.title(f"中学受験 計算プリントメーカー（v{APP_VERSION}）")

col1, col2 = st.columns(2)
with col1:
    grade = st.selectbox("学年（目安）", options=GRADE_LABELS, index=1)
with col2:
    difficulty = st.slider("難度（1=基礎〜5=発展）", 1, 5, 4)

default_units = GRADE_UNITS.get(grade, [])
units = st.multiselect("分野（複数選択可）", options=default_units, default=default_units)
seed = st.number_input("シード（再現用）", min_value=0, max_value=10_000_000, value=random.randint(0,999_999), step=1)

if st.button("問題を生成"):
    problems = generate_set(seed=int(seed), grade=grade, units=units or default_units, difficulty=int(difficulty), n=10)
    st.session_state["problems"] = problems

    # ★プレビュー（JSONは使わない）
    st.subheader("プレビュー（問題）")
    for i, p in enumerate(problems, 1):
        st.markdown(f"**{i}.** {p.text}")

    st.subheader("プレビュー（模範解答）")
    for i, p in enumerate(problems, 1):
        st.markdown(f"**{i}.** {p.answer}")

    # 生成直後DL
    title = f"{grade} 計算プリント"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    subtitle = f"難度:{difficulty} / 分野:{'、'.join(units or default_units)} / 生成:{now}"
    pdf_buffer = make_pdf(problems, title, subtitle)
    st.download_button(
        label="PDFをダウンロード（問題／模範解答）",
        data=pdf_buffer,
        file_name=f"{grade}_計算プリント_{now.replace(' ','_').replace(':','')}.pdf",
        mime="application/pdf"
    )

# 回答入力・正誤判定（任意）
if "problems" in st.session_state:
    problems = st.session_state["problems"]
    st.subheader("問題に回答する")
    user_answers=[]
    for i,p in enumerate(problems,1):
        user_answers.append(st.text_input(f"{i}. {p.text}", key=f"ans_{i}"))
    if st.button("回答を提出"):
        correct=0
        for i,(p,ua) in enumerate(zip(problems,user_answers),1):
            try:
                ok = (Fraction(ua) == Fraction(p.answer))
            except:
                ok = str(ua).strip() == str(p.answer).strip()
            if ok: correct+=1
            st.write(f"{i}. {'正解' if ok else '不正解'}（あなた: {ua} / 正: {p.answer}）")
        st.success(f"正答率: {correct}/{len(problems)} = {correct/len(problems)*100:.1f}%")
