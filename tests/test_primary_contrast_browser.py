"""Computed primary contrast and focus on real local pages; no production writes."""
import json,re
from pathlib import Path
import pytest
from playwright.sync_api import expect
from test_qa_browser import site,page
from test_study_browser import login

OUT=Path('/tmp/cma-primary-contrast-evidence')

def contrast(el):
    c=el.evaluate("""e=>{const s=getComputedStyle(e),layers=[];for(let n=e;n;n=n.parentElement){const p=getComputedStyle(n);layers.push({color:p.backgroundColor,image:p.backgroundImage});}return {text:s.color,background:s.backgroundImage,opacity:s.opacity,layers};}""")
    def colors(value):
        return [[float(x) for x in re.findall(r'[\d.]+',rgb)] for rgb in re.findall(r'rgba?\([^)]+\)',value)]
    def blend(top,bottom):
        alpha=top[3] if len(top)==4 else 1
        return [top[i]*alpha+bottom[i]*(1-alpha) for i in range(3)]
    def lum(rgb):
        v=[n/255 for n in rgb]
        return sum(w*(x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4) for w,x in zip([.2126,.7152,.0722],v))
    backgrounds=[[255,255,255]]
    for layer in reversed(c['layers']):
        solid=colors(layer['color']);assert len(solid)==1,layer
        backgrounds=[blend(solid[0],base) for base in backgrounds]
        if layer['image']!='none':
            stops=colors(layer['image']);assert stops,layer
            # Include every gradient stop over every possible underlying stop.
            # The minimum ratio is conservative for these light-on-dark controls.
            backgrounds=[blend(stop,base) for stop in stops for base in backgrounds]
    fg=lum(colors(c['text'])[0])
    c['ratios']=[(max(fg,lum(bg))+.05)/(min(fg,lum(bg))+.05) for bg in backgrounds]
    return c

@pytest.mark.parametrize('width,height',[(320,800),(1280,720)])
def test_main_actions_contrast_keyboard_and_narrow_layout(page,site,width,height):
    login(page,site);page.set_viewport_size(dict(width=width,height=height))
    OUT.mkdir(exist_ok=True);measurements={}
    for view,selector in [('home','#homeNextAction > button'),('play','#newGame'),('diagnosis','#journeyStart'),('training','#learningFresh'),('learn','#foundation-recommended-action')]:
        page.evaluate("v=>v==='learn'?cmaNavigation.go('learn/basics'):tab(v)",view)
        if view=='diagnosis':page.locator('#diagnosticOther > summary').click()
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
    target=page.locator('#foundation-recommended-action');expect(target).to_be_enabled()
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
