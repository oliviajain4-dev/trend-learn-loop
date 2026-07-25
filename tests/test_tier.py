"""동물 티어 8계급(점검 후 규칙: 정착=시간, 합의=arxiv_recent제외, 나이 미사용) — PYTHONPATH=src python tests/test_tier.py"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from tll.rank import ConceptScore, assign_tier  # noqa: E402

checks = 0


def ok(c, m):
    global checks
    assert c, "FAIL: " + m
    checks += 1


def CS(**kw):
    base = dict(cid="c", attention=0.0, adoption=0.0, adoption_growth=0.0, accelerating=False,
               rising_kinds=0, stock_kinds=0, recurrence=1, fake_flag=False, n_signals=1,
               growth_measured=False, corrob_kinds=0, adoption_mag=0.0)
    base.update(kw)
    return ConceptScore(**base)


# 하이에나 = 가짜 최우선
ok(assign_tier(CS(adoption=85, adoption_growth=200, rising_kinds=1, corrob_kinds=3, fake_flag=True)).tier == "hyena", "가짜=하이에나")
# 코끼리 = 거대 + '측정된 평탄' + 재등장≥3 + 안 뜸 (시간으로 벌어야)
ok(assign_tier(CS(adoption=85, adoption_growth=0.0, growth_measured=True, rising_kinds=0, corrob_kinds=3, recurrence=4)).tier == "elephant", "거대+측정된평탄+여러번=코끼리(관측으로)")
ok(assign_tier(CS(adoption=85, corrob_kinds=3, recurrence=1, growth_measured=False), age_days=3000).tier == "elephant", "거대+신뢰나이(≥4년)=코끼리(첫 관측이라도)")
ok(assign_tier(CS(adoption=85, corrob_kinds=3, recurrence=1, growth_measured=False), age_days=None).tier == "turtle", "거대+나이불명+첫관측=거북이(잠정)")
# ★ 첫 관측(성장 미측정)이면 거대여도 코끼리 불가 → 거북이 잠정
t0 = assign_tier(CS(adoption=85, growth_measured=False, corrob_kinds=3, recurrence=1))
ok(t0.tier == "turtle" and t0.provisional, "첫 관측 거대 = 거북이(잠정), 코끼리 아님")
# 공룡 = 높음 + 측정된 하락
ok(assign_tier(CS(adoption=65, adoption_growth=-40, growth_measured=True, corrob_kinds=2, recurrence=3)).tier == "dinosaur", "측정된 하락=공룡")
# 호랑이 = 높음 + 뜨는 중
ok(assign_tier(CS(adoption=65, adoption_growth=120, rising_kinds=3, growth_measured=True, corrob_kinds=3, recurrence=5)).tier == "tiger", "높음+상승=호랑이")
ok(assign_tier(CS(adoption=65, attention=200, corrob_kinds=2, recurrence=5)).tier == "tiger", "높음+화제=호랑이")
# 거북이(확정) = 중간 + 여러 번 평탄 관측
e = assign_tier(CS(adoption=48, adoption_growth=0.0, growth_measured=True, corrob_kinds=2, recurrence=5))
ok(e.tier == "turtle" and e.provisional is False, "중간+여러번 평탄=거북이(확정)")
# 단일소스인데 큰 것 = 거북이 잠정 (RAG 케이스: 미확인)
r = assign_tier(CS(adoption=74, corrob_kinds=1, recurrence=1))
ok(r.tier == "turtle" and r.provisional, "단일소스 큰 것=거북이(잠정)")
# 치타 = 화제인데 채택 미검증
c1 = assign_tier(CS(attention=300, adoption=0, corrob_kinds=0, recurrence=1, buzz_sources=1))
ok(c1.tier == "cheetah" and c1.provisional, "화제·미검증=치타(잠정)")
# 치타 = 급성장(미검증, 채택 낮음)
ok(assign_tier(CS(adoption=30, adoption_growth=60, rising_kinds=2, growth_measured=True, corrob_kinds=2, recurrence=2)).tier == "cheetah", "급성장·낮은채택=치타")
# 새싹 = 갓 등장
s1 = assign_tier(CS(adoption=15, corrob_kinds=1, recurrence=1))
ok(s1.tier == "sprout" and s1.provisional, "신생·미약=새싹(잠정)")
# 하루살이
ok(assign_tier(CS(adoption=0, corrob_kinds=0, recurrence=6)).tier == "mayfly", "여러번 봤는데 흔적없음=하루살이")
ok(assign_tier(CS(attention=300, adoption=0, corrob_kinds=0, recurrence=5, buzz_sources=1)).tier == "mayfly", "독립 화제 반복 미전환=하루살이")
ok(assign_tier(CS(attention=200, adoption=0, corrob_kinds=0, recurrence=1, buzz_sources=0)).tier == "sprout", "공식 자기홍보만(독립0)=새싹")
# 단일지표는 상위 확정 티어(코끼리·호랑이·공룡) 못 감
ok(assign_tier(CS(adoption=85, corrob_kinds=1, recurrence=5)).tier not in ("elephant", "tiger", "dinosaur"), "단일소스는 확정 상위 금지")

print(f"{checks} checks passed")
