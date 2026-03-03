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
    s5_hint:              'Kernel is starting — redirecting to dashboard…',
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
    footer:               'MCUB Kernel – setup wizard',
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
    qr_new_generated:     'New QR code generated — scan again!',
    qr_checking:          'Checking...',
    btn_please_wait:      '⏳ Please wait…',
  },

  ru: {
    configured_subtitle:   'MCUB уже настроен',
    configured_title:        'Добро пожаловать в MCUB!',
    configured_hint:         'Ваш экземпляр уже настроен и готов к использованию.',
    subtitle_setup:       'Первичная настройка',
    subtitle_reauth:      'Сессия истекла',
    subtitle_bot:         'Настройки бота',
    step_credentials:     'Данные',
    step_scan:            'Скан',
    step_code:            'Код',
    step_bot:             'Бот',
    step_done:            'Готово',
    s1_title:             'API Credentials',
    s1_hint:              'Откройте <a href="https://my.telegram.org" target="_blank">my.telegram.org</a> → API development tools → создайте приложение → вставьте значения ниже.',
    label_api_id:         'API ID',
    label_api_hash:       'API Hash',
    label_phone:          'Номер телефона',
    btn_send_code:        'Отправить',
    btn_qr_code:          'QR-код',
    s1qr_title:           'Сканировать QR-код',
    s1qr_hint:            'Отсканируйте QR-код в приложении Telegram для входа.',
    qr_waiting:           'Ожидание сканирования...',
    btn_back:             'Назад',
    btn_check_again:      'Проверить снова',
    s2_title:             'Код из Telegram',
    s2_hint:              'Код был отправлен в ваш Telegram. Введите его ниже.',
    label_code:           'Код',
    btn_back_arrow:       '← Назад',
    btn_verify:           'Далее →',
    s3_title:             'Двухфакторная аутентификация',
    s3_hint:              'На вашем аккаунте включена 2FA. Введите облачный пароль.',
    label_cloud_password: 'Облачный пароль',
    btn_confirm:          'Далее →',
    s4_title:             'Встроенный бот (необязательно)',
    s4_hint:              'Создайте бота через @BotFather для поддержки инлайн-кнопок.<br>Или пропустите этот шаг и создайте бота позже в настройках.',
    label_bot_token_skip: 'Токен бота (оставьте пустым, чтобы пропустить)',
    btn_verify_token:     'Проверить',
    btn_auto_create:      'Авто-создать бота',
    btn_skip:             'Пропустить →',
    btn_continue:         'Продолжить →',
    s5_title:             'MCUB установлен!',
    s5_hint:              'Ядро запускается — переход к панели управления…',
    kernel_waiting:       'Ожидание ядра…',
    kernel_ready:         '✅ Ядро готово! Перенаправление…',
    kernel_poll:          'Ожидание ядра… ({n})',
    reset_configured:     'Уже настроено?',
    reset_link:           'Сбросить и перенастроить',
    bot_settings_link:    'Настройки бота',
    reset_fresh:          'Сбросить и начать заново',
    modal_title:          'Выберите способ входа',
    modal_hint:           'Как вы хотите войти в свой аккаунт Telegram?',
    modal_qr:             'Войти по QR',
    modal_code:           'Код на телефон',
    btn_cancel:           'Отмена',
    footer:               'MCUB Kernel – мастер настройки',
    reauth_title:         'Повторная авторизация',
    reauth_hint:          'Ваша сессия истекла. Пожалуйста, войдите снова для продолжения.',
    bot_form_title:       'Токен бота',
    bot_form_hint:        'Создайте бота через @BotFather в Telegram, затем введите токен ниже.',
    label_bot_token:      'Токен бота',
    btn_save_token:       'Сохранить',
    bot_active_title:     'Бот активен',
    btn_start_bot:        'Запустить',
    loading:              'Загрузка...',
    err_fields_required:  'Все поля обязательны для заполнения.',
    err_api_required:     'Необходимы API ID и Hash.',
    err_enter_code:       'Пожалуйста, введите код.',
    err_enter_password:   'Пожалуйста, введите пароль.',
    err_token_required:   'Токен обязателен',
    err_invalid_token:    'Недействительный токен',
    err_saving:           'Ошибка сохранения',
    err_unknown:          'Неизвестная ошибка',
    err_network:          'Ошибка сети: ',
    err_auto_create:      'Автосоздание не удалось. Введите токен вручную или пропустите.',
    err_bot_start:        'Ошибка запуска бота',
    err_bot_create:       'Ошибка создания бота',
    err_loading_status:   'Ошибка загрузки статуса',
    err_fill_credentials: 'Заполните API credentials для продолжения',
    ok_token_valid:       'Токен действителен! Бот: @{username}',
    ok_bot_created:       'Бот @{username} создан! Продолжайте.',
    ok_bot_started:       'Бот запущен!',
    ok_token_saved:       'Токен сохранён! Перезапустите ядро для применения.',
    ok_qr_regenerated:    'QR-код истёк, сгенерирован новый',
    ok_enter_credentials: 'Введите API credentials и нажмите кнопку QR-код',
    qr_scan_app:          'Отсканируйте в приложении Telegram...',
    qr_new_generated:     'Сгенерирован новый QR-код — отсканируйте снова!',
    qr_checking:          'Проверяем...',
    btn_please_wait:      '⏳ Ждите…',
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
