/* ============================================================
   INKLING — app.js
   Cozy Literary Workspace
   ============================================================ */

'use strict';

// ── Configuration ──────────────────────────────────────────
const API_URL = 'https://d5e2oo5egnkilx3dkq2qvvxa5a0kdppl.lambda-url.ap-south-1.on.aws/';


// ── DOM References ──────────────────────────────────────────
const form         = document.getElementById('generator-form');
const generateBtn  = document.getElementById('generate-btn');
const btnText      = generateBtn.querySelector('.btn-text');
const newBtn       = document.getElementById('new-creation-btn');

const nameInput    = document.getElementById('input-name');
const themeInput   = document.getElementById('input-theme');
const moodSelect   = document.getElementById('input-mood');
const toneSelect   = document.getElementById('input-tone');
const styleSelect  = document.getElementById('input-style');
const perspSelect  = document.getElementById('input-perspective');

// View States
const viewEmpty    = document.getElementById('view-empty');
const viewLoading  = document.getElementById('view-loading');
const viewError    = document.getElementById('view-error');
const viewResult   = document.getElementById('view-result');
const loadingText  = document.getElementById('loading-text');

// Result Elements
const resultTitle  = document.getElementById('result-title');
const resultText   = document.getElementById('result-text');
const resultMeta   = document.getElementById('result-metadata');

// Error Elements
const errorMessage = document.getElementById('error-message');
const errorHint    = document.getElementById('error-hint');
const retryBtn     = document.getElementById('retry-btn');

// Action Elements
const copyBtn       = document.getElementById('copy-btn');
const copyLabel     = copyBtn.querySelector('.action-label');
const regenerateBtn = document.getElementById('regenerate-btn');
const speakBtn      = document.getElementById('speak-btn');
const speakLabel    = speakBtn.querySelector('.action-label');

// ── App State ──────────────────────────────────────────────
let state = {
  format: 'poem',
  length: 'short',
  loading: false,
  lastResult: null,
  utterance: null,
  speaking: false,
};

// ── View Management ─────────────────────────────────────────
function showView(viewId) {
  [viewEmpty, viewLoading, viewError, viewResult].forEach(v => {
    v.classList.remove('active');
  });
  document.getElementById(viewId).classList.add('active');
  
  // Reset scroll on right pane
  document.querySelector('.pane-right').scrollTop = 0;
}

// ── Format & Length Toggles ────────────────────────────────
function setupToggleGroup(selector, stateKey) {
  const btns = document.querySelectorAll(selector);
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('active');
      btn.setAttribute('aria-pressed', 'true');
      state[stateKey] = btn.dataset.value;
    });
  });
}
setupToggleGroup('#toggle-poem, #toggle-story', 'format');
setupToggleGroup('#toggle-short, #toggle-long', 'length');

// ── Form Submit ────────────────────────────────────────────
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (state.loading) return;
  await generate();
});

regenerateBtn.addEventListener('click', async () => {
  if (state.loading) return;
  await generate();
});

retryBtn.addEventListener('click', async () => {
  await generate();
});

newBtn.addEventListener('click', () => {
  if (state.loading) return;
  form.reset();
  // reset toggles if needed, but keeping them as is works fine too
  state.lastResult = null;
  showView('view-empty');
  stopSpeaking();
});

// ── Core: Generate ─────────────────────────────────────────
async function generate() {
  const payload = {
    name:        nameInput.value.trim() || undefined,
    theme:       themeInput.value.trim() || undefined,
    mood:        moodSelect.value,
    format:      state.format,
    length:      state.length,
    tone:        toneSelect.value,
    style:       styleSelect.value,
    perspective: perspSelect.value
  };

  setLoading(true);
  stopSpeaking();

  try {
    const res = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok || data.error) {
      throw new Error(data.error || `Server error ${res.status}`);
    }

    state.lastResult = data;
    setLoading(false);
    await renderResult(data);

  } catch (err) {
    console.error('Generation failed:', err);
    setLoading(false);
    errorMessage.textContent = err.message || 'Inkling got a little tongue-tied.';
    showView('view-error');
  }
}

// ── Loading State ──────────────────────────────────────────
function setLoading(on) {
  state.loading = on;
  if (on) {
    generateBtn.disabled = true;
    regenerateBtn.disabled = true;
    btnText.textContent = 'Creating...';
    
    const messages = [
      'Dipping the quill...',
      'Finding the right words...',
      'Weaving your story...',
      'Summoning inspiration...'
    ];
    loadingText.textContent = messages[Math.floor(Math.random() * messages.length)];
    showView('view-loading');
  } else {
    generateBtn.disabled = false;
    regenerateBtn.disabled = false;
    btnText.textContent = 'Create';
  }
}

// ── Show Result with Typewriter ────────────────────────────
async function renderResult(data) {
  showView('view-result');
  
  // Capitalize helpers
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  const actualFormat = data.format || state.format;
  resultMeta.textContent = `${cap(moodSelect.value)} · ${cap(actualFormat)} · ${cap(state.length)}`;
  
  resultTitle.textContent = data.title || 'Untitled';
  
  let finalPiece = data.text || '';
  if (actualFormat === 'story') {
    if (state.length === 'short') {
      finalPiece += '\n\nPerfect 2 minute story';
    } else {
      finalPiece += '\n\nPerfect ideation for the Special ones';
    }
  }
  
  await typewriterReveal(resultText, finalPiece);
}

// ── Typewriter Effect ──────────────────────────────────────
function typewriterReveal(element, text) {
  return new Promise(resolve => {
    element.textContent = '';
    element.classList.add('typing');

    const chars = text.split('');
    let i = 0;
    const baseDelay = Math.max(12, Math.min(30, 2400 / chars.length));

    function type() {
      if (i < chars.length) {
        element.textContent += chars[i];
        i++;
        const ch = chars[i - 1];
        const pause = /[.!?\n]/.test(ch) ? baseDelay * 6 : baseDelay;
        setTimeout(type, pause);
      } else {
        element.classList.remove('typing');
        resolve();
      }
    }
    type();
  });
}

// ── Copy Button ────────────────────────────────────────────
copyBtn.addEventListener('click', async () => {
  if (!state.lastResult) return;
  const textToCopy = `${state.lastResult.title}\n\n${state.lastResult.text}`;

  try {
    await navigator.clipboard.writeText(textToCopy);
    copyLabel.textContent = 'Copied';
    copyBtn.classList.add('active');
    setTimeout(() => {
      copyLabel.textContent = 'Copy';
      copyBtn.classList.remove('active');
    }, 2000);
  } catch (e) {
    const ta = document.createElement('textarea');
    ta.value = textToCopy;
    ta.style.position = 'fixed';
    ta.style.opacity  = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    
    copyLabel.textContent = 'Copied';
    copyBtn.classList.add('active');
    setTimeout(() => {
      copyLabel.textContent = 'Copy';
      copyBtn.classList.remove('active');
    }, 2000);
  }
});

// ── Read Aloud (browser speech synthesis) ─────────────────
speakBtn.addEventListener('click', () => {
  if (!state.lastResult) return;

  if (state.speaking) {
    stopSpeaking();
    return;
  }

  const text = `${state.lastResult.title}. ${state.lastResult.text}`;
  state.utterance = new SpeechSynthesisUtterance(text);
  state.utterance.rate  = 0.88;
  state.utterance.pitch = 1.05;

  state.utterance.onstart = () => {
    state.speaking = true;
    speakLabel.textContent = 'Stop';
    speakBtn.classList.add('active');
  };
  state.utterance.onend = () => {
    state.speaking = false;
    speakLabel.textContent = 'Listen';
    speakBtn.classList.remove('active');
  };
  state.utterance.onerror = () => {
    state.speaking = false;
    speakLabel.textContent = 'Listen';
    speakBtn.classList.remove('active');
  };

  window.speechSynthesis.speak(state.utterance);
});

function stopSpeaking() {
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
  state.speaking = false;
  speakLabel.textContent = 'Listen';
  speakBtn.classList.remove('active');
}

// ── Keyboard shortcut: Ctrl/Cmd+Enter to generate ─────────
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    e.preventDefault();
    if (!state.loading) generate();
  }
});
