"""Initial-course engagement is explicit; scoped result reads cannot start it."""
from test_redesign_browser_followup import isolated,site
from test_movement_browser import enter


def test_scoped_history_does_not_engage_initial_but_started_course_keeps_priority(isolated,site):
    page,_=isolated;enter(page)
    before=page.evaluate("api('/journey')")
    assert before['initial_profile']['state']=='not_started'
    result=page.evaluate("""j=>{
      const scoped={...j,active:null,results:[{id:'display-only-scoped-result',diagnostic_scope:{mode:'domain'}}]};
      const choose=state=>cmaInitial.recommendation({...scoped,initial_profile:{...j.initial_profile,state}},null,{},false)?.label||null;
      return {notStarted:choose('not_started'),started:choose('in_progress'),
        active:cmaInitial.recommendation({...scoped,active:{initial_course:true}},null,{},false).label};
    }""",before)
    assert result=={'notStarted':None,'started':'초기 진단 이어하기','active':'진단 이어하기'}
    assert page.evaluate("api('/journey')")==before
