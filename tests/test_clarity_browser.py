"""Clarity flows against isolated local APIs; viewport emulation, not user research."""
import re
import chess
from playwright.sync_api import expect
from test_redesign_browser_followup import isolated, site
from test_activity_flow_browser import start, home, fit


def solution_positions():
    from v9_server import LIB
    answers={}
    for row in LIB.values():
        board=chess.Board(row['fen'])
        for i,move in enumerate(row['moves']):
            if i%2: answers[board.fen()]=move
            board.push_uci(move)
    return answers


def play(page,board,move):
    page.locator(f'#{board} [aria-label^="{move[:2]} "]').click()
    page.locator(f'#{board} [aria-label^="{move[2:4]} "]').click()
    if len(move)==5:
        page.locator('#cmaPromotionModal').get_by_role('button',name=re.compile({'q':'퀸','r':'룩','b':'비숍','n':'나이트'}[move[4]])).click()


def test_real_diagnosis_to_recommendation_and_completed_training(isolated):
    page,_=isolated;start(page);page.evaluate("tab('diagnosis')")
    expect(page.locator('#resultNextAction')).to_be_hidden()
    page.locator('.diagnostic-choice[data-scope=subskill]').click()
    page.get_by_label('진단 분야',exact=True).select_option('mate')
    page.get_by_label('진단 하위 기술',exact=True).select_option('mateIn1')
    page.locator('#diagnosticBegin').click()
    expect(page.locator('#journeyTask')).to_be_visible()
    answers=solution_positions()
    for _ in range(40):
        state=page.evaluate("api('/journey')")['active']
        if not state: break
        if state['phase']=='feedback':
            page.locator('#journeyNext').click()
        elif state['phase']=='question':
            move=answers[state['question']['fen']]
            with page.expect_response('**/api/journey/action'): play(page,'journeyBoard',move)
        else: break
        page.wait_for_function('!cmaJourney.status().busy')
    report=page.evaluate("api('/journey')")['latest']
    assert report['diagnostic_scope']['level']=='subskill'
    assert report['scoped_training']['tasks']
    expect(page.locator('#resultNextAction > button')).to_contain_text('새 문제로 연습')
    page.locator('#resultNextAction > button').click()
    expect(page.locator('#learningBoard .sq')).to_have_count(64)
    expect(page.locator('#trainingTaskBrief')).to_contain_text('전체 수순')
    state=page.evaluate("api('/learning/dashboard')")['active']
    for _ in range(25):
        if state['done']: break
        with page.expect_response('**/api/learning/action') as response: play(page,'learningBoard',answers[state['fen']])
        state=response.value.json()
        page.wait_for_timeout(250)
    assert state['done'] and state['scoped_task']
    page.locator('#learningControls').get_by_role('button',name='추천 훈련과 진행률 보기').click()
    expect(page.locator('#resultNextAction')).to_contain_text('이번 추천 훈련을 마쳤습니다')
    expect(page.locator('[data-scoped-report]')).to_be_disabled()
    saved=page.evaluate("api('/learning/dashboard')")
    assert len(saved['scoped_completed'])==1
    home(page);expect(page.locator('#homeNextAction')).to_contain_text('성장을 확정하지 않습니다')
    page.reload();expect(page.locator('#homeNextAction')).to_contain_text('이번 추천 훈련을 마쳤습니다')
    assert page.evaluate("api('/learning/dashboard')")['scoped_completed']==saved['scoped_completed']

import pytest
from pathlib import Path

@pytest.mark.parametrize('width,height',[(1366,768),(1180,650),(360,800),(390,844),(844,390)])
def test_all_destinations_keyboard_zoom_and_real_review(isolated,width,height):
    page,_=isolated;page.set_viewport_size(dict(width=width,height=height));start(page)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    for route in ['home','learn','learn/basics','learn/basics/practice','learn/tactics','learn/education','puzzle','training','diagnosis','opening','play','review','profile','profile/settings']:
        page.evaluate('(r)=>cmaNavigation.go(r)',route)
        page.wait_for_timeout(150);fit(page)
    page.evaluate("tab('diagnosis')")
    card=page.locator('.diagnostic-choice[data-scope=domain]');card.focus();page.keyboard.press('Enter')
    expect(card).to_have_attribute('aria-pressed','true')
    expect(page.get_by_label('진단 범위',exact=True)).to_be_hidden()
    page.evaluate("tab('puzzle')");page.locator('#v9PuzzleStart').click()
    expect(page.locator('#v9PuzzleBoard .sq')).to_have_count(64)
    expect(page.locator('#focusPuzzleSelection')).not_to_have_attribute('open','')
    fit(page)
    page.evaluate("tab('training')");page.locator('#learningFresh').click()
    expect(page.locator('#trainingTaskBrief')).to_contain_text('첫 수 1개만')
    assert '기준 충족' not in page.locator('#trainingTaskBrief').inner_text()
    assert page.locator('#trainingTaskBrief').bounding_box()['y']<page.locator('#learningBoard').bounding_box()['y']
    saved=page.evaluate("api('/learning/dashboard')")['active'];fit(page)
    page.evaluate("document.body.style.zoom='2'")
    fit(page);page.evaluate("document.body.style.zoom='1'")
    page.evaluate("tab('play')");page.locator('#gameSettings').evaluate('(e)=>e.open=true')
    page.locator('#playerColor').select_option('white');page.locator('#aiLevel').select_option('1');page.locator('#newGame').click()
    expect(page.locator('#gameBoard .sq')).to_have_count(64)
    expect(page.locator('#v7Hint')).to_be_visible();expect(page.locator('#v7Undo')).to_be_visible();fit(page)
    play(page,'gameBoard','e2e4');page.wait_for_function("game?.board?.turn==='white'||game?.turn==='white'",timeout=20000)
    page.locator('#gameTools').evaluate('(e)=>e.open=true');page.on('dialog',lambda d:d.accept());
    with page.expect_response('**/api/game/resign') as resigned: page.locator('#resign').click()
    assert resigned.value.ok
    page.evaluate("tab('review')");expect(page.locator('#reviewLoad')).to_be_enabled();page.locator('#reviewLoad').click()
    expect(page.locator('#reviewBoard .sq')).to_have_count(64,timeout=30000)
    expect(page.locator('#reviewSelection')).not_to_have_attribute('open','')
    page.locator('#reviewNext').click();expect(page.locator('#reviewReasonBrief')).to_contain_text('e4')
    fit(page);page.locator('#reviewSelection > summary').click();expect(page.locator('#reviewGameSelect')).to_be_visible()
    assert page.evaluate("api('/learning/dashboard')")['active']==saved
    assert not errors
    out=Path('docs/qa-whole-app');out.mkdir(exist_ok=True)
    page.screenshot(path=str(out/f'review-{width}x{height}.png'))


def test_original_explanation_is_retained_and_labels_are_explicit(isolated):
    page,_=isolated;start(page)
    original='룩은 같은 파일에서 움직입니다. 디스커버드 어택을 확인하세요.'
    page.evaluate('(v)=>document.getElementById("foundationFeedback").textContent=v',original)
    expect(page.locator('#foundationReasonBrief')).to_contain_text('같은 세로줄(파일)')
    expect(page.locator('#foundationReasonBrief')).to_contain_text('원문 확인')
    page.locator('#foundationExplanation > summary').click()
    expect(page.locator('#foundationFeedback')).to_have_text(original)
    page.evaluate("tab('training')");page.locator('#learningFresh').click()
    expect(page.locator('#learningBoard .sq')).to_have_count(64)
    saved=page.evaluate("api('/learning/dashboard')")
    page.evaluate('(v)=>document.getElementById("learningExplanation").textContent=v',original)
    expect(page.locator('#learningPlainExplanation')).to_contain_text('세로줄(파일)')
    page.locator('#learningOriginalExplanation > summary').click()
    expect(page.locator('#learningExplanation')).to_have_text(original)
    assert page.evaluate("api('/learning/dashboard')")==saved


def test_slow_read_keeps_recent_destination_and_coalesces_gets(isolated):
    page,_=isolated;start(page);page.evaluate("tab('diagnosis')")
    page.locator('.diagnostic-choice[data-scope=domain]').click();page.locator('#diagnosticBegin').click()
    expect(page.locator('#journeyTask')).to_be_visible()
    saved=page.evaluate("api('/journey')");home(page)
    pending=[];page.route('**/api/journey',lambda r:pending.append(r));page.reload()
    expect(page.locator('#homeNextAction > button')).to_be_disabled()
    expect(page.locator('#homeNextAction')).to_contain_text('조회가 지연',timeout=7000)
    assert len(pending)==1
    for r in pending:r.fulfill(json=saved)
    page.unroute('**/api/journey')
    expect(page.locator('#homeNextAction > button')).to_have_text('진단 이어하기')
    page.locator('#homeNextAction > button').click();expect(page.locator('#journeyTask')).to_be_visible()
    assert page.evaluate("api('/journey')")['active']==saved['active']
