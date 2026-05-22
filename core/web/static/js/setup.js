const TRANSLATIONS = {
  en: {
    configured_subtitle:   'MCUB is already configured',
    configured_title:        'Welcome to MCUB!',
    configured_hint:         'Your instance is already configured and ready to use.',
    subtitle_setup:       'First-time setup',
    subtitle_reauth:      'Session Expired',
    subtitle_bot:         'Inline Bot Settings',
    step_credentials:     'Credentials',
    step_scan:            'Scan',
    step_code:            'Code',
    step_bot:             'Bot',
    step_done:            'Done',
    s1_title:             'API Credentials',
    s1_hint:              'Open <a href="https://my.telegram.org" target="_blank">my.telegram.org</a> → API development tools → create app → paste values below.',
    label_api_id:         'API ID',
    label_api_hash:       'API Hash',
    label_phone:          'Phone number',
    btn_send_code:        'Send code',
    btn_qr_code:          'QR Code',
    s1qr_title:           'Scan QR Code',
    s1qr_hint:            'Scan this QR code with your Telegram app to log in.',
    qr_waiting:           'Waiting for scan...',
    btn_back:             'Back',
    btn_check_again:      'Check Again',
    s2_title:             'Telegram Code',
    s2_hint:              'A code was sent to your Telegram account. Enter it below.',
    label_code:           'Code',
    btn_back_arrow:       '← Back',
    btn_verify:           'Verify →',
    s3_title:             'Two-Factor Auth',
    s3_hint:              'Your account has 2FA enabled. Enter your cloud password.',
    label_cloud_password: 'Cloud password', // pragma: allowlist secret
    btn_confirm:          'Confirm →',
    s4_title:             'Inline Bot (Optional)',
    s4_hint:              'Create a bot via @BotFather for inline buttons support.<br>Or skip this step and create bot later in settings.',
    label_bot_token_skip: 'Bot Token (leave empty to skip)',
    btn_verify_token:     'Verify Token',
    btn_auto_create:      'Auto Create Bot',
    btn_skip:             'Skip →',
    btn_continue:         'Continue →',
    s5_title:             'MCUB is installed!',
    s5_hint:              'Kernel is starting - redirecting to dashboard…',
    kernel_waiting:       'Waiting for kernel…',
    kernel_ready:         '✅ Kernel ready! Redirecting…',
    kernel_poll:          'Waiting for kernel… ({n})',
    reset_configured:     'Already configured?',
    reset_link:           'Reset & reconfigure',
    bot_settings_link:    'Bot Settings',
    reset_fresh:          'Reset & start fresh',
    modal_title:          'Choose Login Method',
    modal_hint:           'How would you like to log in to your Telegram account?',
    modal_qr:             'Login via QR Code',
    modal_code:           'Send Code',
    btn_cancel:           'Cancel',
    footer:               'MCUB Kernel - setup wizard',
    reauth_title:         'Re-authenticate',
    reauth_hint:          'Your session has expired. Please log in again to continue.',
    bot_form_title:       'Bot Token',
    bot_form_hint:        'Create a bot via @BotFather in Telegram, then enter the token below.',
    label_bot_token:      'Bot Token',
    btn_save_token:       'Save Token',
    bot_active_title:     'Bot Active',
    btn_start_bot:        'Start Bot',
    loading:              'Loading...',
    err_fields_required:  'All fields are required.',
    err_api_required:     'API ID and Hash are required.',
    err_enter_code:       'Please enter the code.',
    err_enter_password:   'Please enter your password.', // pragma: allowlist secret
    err_token_required:   'Token is required',
    err_invalid_token:    'Invalid token',
    err_saving:           'Error saving',
    err_unknown:          'Unknown error',
    err_network:          'Network error: ',
    err_auto_create:      'Auto create failed. Enter token manually or skip.',
    err_bot_start:        'Error starting bot',
    err_bot_create:       'Error creating bot',
    err_loading_status:   'Error loading status',
    err_fill_credentials: 'Fill in API credentials to continue',
    ok_token_valid:       'Token valid! Bot: @{username}',
    ok_bot_created:       'Bot @{username} created! Continue.',
    ok_bot_started:       'Bot started!',
    ok_token_saved:       'Token saved! Restart kernel to apply.',
    ok_qr_regenerated:    'QR code expired, new one generated',
    ok_enter_credentials: 'Enter API credentials and click QR Code button',
    qr_scan_app:          'Scan with your Telegram app...',
    qr_new_generated:     'New QR code generated - scan again!',
    qr_checking:          'Checking...',
    btn_please_wait:      '⏳ Please wait…',
  },

  ru: {
    configured_subtitle:   'MCUB yжe нacтpoeн',
    configured_title:        'Дoбpo пoжaлoвaть в MCUB!',
    configured_hint:         'Вaш экзeмпляp yжe нacтpoeн и гoтoв к иcпoльзoвaнию.',
    subtitle_setup:       'Пepвичнaя нacтpoйкa',
    subtitle_reauth:      'Ceccия иcтeклa',
    subtitle_bot:         'Hacтpoйки бoтa',
    step_credentials:     'Дaнныe',
    step_scan:            'Cкaн',
    step_code:            'Кoд',
    step_bot:             'Бoт',
    step_done:            'Гoтoвo',
    s1_title:             'API Credentials',
    s1_hint:              'Oткpoйтe <a href="https://my.telegram.org" target="_blank">my.telegram.org</a> → API development tools → coздaйтe пpилoжeниe → вcтaвьтe знaчeния нижe.',
    label_api_id:         'API ID',
    label_api_hash:       'API Hash',
    label_phone:          'Hoмep тeлeфoнa',
    btn_send_code:        'Oтпpaвить',
    btn_qr_code:          'QR-кoд',
    s1qr_title:           'Cкaниpoвaть QR-кoд',
    s1qr_hint:            'Oтcкaниpyйтe QR-кoд в пpилoжeнии Telegram для вxoдa.',
    qr_waiting:           'Oжидaниe cкaниpoвaния...',
    btn_back:             'Haзaд',
    btn_check_again:      'Пpoвepить cнoвa',
    s2_title:             'Кoд из Telegram',
    s2_hint:              'Кoд был oтпpaвлeн в вaш Telegram. Ввeдитe eгo нижe.',
    label_code:           'Кoд',
    btn_back_arrow:       '← Haзaд',
    btn_verify:           'Дaлee →',
    s3_title:             'Двyxфaктopнaя ayтeнтификaция',
    s3_hint:              'Ha вaшeм aккayнтe включeнa 2FA. Ввeдитe oблaчный пapoль.',
    label_cloud_password: 'Oблaчный пapoль', // pragma: allowlist secret
    btn_confirm:          'Дaлee →',
    s4_title:             'Вcтpoeнный бoт (нeoбязaтeльнo)',
    s4_hint:              'Coздaйтe бoтa чepeз @BotFather для пoддepжки инлaйн-кнoпoк.<br>Или пpoпycтитe этoт шaг и coздaйтe бoтa пoзжe в нacтpoйкax.',
    label_bot_token_skip: 'Тoкeн бoтa (ocтaвьтe пycтым, чтoбы пpoпycтить)',
    btn_verify_token:     'Пpoвepить',
    btn_auto_create:      'Aвтo-coздaть бoтa',
    btn_skip:             'Пpoпycтить →',
    btn_continue:         'Пpoдoлжить →',
    s5_title:             'MCUB ycтaнoвлeн!',
    s5_hint:              'Ядpo зaпycкaeтcя - пepexoд к пaнeли yпpaвлeния…',
    kernel_waiting:       'Oжидaниe ядpa…',
    kernel_ready:         '✅ Ядpo гoтoвo! Пepeнaпpaвлeниe…',
    kernel_poll:          'Oжидaниe ядpa… ({n})',
    reset_configured:     'Ужe нacтpoeнo?',
    reset_link:           'Cбpocить и пepeнacтpoить',
    bot_settings_link:    'Hacтpoйки бoтa',
    reset_fresh:          'Cбpocить и нaчaть зaнoвo',
    modal_title:          'Выбepитe cпocoб вxoдa',
    modal_hint:           'Кaк вы xoтитe вoйти в cвoй aккayнт Telegram?',
    modal_qr:             'Вoйти пo QR',
    modal_code:           'Кoд нa тeлeфoн',
    btn_cancel:           'Oтмeнa',
    footer:               'MCUB Kernel - мacтep нacтpoйки',
    reauth_title:         'Пoвтopнaя aвтopизaция',
    reauth_hint:          'Вaшa ceccия иcтeклa. Пoжaлyйcтa, вoйдитe cнoвa для пpoдoлжeния.',
    bot_form_title:       'Тoкeн бoтa',
    bot_form_hint:        'Coздaйтe бoтa чepeз @BotFather в Telegram, зaтeм ввeдитe тoкeн нижe.',
    label_bot_token:      'Тoкeн бoтa',
    btn_save_token:       'Coxpaнить',
    bot_active_title:     'Бoт aктивeн',
    btn_start_bot:        'Зaпycтить',
    loading:              'Зaгpyзкa...',
    err_fields_required:  'Вce пoля oбязaтeльны для зaпoлнeния.',
    err_api_required:     'Heoбxoдимы API ID и Hash.',
    err_enter_code:       'Пoжaлyйcтa, ввeдитe кoд.',
    err_enter_password:   'Пoжaлyйcтa, ввeдитe пapoль.', // pragma: allowlist secret
    err_token_required:   'Тoкeн oбязaтeлeн',
    err_invalid_token:    'Heдeйcтвитeльный тoкeн',
    err_saving:           'Oшибкa coxpaнeния',
    err_unknown:          'Heизвecтнaя oшибкa',
    err_network:          'Oшибкa ceти: ',
    err_auto_create:      'Aвтocoздaниe нe yдaлocь. Ввeдитe тoкeн вpyчнyю или пpoпycтитe.',
    err_bot_start:        'Oшибкa зaпycкa бoтa',
    err_bot_create:       'Oшибкa coздaния бoтa',
    err_loading_status:   'Oшибкa зaгpyзки cтaтyca',
    err_fill_credentials: 'Зaпoлнитe API credentials для пpoдoлжeния',
    ok_token_valid:       'Тoкeн дeйcтвитeлeн! Бoт: @{username}',
    ok_bot_created:       'Бoт @{username} coздaн! Пpoдoлжaйтe.',
    ok_bot_started:       'Бoт зaпyщeн!',
    ok_token_saved:       'Тoкeн coxpaнён! Пepeзaпycтитe ядpo для пpимeнeния.',
    ok_qr_regenerated:    'QR-кoд иcтёк, cгeнepиpoвaн нoвый',
    ok_enter_credentials: 'Ввeдитe API credentials и нaжмитe кнoпкy QR-кoд',
    qr_scan_app:          'Oтcкaниpyйтe в пpилoжeнии Telegram...',
    qr_new_generated:     'Cгeнepиpoвaн нoвый QR-кoд - oтcкaниpyйтe cнoвa!',
    qr_checking:          'Пpoвepяeм...',
    btn_please_wait:      '⏳ Ждитe…',
  }
};

let lang = localStorage.getItem('mcub_lang') || 'en';

function t(key, vars = {}) {
  const str = TRANSLATIONS[lang]?.[key] ?? TRANSLATIONS.en[key] ?? key;
  return str.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
}

function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll('[data-i18n-html]').forEach(el => {
    el.innerHTML = t(el.dataset.i18nHtml);
  });
  document.documentElement.lang = lang;
}

function toggleLang() {
  lang = lang === 'en' ? 'ru' : 'en';
  localStorage.setItem('mcub_lang', lang);
  langToggleBtn.textContent = lang.toUpperCase();
  applyI18n();
}

const toggleBtn     = document.getElementById('themeToggle');
const langToggleBtn = document.getElementById('langToggle');
let dark = localStorage.getItem('mcub_theme') !== 'light';

function applyTheme() {
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  toggleBtn.textContent = dark ? '🌙' : '☀️';
  localStorage.setItem('mcub_theme', dark ? 'dark' : 'light');
}

applyTheme();
applyI18n();
langToggleBtn.textContent = lang.toUpperCase();

toggleBtn.onclick    = () => { dark = !dark; applyTheme(); };
langToggleBtn.onclick = toggleLang;

function dismiss(el) {
  el.style.animation = 'slideOut .25s ease forwards';
  setTimeout(() => el.remove(), 250);
}

function shakeInput(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('shake');
  void el.offsetWidth;
  el.classList.add('shake');
  el.addEventListener('animationend', () => el.classList.remove('shake'), {once:true});
}

function toast(msg, type = 'err') {
  if (type === 'err') {
    const active = document.activeElement;
    if (active && active.tagName === 'INPUT') {
      active.classList.remove('shake');
      void active.offsetWidth;
      active.classList.add('shake');
      active.addEventListener('animationend', () => active.classList.remove('shake'), {once:true});
    }
  }
  const MAX_TOASTS = 5;
  const wrap = document.getElementById('toasts');
  const el   = document.createElement('div');
  el.className = 'toast' + (type === 'ok' ? ' ok' : '');
  el.innerHTML = `<span class="toast-icon">${type === 'ok' ? '✓' : '⚠'}</span><span>${msg}</span><span class="toast-close">✕</span>`;
  wrap.prepend(el);
  while (wrap.children.length > MAX_TOASTS) wrap.lastElementChild.remove();
  setTimeout(() => { if (el.isConnected) dismiss(el); }, 6000);
}

let _currentStep = 1;

const STEP_MAP = { '1':1, '1qr':2, '2':3, '3':4, '4':5, '5':6 };

function show(n) {
  const idx = STEP_MAP[String(n)];
  if (idx === undefined) return;

  const goingBack = idx < _currentStep;
  _currentStep = idx;

  document.querySelectorAll('.wstep').forEach((el, i) => {
    const visible = i + 1 === idx;
    el.classList.toggle('hidden', !visible);
    if (visible) {
      el.classList.remove('slide-back');
      void el.offsetWidth;
      if (goingBack) el.classList.add('slide-back');
    }
  });

  document.querySelectorAll('.step').forEach((el, i) => {
    el.classList.toggle('active', i + 1 === idx);
    el.classList.toggle('done',   i + 1 < idx);
  });

  document.querySelectorAll('.sconn').forEach((el, i) => {
    el.classList.toggle('filled', i < idx - 1);
  });

  const inp = document.querySelector(`#s${n} input`);
  if (inp) setTimeout(() => inp.focus(), 80);
}

function btnLoading(id, on) {
  const b = document.getElementById(id);
  if (!b) return;
  if (on) {
    b._label    = b.textContent;
    b._disabled = b.disabled;
    b.textContent = t('btn_please_wait');
    b.disabled    = true;
  } else {
    b.textContent = b._label ?? b.textContent;
    b.disabled    = b._disabled ?? false;
  }
}

async function post(url, body) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  let data = {};
  try { data = await r.json(); } catch (_) { }
  return { ok: r.ok, status: r.status, ...data };
}

function renderQR(url) {
  const container = document.getElementById('qr-image');
  container.innerHTML = '';
  new QRCode(container, {
    text: url,
    width: 220, height: 220,
    colorDark: '#000', colorLight: '#fff',
    correctLevel: QRCode.CorrectLevel.M
  });
}

function setQRStatus(key, raw) {
  document.getElementById('qr-status').textContent = raw ?? t(key);
}

async function step1() {
  const api_id   = document.getElementById('f_api_id').value.trim();
  const api_hash = document.getElementById('f_api_hash').value.trim();
  const phone    = document.getElementById('f_phone').value.trim();
  if (!api_id || !api_hash || !phone) { toast(t('err_fields_required')); return; }
  btnLoading('btn1', true);
  try {
    const r = await post('/api/setup/send_code', { api_id, api_hash, phone });
    if (!r.ok) { toast(r.error || t('err_unknown')); return; }
    show(2);
  } catch(e) { toast(t('err_network') + e.message); }
  finally    { btnLoading('btn1', false); }
}

async function step2() {
  const code = document.getElementById('f_code').value.trim();
  if (!code) { toast(t('err_enter_code')); return; }
  btnLoading('btn2', true);
  try {
    const r = await post('/api/setup/verify_code', { code });
    if (r.requires_2fa) { show(3); return; }
    if (!r.ok) { toast(r.error || t('err_unknown')); return; }
    show(4);
  } catch(e) { toast(t('err_network') + e.message); }
  finally    { btnLoading('btn2', false); }
}

async function step3() {
  const password = document.getElementById('f_pass').value;
  if (!password) { toast(t('err_enter_password')); return; }
  btnLoading('btn3', true);
  try {
    const r = await post('/api/setup/verify_code', { password });
    if (!r.ok) { toast(r.error || t('err_unknown')); return; }
    show(4);
  } catch(e) { toast(t('err_network') + e.message); }
  finally    { btnLoading('btn3', false); }
}

async function step1QR() {
  const api_id   = document.getElementById('f_api_id').value.trim();
  const api_hash = document.getElementById('f_api_hash').value.trim();
  if (!api_id || !api_hash) { toast(t('err_api_required')); return; }

  const btn = document.getElementById('btn1_qr');
  btn._label = btn.textContent;
  btn.textContent = t('btn_please_wait');
  btn.disabled = true;
  const resetBtn = () => { btn.textContent = btn._label; btn.disabled = false; };

  try {
    const r = await post('/api/setup/qr_login', { api_id, api_hash });
    if (!r.ok) { toast(r.error || t('err_unknown')); resetBtn(); return; }
    renderQR(r.qr_url);
    setQRStatus('qr_scan_app');
    show('1qr');
    pollQRLoop();
    resetBtn();
  } catch(e) { toast(t('err_network') + e.message); resetBtn(); }
}

let qrPollInterval = null;

function pollQRLoop() {
  if (qrPollInterval) clearInterval(qrPollInterval);
  qrPollInterval = setInterval(async () => {
    try {
      const r = await post('/api/setup/qr_poll', {});
      if (r.requires_2fa) {
        clearInterval(qrPollInterval);
        show(3);
        return;
      }
      if (r.qr_expired && r.qr_url) {
        renderQR(r.qr_url);
        setQRStatus('qr_new_generated');
        toast(t('ok_qr_regenerated'), 'ok');
        animateQR();
        return;
      }
      if (r.ok && !r.waiting) {
        clearInterval(qrPollInterval);
        show(4);
        return;
      }
      if (r.error) {
        clearInterval(qrPollInterval);
        toast(r.error);
        show(1);
      }
    } catch(_) {}
  }, 3000);
}

async function pollQR() {
  setQRStatus('qr_checking');
  try {
    const r = await post('/api/setup/qr_poll', {});
    if (r.requires_2fa) {
      clearInterval(qrPollInterval);
      show(3);
      return;
    }
    if (r.qr_expired && r.qr_url) {
      renderQR(r.qr_url);
      setQRStatus('qr_new_generated');
      toast(t('ok_qr_regenerated'), 'ok');
      animateQR();
      return;
    }
    if (r.ok && !r.waiting) {
      clearInterval(qrPollInterval);
      show(4);
      return;
    }
    setQRStatus('qr_waiting');
  } catch(e) {
    document.getElementById('qr-status').textContent = t('err_network') + e.message;
  }
}

function pollKernel() {
  const st = document.getElementById('poll-status');
  let n = 0;
  const interval = setInterval(async () => {
    n++;
    try {
      const r = await fetch('/status');
      if (r.ok) {
        clearInterval(interval);
        st.textContent = t('kernel_ready');
        setTimeout(() => location.href = '/', 1200);
        return;
      }
    } catch(_) {}
    st.textContent = t('kernel_poll', { n });
  }, 2000);
}

function showResetChoice() {
  document.getElementById('resetModal').classList.remove('hidden');
}

async function resetAndChoose(method) {
  document.getElementById('resetModal').classList.add('hidden');
  try { await fetch('/setup/reset', { method: 'GET' }); } catch(_) {}

  if (method === 'qr') {
    show(1);
    toast(t('ok_enter_credentials'), 'ok');
  } else {
    location.reload();
  }
}

async function verifyBotInSetup() {
  const token = document.getElementById('f_bot_token').value.trim();
  if (!token) {
    document.getElementById('btn4').disabled = false;
    return;
  }
  btnLoading('btn4verify', true);
  try {
    const r = await post('/api/bot/verify_token', { token });
    if (!r.ok || !r.valid) { toast(r.error || t('err_invalid_token')); return; }
    toast(t('ok_token_valid', { username: r.username }), 'ok');
    document.getElementById('btn4').disabled = false;
  } catch(e) { toast(t('err_network') + e.message); }
  finally    { btnLoading('btn4verify', false); }
}

async function autoCreateBot() {
  btnLoading('btn4auto', true);
  try {
    const r = await post('/api/bot/auto_create', {});
    if (!r.ok) {
      toast(r.manual ? t('err_auto_create') : (r.error || t('err_bot_create')));
      return;
    }
    document.getElementById('f_bot_token').value = r.token;
    toast(t('ok_bot_created', { username: r.username }), 'ok');
    document.getElementById('btn4').disabled = false;
  } catch(e) { toast(t('err_network') + e.message); }
  finally    { btnLoading('btn4auto', false); }
}

async function skipBot() {
  await post('/api/setup/complete', {});
  show(5);
  pollKernel();
}

async function finishWithBot() {
  const token = document.getElementById('f_bot_token').value.trim();
  btnLoading('btn4', true);
  try {
    if (token) {
      const r = await post('/api/bot/save_token', { token });
      if (!r.ok) { toast(r.error || t('err_saving')); return; }
    }
    await post('/api/setup/complete', {});
    show(5);
    pollKernel();
  } catch(e) { toast(t('err_network') + e.message); }
  finally    { btnLoading('btn4', false); }
}

async function loadBotStatus() {
  try {
    const r    = await fetch('/api/bot/status');
    const data = await r.json();

    document.getElementById('botStatus').classList.add('hidden');

    if (data.running) {
      document.getElementById('botActions').classList.remove('hidden');
      document.getElementById('botUsernameDisplay').textContent = 'Running as @' + data.username;
      document.getElementById('btnBotStart').textContent = 'Running ✓';
      document.getElementById('btnBotStart').disabled = true;
    } else if (data.has_token) {
      document.getElementById('botActions').classList.remove('hidden');
      document.getElementById('botUsernameDisplay').textContent = t('ok_token_saved').split('!')[0] + '!';
      document.getElementById('btnBotStart').disabled = false;
    } else {
      document.getElementById('botForm').classList.remove('hidden');
    }
  } catch(_) {
    document.getElementById('botStatus').innerHTML = `<p class="hint">${t('err_loading_status')}</p>`;
  }
}

async function verifyBotToken() {
  const token = document.getElementById('f_bot_token_page').value.trim();
  if (!token) { toast(t('err_token_required')); return; }

  btnLoading('btnBotVerify', true);
  try {
    const r = await post('/api/bot/verify_token', { token });
    if (!r.ok)   { toast(r.error || t('err_invalid_token')); return; }
    if (r.valid) {
      toast(t('ok_token_valid', { username: r.username }), 'ok');
      document.getElementById('btnBotSave').disabled = false;
    }
  } catch(e) { toast(t('err_network') + e.message); }
  finally    { btnLoading('btnBotVerify', false); }
}

async function saveBotToken() {
  const token = document.getElementById('f_bot_token_page').value.trim();
  btnLoading('btnBotSave', true);
  try {
    const r = await post('/api/bot/save_token', { token });
    if (!r.ok) { toast(r.error || t('err_saving')); return; }
    toast(t('ok_token_saved'), 'ok');
    setTimeout(() => location.reload(), 1500);
  } catch(e) { toast(t('err_network') + e.message); }
  finally    { btnLoading('btnBotSave', false); }
}

async function startBot() {
  btnLoading('btnBotStart', true);
  try {
    const r = await post('/api/bot/start', {});
    if (!r.ok) { toast(r.error || t('err_bot_start')); return; }
    toast(t('ok_bot_started'), 'ok');
    setTimeout(() => location.reload(), 1500);
  } catch(e) { toast(t('err_network') + e.message); }
  finally    { btnLoading('btnBotStart', false); }
}

async function showReauthQR() {
  document.getElementById('reauthPage').classList.add('hidden');
  document.getElementById('setupPage').classList.remove('hidden');
  const d = await _prefillFromConfig();
  if (d.ok && d.api_id && d.api_hash) {
    await step1QR();
  } else {
    show(1);
    toast(t('err_fill_credentials'), 'err');
  }
}

async function showReauthCode() {
  document.getElementById('reauthPage').classList.add('hidden');
  document.getElementById('setupPage').classList.remove('hidden');
  const d = await _prefillFromConfig();
  if (d.ok && d.api_id && d.api_hash && d.phone) {
    await step1();
  } else {
    show(1);
    toast(t('err_fill_credentials'), 'err');
  }
}

async function _prefillFromConfig() {
  try {
    const r = await fetch('/api/setup/prefill');
    const d = await r.json();
    if (d.ok) {
      document.getElementById('f_api_id').value   = d.api_id   || '';
      document.getElementById('f_api_hash').value = d.api_hash || '';
      document.getElementById('f_phone').value    = d.phone    || '';
    }
    return d;
  } catch(_) { return {}; }
}

if (location.pathname === '/bot') {
  document.getElementById('setupPage').classList.add('hidden');
  document.getElementById('botPage').classList.remove('hidden');
  loadBotStatus();
}

{% if show_reauth %}
document.getElementById('setupPage').classList.add('hidden');
document.getElementById('reauthPage').classList.remove('hidden');
{% else %}
(async function checkReauth() {
  try {
    const r     = await fetch('/api/setup/state');
    const state = await r.json();
    if (state.needs_reauth) {
      document.getElementById('setupPage').classList.add('hidden');
      document.getElementById('reauthPage').classList.remove('hidden');
    }
  } catch(_) {}
})();
{% endif %}

function animateQR() {
  const el = document.getElementById('qr-image');
  el.classList.remove('refreshed');
  void el.offsetWidth;
  el.classList.add('refreshed');
}

document.getElementById('f_phone').addEventListener('keydown',    e => e.key === 'Enter' && step1());
document.getElementById('f_code').addEventListener('keydown',     e => e.key === 'Enter' && step2());
document.getElementById('f_pass').addEventListener('keydown',     e => e.key === 'Enter' && step3());
document.getElementById('f_api_hash').addEventListener('keydown', e => e.key === 'Enter' && document.getElementById('f_phone').focus());

document.getElementById('toasts').addEventListener('click', e => {
  const closeBtn = e.target.closest('.toast-close');
  if (closeBtn) {
    const toastEl = closeBtn.closest('.toast');
    if (toastEl) dismiss(toastEl);
  }
});

document.addEventListener('click', e => {
  const btn = e.target.closest('.btn-primary, .btn-ghost');
  if (!btn) return;
  const r    = document.createElement('span');
  r.className = 'ripple';
  const rect = btn.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height);
  r.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - rect.left - size / 2}px;top:${e.clientY - rect.top - size / 2}px`;
  btn.appendChild(r);
  r.addEventListener('animationend', () => r.remove());
});

function rand(a, b) { return Math.random() * (b - a) + a; }

document.querySelectorAll('.wish').forEach(el => {
  function shoot() {
    el.style.top    = rand(10, 80) + 'px';
    el.style.left   = rand(10, 100) + '%';
    el.style.width  = rand(40, 200) + 'px';
    el.style.opacity = 0;
    el.style.animation = 'none';
    el.offsetWidth;
    el.style.animation = `shoot ${rand(1, 3)}s ease-in-out forwards`;
    el.addEventListener('animationend', () => setTimeout(shoot, rand(500, 5000)), { once: true });
  }
  setTimeout(shoot, rand(0, 5000));
});
