/* Account-persisted introduction. Navigation never starts an assessment or a game. */
(() => {
  const steps = [
    ['나에게 필요한 학습부터', '실력 진단으로 현재 확인된 수행과 아직 확인하지 못한 부분을 구분합니다. 평가에서는 먼저 혼자 풀고, 훈련에서는 도움을 활용하세요.'],
    ['첫 단계로 실력 진단을 추천해요', '진단 화면에서 문항 수와 저장 방식을 확인한 뒤 직접 시작하세요. 진행 중인 진단은 이어갈 수 있습니다. 이 안내는 진단을 시작하거나 초기화하지 않습니다.'],
    ['결과의 근거에서 훈련으로', '틀린 수와 놓친 응수를 확인하고 연결된 훈련을 선택하세요. 도움을 받은 연습과 새로운 국면의 독립 수행을 구분하며, 근거가 부족하면 추가 확인이 필요하다고 표시합니다.'],
    ['자유롭게 연습하고 돌아오세요', '자유 대국, 퍼즐, 아카데미와 복기도 계속 이용할 수 있습니다. 프로필이나 도움말에서 이 안내를 다시 볼 수 있습니다.']
  ];
  const dialog = document.createElement('dialog');
  dialog.id = 'onboardingDialog';
  dialog.setAttribute('aria-labelledby', 'onboardingTitle');
  dialog.setAttribute('aria-describedby', 'onboardingText');
  dialog.innerHTML = `<div class="onboarding-content"><p id="onboardingProgress" aria-live="polite"></p><h2 id="onboardingTitle" tabindex="-1"></h2><p id="onboardingText"></p><p class="onboarding-clock">안내를 열어도 진행 중인 대국 시계는 멈추지 않습니다.</p><p id="onboardingError" role="status"></p><div class="onboarding-actions"><button type="button" id="onboardingSkip" class="btn">건너뛰기 · 닫기</button><button type="button" id="onboardingBack" class="btn">이전</button><button type="button" id="onboardingNext" class="btn primary">다음</button></div></div>`;
  document.body.append(dialog);
  const byId = id => document.getElementById(id);
  let state = null, step = 0, account = '', saving = false, opener = null, generation = 0, modalCycle = 0;
  const banner = document.createElement('aside');
  banner.id = 'onboardingInvitation'; banner.hidden = true;
  banner.innerHTML = '<span>진단부터 훈련까지, 사용 안내를 확인하세요. 진행 중인 대국 시계는 멈추지 않습니다.</span> <button type="button" class="btn tiny">사용 안내 보기</button>';
  (document.querySelector('.main') || document.body).prepend(banner);
  banner.querySelector('button').onclick = () => open();
  function draw() {
    byId('onboardingProgress').textContent = `${step + 1} / ${steps.length}`;
    byId('onboardingTitle').textContent = steps[step][0];
    byId('onboardingText').textContent = steps[step][1];
    byId('onboardingBack').disabled = step === 0 || saving;
    byId('onboardingNext').textContent = step === 3 ? '안내 완료 · 진단 화면 보기' : '다음';
    byId('onboardingNext').disabled = saving;
    byId('onboardingSkip').disabled = false;
  }
  function close() {
    modalCycle++;
    if (dialog.open) dialog.close();
    if (opener?.isConnected) opener.focus();
  }
  async function persist(status, nextStep) {
    if (!token || token !== account) { close(); return false; }
    const requestAccount = account;
    saving = true; draw(); byId('onboardingError').textContent = '';
    try {
      const result = await api('/onboarding', 'POST', {status, step: nextStep});
      if (token !== requestAccount) { close(); return false; }
      state = result;
      banner.hidden = ['completed', 'skipped'].includes(result.status);
      return true;
    } catch (error) {
      byId('onboardingError').textContent = '안내 상태를 저장하지 못했습니다. 다시 시도하거나 닫을 수 있습니다. ' + error.message;
      return false;
    } finally { saving = false; draw(); }
  }
  async function open() {
    if (!token) { if (typeof ready === 'function') ready('profile'); return; }
    account = token;
    modalCycle++;
    opener = document.activeElement;
    step = state?.status === 'in_progress' ? state.step : 0;
    draw(); byId('onboardingError').textContent = '';
    if (!dialog.open) dialog.showModal();
    byId('onboardingTitle').focus();
  }
  async function skip() {
    const alreadySaving = saving;
    // Closing always stays possible, even if the persistence request fails.
    close();
    if (alreadySaving) return;
    if (!await persist('skipped', step)) {
      banner.hidden = false;
      banner.querySelector('span').textContent = '안내를 닫았습니다. 계정에 저장하지 못해 다음 접속에서 다시 안내될 수 있습니다.';
    }
  }
  byId('onboardingSkip').onclick = skip;
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.querySelectorAll('button:not(:disabled)')];
    const first = controls[0], last = controls.at(-1);
    if (!first) { event.preventDefault(); return; }
    if (event.shiftKey && (document.activeElement === first || document.activeElement === byId('onboardingTitle'))) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  dialog.addEventListener('cancel', event => { event.preventDefault(); skip(); });
  byId('onboardingBack').onclick = async () => {
    const cycle = modalCycle;
    if (step > 0 && await persist('in_progress', step - 1) && dialog.open && cycle === modalCycle) { step--; draw(); byId('onboardingTitle').focus(); }
  };
  byId('onboardingNext').onclick = async () => {
    const cycle = modalCycle;
    if (await persist(step === 3 ? 'completed' : 'in_progress', Math.min(3, step + 1)) && dialog.open && cycle === modalCycle) {
      if (step === 3) { close(); tab('diagnosis'); }
      else { step++; draw(); byId('onboardingTitle').focus(); }
    }
  };
  async function check(auto = false) {
    const request = ++generation, requestAccount = token;
    if (!requestAccount) { banner.hidden = true; close(); return; }
    try {
      const result = await api('/onboarding');
      if (request !== generation || token !== requestAccount) return;
      account = requestAccount; state = result;
      const pending = !['completed', 'skipped'].includes(state.status);
      banner.hidden = !pending;
      if (auto && pending && !state.defer_auto) open();
    } catch (_) { /* Existing application remains usable; manual replay stays available. */ }
  }
  for (const id of ['profile', 'help']) {
    const host = byId(id);
    if (!host) continue;
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'btn onboarding-replay';
    button.textContent = '사용 안내 다시 보기'; button.onclick = async () => { await check(); open(); };
    host.prepend(button);
  }
  const originalAuth = auth;
  auth = async function(...args) {
    const hadPin = !!byId('pinField')?.value;
    await originalAuth(...args);
    if (hadPin && token && !byId('pinField')?.value) await check(true);
  };
  byId('signout')?.addEventListener('click', () => { generation++; banner.hidden = true; close(); state = null; });
  window.cmaOnboarding = {open, check};
  check();
})();
