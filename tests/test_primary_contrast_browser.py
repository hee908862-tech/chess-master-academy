"""Computed primary contrast and focus on real local pages; no production writes."""
import json,re
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page
from test_study_browser import login

OUT=Path('/tmp/cma-primary-contrast-evidence')

def contrast(el):
    c=el.evaluate("e=>{const s=getComputedStyle(e);return {text:s.color,background:s.backgroundImage,opacity:s.opacity}}")
    def lum(rgb):
        v=[int(n)/255 for n in rgb]
        return sum(w*(x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4) for w,x in zip([.2126,.7152,.0722],v))
    fg=lum(re.findall(r'\d+',c['text'])[:3])
    stops=re.findall(r'rgb\((\d+), (\d+), (\d+)\)',c['background'])
    assert len(stops)==2,c
    c['ratios']=[(max(fg,lum(s))+.05)/(min(fg,lum(s))+.05) for s in stops]
    return c

@pytest.mark.parametrize('width,height',[(320,800),(1280,720)])
def test_main_actions_contrast_keyboard_and_narrow_layout(page,site,width,height):
    login(page,site);page.set_viewport_size(dict(width=width,height=height))
    OUT.mkdir(exist_ok=True);measurements={}
    for view,selector in [('home','#journeyHomeOpen'),('play','#newGame'),('diagnosis','#journeyStart'),('training','#learningFresh'),('learn','#foundationPrimary button')]:
        page.evaluate("v=>v==='learn'?cmaNavigation.go('learn/basics'):tab(v)",view)
        target=page.locator(selector);expect(target).to_be_visible();expect(target).to_be_enabled()
        page.keyboard.press('Tab');target.focus();target.scroll_into_view_if_needed();page.wait_for_timeout(200)
        expect(target).to_be_focused()
        assert target.evaluate("e=>getComputedStyle(e).outlineStyle")!='none'
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        if view!='learn':
            c=contrast(target);measurements[view]=c
            assert min(c['ratios'])>=4.5,(view,c)
            target.hover();page.wait_for_timeout(200)
            assert min(contrast(target)['ratios'])>=4.5
        page.screenshot(path=str(OUT/f'{view}-{width}.png'))
    (OUT/f'computed-{width}.json').write_text(json.dumps(measurements,indent=2))


def test_foundation_waiting_error_reason_and_primary_disabled_style(page,site):
    login(page,site);page.set_viewport_size(dict(width=360,height=800));page.evaluate("cmaNavigation.go('learn/basics')")
    target=page.locator('#foundationPrimary button');expect(target).to_be_enabled()
    waits=[];page.route('**/api/foundations/action',lambda r:waits.append(r))
    target.click()
    for _ in range(100):
        if waits:break
        page.wait_for_timeout(20)
    assert len(waits)==1
    expect(page.locator('#foundationAcademy')).to_have_attribute('aria-busy','true')
    expect(target).to_be_disabled()
    expect(page.locator('#foundationStatus')).not_to_be_empty()
    waits[0].fulfill(status=503,json={'detail':'검사 중 임시 저장 실패'})
    expect(page.locator('#foundationStatus')).to_contain_text('검사 중 임시 저장 실패')
    expect(page.locator('#foundationReload')).to_be_enabled()
    # Style-only controlled disabled state; no game request or account mutation.
    page.evaluate("tab('play');document.getElementById('newGame').disabled=true")
    el=page.locator('#newGame');expect(el).to_be_disabled()
    page.wait_for_function("getComputedStyle(document.getElementById('newGame')).opacity==='0.5'")
    assert contrast(el)['opacity']=='0.5'
    page.keyboard.press('Tab');assert not el.evaluate('e=>e===document.activeElement')
    OUT.mkdir(exist_ok=True);el.scroll_into_view_if_needed();page.screenshot(path=str(OUT/'disabled-360.png'))
