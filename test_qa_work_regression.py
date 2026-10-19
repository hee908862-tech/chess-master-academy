"""Regression contract tests for QA-01..11 (static, no account or engine required).
Run: python test_qa_work_regression.py
Full integration and mating-variation correctness require python-chess + Stockfish.
"""
from pathlib import Path
import ast
root=Path(__file__).parent
server=(root/'server.py').read_text()
v9=(root/'v9_server.py').read_text()
v8=(root/'public/v8.js').read_text()
ui=(root/'public/v9.js').read_text()
app=(root/'public/app.js').read_text()
html=(root/'public/index.html').read_text()
a=(root/'assessment_v8.py').read_text()
for src in root.glob('*.py'):ast.parse(src.read_text())
checks={
 'QA-01 terminal mating alternative':'trial.is_checkmate()' in v9 and '_is_alternative_mate(b,m,p,task)' in v9,
 'QA-02 timeout state':'termination\':\'timeout\'' in server and 'resumeGame().finally' in app,
 'QA-03 v9 recommendation navigation':'window.cmaOpenV9Course' in ui and 'window.cmaOpenV9Course?.(course.id)' in v8,
 'QA-04 first attempt and hint':'first_try_correct' in v9 and 'hint_used' in v9 and 'first_try_total' in server,
 'QA-05 course progress included':'courses_completed' in server and '학습 이수 세션' in app,
 'QA-06 minimum evaluated moves':'len(game_losses)>=12' in a,
 'QA-07 zero content disabled':'btn.disabled=total===0' in ui and "el('v9CourseStart').disabled=!available.length" in ui,
 'QA-08 task state reset':'st.task=null;st.selected=null;st.solved=false' in ui,
 'QA-09 legacy recommendations suppressed':'id="v6Recommendations" hidden' in html,
 'QA-10 1 puzzle is not /15':'kind===\'puzzle\'?r.message' in ui,
 'QA-11 promotion guidance':'폰이 마지막 줄에 도달하면 퀸·룩·비숍·나이트' in html,
 'Preserves corpus':(root/'puzzles_lichess.jsonl').is_file() and (root/'puzzles_lichess.jsonl').stat().st_size > 0,
}
for k,ok in checks.items():print(('PASS' if ok else 'FAIL'),k)
assert all(checks.values())
