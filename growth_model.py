from engine_budget import open_engine, EngineBusy
"""Versioned app exercise performance; no population rating or Elo conversion."""
import copy
import math
import threading
_diagnostic_slot=threading.BoundedSemaphore(1)
from competencies import COMPETENCIES, position_key
from skill_index import VERSION as SKILL_VERSION, score_areas, summary as skill_summary

VERSION='growth-v1'
BANDS=((600,1200),(1200,1800))
MODES=('balanced','quick')


def area_score(items):
    eligible=[i for i in items if i.get('app_new') and i.get('first_attempt',True) and not i.get('helped') and i.get('outcome') in ('completed','partial_execution','verified_non_mate','verified_error')]
    groups=[[i for i in eligible if tuple(i.get('band',[]))==band] for band in BANDS]
    observed=len(eligible)
    # Each difficulty band has equal weight; missing/uncertain work never becomes zero.
    values=[sum(1 if i.get('outcome')=='completed' else min(1,i.get('correct_plies',0)/max(1,i.get('total_plies',1))) for i in g)/len(g) if g else None for g in groups]
    score=round(sum(values)*50) if all(v is not None for v in values) else None
    comparable=all(len(g)>=2 for g in groups)
    # Conservative distribution-free range for a bounded mean in each stratum.
    margin=min(100,100*sum(math.sqrt(math.log(40)/(2*len(g))) for g in groups)/2) if all(groups) else None
    return {'score':score,'observed':observed,'band_counts':[len(g) for g in groups],
            'comparable':comparable,'range':[max(0,round(score-margin)),min(100,round(score+margin))] if score is not None else None,
            'condition':'같은 비중의 기초·응용 수순 수행, 도움 없이 처음 본 위치','confidence':'초기 관찰' if observed<12 else '누적 확인 필요'}


def decorate(report):
    """Called only for new sessions. Old reports are never rewritten."""
    if report.get('mode') not in (*MODES,'domain','subskill'):return report
    new_scale=report.get('scoring_version')==SKILL_VERSION
    report['score_version']=SKILL_VERSION if new_scale else VERSION
    scores=score_areas(report['items']) if new_scale else None
    if new_scale and report.get('mode') in MODES:report['internal_skill']=skill_summary(scores)
    for area in report['areas']:
        items=[i for i in report['items'] if i['competency']==area['id']]
        area['performance']=scores[area['id']] if new_scale else area_score(items)
        attempted=sum(bool(i.get('submitted')) for i in items)
        area['observation']=f"{len(items)}문제 중 {attempted}개에 도전해 {area['full_success']}개 수순을 끝까지 풀었어요."
        if not COMPETENCIES[area['id']]['measured']:area['observation']='아직 측정하지 않은 분야예요. 점수를 만들지 않습니다.'
        elif not attempted:area['observation']='아직 직접 둔 수가 없어요. 쉬운 문제부터 함께 확인해 보세요.'
        elif area['partial']:area['observation']+=f" {area['partial']}개는 첫 판단 뒤 이어지는 수를 더 연습해 보세요."
        elif area['unverified']:area['observation']+=' 다른 답을 낸 문제는 정답 수순과 비교해 보세요.'
    measured=[a for a in report['areas'] if a['count']]
    errors=lambda a:sum(i.get('outcome') in ('partial_execution','verified_error','verified_non_mate') for i in a['items'])
    ordered=sorted(measured,key=lambda a:(-errors(a),-a['unverified'],a['full_success']))
    tied=len({(errors(a),a['unverified'],a['full_success']) for a in measured})<=1
    attempted_total=sum(bool(i.get('submitted')) for i in report['items'])
    all_full=all(a['full_success']==a['count'] for a in measured)
    message=('아직 직접 둔 수가 없어요. 기초 문제를 연습하거나 한 분야부터 추가로 확인해 보세요.' if not attempted_total else '모든 수순을 완주했어요. 더 높은 난도의 추가 진단으로 도전 범위를 넓혀 보세요.' if all_full else '기초 수순부터 차근차근 익혀 보세요. 힌트와 해설을 보며 추천 과제를 마칠 수 있어요.' if not any(a['full_success'] for a in measured) else '분야별 수행이 고르게 나타났어요. 더 많은 위치에서 확인해 보세요.' if tied else '끝까지 푼 수순과 다음에 연습할 부분을 확인해 보세요.')
    report['insights']={'strengths':[{'id':a['id'],'label':a['label'],'reason':a['observation']} for a in measured if a['full_success']>=2][:3],
                        'priorities':[] if tied else [{'id':a['id'],'label':a['label'],'reason':a['observation']} for a in ordered if errors(a)>0][:3],
                        'balanced':tied,'message':message}
    # Fixed five assignments: two original exercises, two novel applications, one mixed novel.
    chosen=ordered[:2] if not tied else measured[:2]
    plan=[]
    for area in chosen:
        source=next((i for i in report['items'] if i['competency']==area['id'] and not i.get('complete')),next(i for i in report['items'] if i['competency']==area['id']))
        for kind in ('original','application'):
            plan.append({'id':str(len(plan)+1),'competency':area['id'],'item_id':source['id'],'kind':kind,
                         'label':area['label']+(' · 다시 익히기' if kind=='original' else ' · 새 문제에 적용'),
                         'reason':area['observation']})
    if measured:
        mixed=next((a for a in measured if a not in chosen),measured[0]);source=next(i for i in report['items'] if i['competency']==mixed['id'])
        plan.append({'id':str(len(plan)+1),'competency':mixed['id'],'item_id':source['id'],'kind':'application','label':mixed['label']+' · 함께 확인하기','reason':'다른 분야의 새 문제로 배운 판단을 넓혀 보세요.'})
    report['training_plan']=plan
    if report.get('diagnostic_scope'):
        from diagnostic_blueprint import training_recommendations
        report['scoped_training']=training_recommendations(report)
    report['snapshot']={'version':report['score_version'],'assessment_version':report['version'],'competency_version':report['competency_version'],'mode':report['mode'],
                        'scope':report['measurement_scope'],'answer_policy':report.get('answer_policy','reference-line-v1'),'diagnostic_scope':report.get('diagnostic_scope'),'corpus':report.get('corpus_sha256'),'at':report['at'],'areas':{a['id']:copy.deepcopy(a['performance']) for a in report['areas']}}
    return report


def latest_cycle_report(reports):
    return next((r for r in reversed(reports) if r.get('score_version') in (VERSION,SKILL_VERSION) and r.get('mode') in MODES),None)


def cycle_status(report,learning):
    if not report:return None
    cycle=learning.get('cycles',{}).get(report['id'],{})
    done=cycle.get('completed',{})
    tasks=[{**t,**({'completion':copy.deepcopy(done[t['id']])} if t['id'] in done else {})} for t in report['training_plan']]
    count=sum('completion' in t for t in tasks)
    return {'report_id':report['id'],'tasks':tasks,'completed':count,'required':5,'remaining':max(0,5-count),'unlocked':count>=5,
            'message':'다섯 과제를 마쳤어요. 새로운 문제로 성장한 부분을 확인해 보세요.' if count>=5 else f'추천 과제 {5-count}개를 더 마치면 다시 진단할 수 있어요.'}


def credit_cycle(state,session,attempt):
    ref=session.get('growth_task')
    if not ref or attempt.get('success') is not True or attempt.get('assessment_scope')!='full_line' or session.get('turns',0)<1:return
    cycle=state.get('cycles',{}).get(ref['report_id'])
    if not cycle or cycle.get('cards',{}).get(ref['task_id'])!=session['card_id']:return
    done=cycle.setdefault('completed',{})
    if ref['task_id'] in done:return
    position=attempt['position']
    if any(c['position']==position for c in done.values()):return
    done[ref['task_id']]={'at':attempt['at'],'session_id':session['id'],'card_id':session['card_id'],'position':position,
                          'helped':attempt['helped'],'turns':session['turns']}


def verify_loss(fen,move,path):
    """Bounded evidence, including why an alternative could not be judged."""
    import chess
    import chess.engine
    import time
    import logging
    from pathlib import Path
    started=time.monotonic();timings={};stage='validation'
    evidence={'timings_ms':timings,'status':'unverified','reason':'engine_unavailable','policy':'alternative-v2',
              'settings':{'threads':1,'hash_mb':16,'seconds_per_position':.3,'max_depth':16,'minimum_depth':10}}
    if not path or not Path(path).is_file():return evidence
    if not _diagnostic_slot.acquire(blocking=False):return {**evidence,'reason':'diagnosis_busy'}
    try:
        board=chess.Board(fen);side=board.turn;m=chess.Move.from_uci(move)
        if not board.is_valid() or m not in board.legal_moves:return {**evidence,'reason':'invalid_position_or_move'}
        stage='startup'
        with open_engine(path,timeout=3,timings=timings) as engine:
            stage='configure';t=time.monotonic()
            engine.configure({'Threads':1,'Hash':16})
            timings['configure_ms']=round((time.monotonic()-t)*1000,3)
            stage='analysis_before';t=time.monotonic()
            try:first=engine.analyse(board,chess.engine.Limit(time=.3,depth=16))
            finally:timings['analysis_before_ms']=round((time.monotonic()-t)*1000,3)
            board.push(m);stage='analysis_after';t=time.monotonic()
            try:second=engine.analyse(board,chess.engine.Limit(time=.3,depth=16)) if not board.is_game_over() else {'score':chess.engine.PovScore(chess.engine.Cp(0),side),'depth':first.get('depth',0)}
            finally:timings['analysis_after_ms']=round((time.monotonic()-t)*1000,3)
            stage='evaluation'
            depths=[first.get('depth',0),second.get('depth',0)]
            a=first['score'].pov(side);b=second['score'].pov(side)
            evidence.update(engine=engine.id.get('name'),depths=depths,depth=min(depths),before_cp=a.score(),after_cp=b.score(),before_mate=a.mate(),after_mate=b.mate())
            if min(depths)<10:return {**evidence,'reason':'insufficient_depth'}
            if a.score() is None or b.score() is None:return {**evidence,'reason':'mate_requires_proof'}
            loss=max(0,a.score()-b.score());evidence['loss_cp']=loss
            return {**evidence,'status':'verified_error' if loss>=200 else 'equivalent_alternative' if loss<=35 else 'unverified',
                    'reason':'large_loss' if loss>=200 else 'similar_evaluation' if loss<=35 else 'uncertain_difference'}
    except EngineBusy:return {**evidence,'reason':'engine_busy'}
    except (ValueError,KeyError,OSError,chess.engine.EngineError,TimeoutError) as exc:
        evidence.pop('loss_cp',None)
        return {**evidence,'reason':'engine_failure','error_type':type(exc).__name__,'failure_stage':getattr(exc,'engine_failure_stage',stage)}
    finally:
        timings['total_ms']=round((time.monotonic()-started)*1000,3)
        logging.getLogger(__name__).info('diagnostic_engine_timing stage=%s timings_ms=%s',stage,timings)
        _diagnostic_slot.release()


ANSWER_POLICY = 'goal-alternatives-v1'


def prove_mate_alternative(fen, move, item, correct_plies=0, *, max_nodes=6000, seconds=.15):
    """Exhaustive bounded mate objective, not an engine evaluation or win estimate.

    All legal defender replies must admit a mating continuation within the original
    remaining own-move allowance. Budget exhaustion is unknown, never a negative.
    Original item/line are read-only; returned PV is a separate execution branch.
    """
    import chess
    import time
    tags=item.get('tags',[])
    if not any(t.startswith('mateIn') for t in tags):return None
    try:
        original=chess.Board(item['fen'])
        for u in item['line']:original.push_uci(u)
        if not original.is_checkmate():return None
        remaining=(len(item['line'])+1)//2-correct_plies
        if not 1<=remaining<=3:return None
        board=chess.Board(fen);side=board.turn;m=chess.Move.from_uci(move)
        if not board.is_valid() or m not in board.legal_moves:return None
    except (ValueError,KeyError,TypeError):return None
    started=time.monotonic();nodes=0;cache={}
    base={'policy':ANSWER_POLICY,'basis':'all_legal_defenses','objective':'mate_within_original_bound',
          'remaining_own_moves':remaining,'limits':{'nodes':max_nodes,'seconds':seconds},'status':'unverified'}
    class Budget(Exception):pass
    def solve(b,left):
        nonlocal nodes
        nodes+=1
        if nodes>max_nodes or time.monotonic()-started>seconds:raise Budget()
        if b.is_checkmate():return (b.turn!=side,[])
        if b.is_game_over() or left<=0:return (False,[])
        key=(b.fen(),left)
        if key in cache:return cache[key]
        attacker=b.turn==side
        moves=sorted(b.legal_moves,key=lambda x:(not b.gives_check(x),x.uci()))
        best=[]
        for candidate in moves:
            b.push(candidate);ok,pv=solve(b,left-1);b.pop()
            if attacker and ok:
                result=(True,[candidate.uci()]+pv);cache[key]=result;return result
            if not attacker and not ok:
                cache[key]=(False,[]);return (False,[])
            if not attacker and len(pv)+1>len(best):best=[candidate.uci()]+pv
        result=(not attacker,best if not attacker else [])
        cache[key]=result;return result
    board.push(m)
    try:
        ok,pv=solve(board,2*remaining-2)
        return {**base,'status':'verified_goal' if ok else 'verified_non_mate',
                'reason':'forced_mate_proved' if ok else 'no_mate_within_bound','continuation':pv,'nodes':nodes,
                'elapsed_ms':round((time.monotonic()-started)*1000,3)}
    except Budget:
        return {**base,'reason':'mate_proof_budget','nodes':nodes,'elapsed_ms':round((time.monotonic()-started)*1000,3)}
