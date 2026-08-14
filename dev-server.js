/**
 * dev-server.js
 * Local development server for Inkling.
 *
 * - Serves frontend/ as static files on http://localhost:3000
 * - Provides POST /generate with mood-aware mock poems & stories
 *   so you can test the full UI without any AWS setup.
 *
 * Usage:
 *   npm install
 *   npm start
 *   → open http://localhost:3000
 *
 * When ready to use real AWS:
 *   In frontend/app.js, change API_URL to your Lambda function URL.
 */

'use strict';

const express = require('express');
const path    = require('path');

const app  = express();
const PORT = process.env.PORT || 3000;

// ── Middleware ────────────────────────────────────────────────
app.use(express.json());

// CORS — allow all origins for local dev
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin',  '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

// Serve the frontend directory as static files
app.use(express.static(path.join(__dirname, 'frontend')));

// ── Mock poem/story data ──────────────────────────────────────
const MOCK_POEMS = {
  whimsical: {
    poem: {
      title: 'The Umbrella That Learned to Dance',
      text:  `Under a sky of lavender rain,
your umbrella learned to twirl again —
not to keep the droplets out,
but to spin with them, without a doubt.

Each puddle became a mirror bright,
reflecting back a softer light,
and you, dear soul, mid-storm, mid-song,
discovered dancing was there all along.`,
    },
    story: {
      title: 'The Teacup That Travelled the World',
      text:  `Once upon a Tuesday, a small porcelain teacup decided it had seen quite enough of its shelf. It slipped quietly off the edge — not falling, exactly, but drifting — and landed softly on the kitchen floor with a sound like a whispered secret.\n\nBy morning it had crossed three gardens, hitched a ride on a passing cloud, and arrived, steaming gently, on a doorstep where someone desperately needed a cup of chamomile.\n\nIt never did go back to the shelf. Some things are meant to wander.`,
    },
  },
  adventurous: {
    poem: {
      title: 'The Map That Had One More Edge',
      text:  `Beyond the last marked ridge
where cartographers gave up and drew a bridge
to nowhere — that is exactly where
the real adventure fills the air.

Your boots know the untranslated ground,
your compass points to the unbound,
and every summit just reveals
ten more horizons, ten new deals.`,
    },
    story: {
      title: 'Three Hours Past the Last Trail Marker',
      text:  `The trail marker had rusted to illegibility. Perfect, thought the explorer, pulling out a fresh notebook.\n\nThree hours past the last reliable map, the valley opened into something no satellite had quite caught — a meadow the colour of new copper, ringed by trees that hummed in a frequency just below hearing.\n\nShe made camp there. The stars, that far from any road, were almost embarrassingly bright. She wrote four pages before sleep caught her, and woke up with six more ideas.`,
    },
  },
  cozy: {
    poem: {
      title: 'Rain on a Saturday Bookshop Window',
      text:  `The radiator ticks its quiet count.
Outside, rain rehearses on the glass —
a soft percussion no one asked for
but everyone is glad of.

Your mug warms both hands at once.
The page turns of its own accord.
Somewhere, a cat is making itself
unambiguously at home.

This is the whole thing, you think.
This is the whole thing.`,
    },
    story: {
      title: 'The Afternoon That Refused to End',
      text:  `It was the kind of afternoon that seems to stretch on purpose — four o'clock lingering pleasantly past its welcome, golden light pooling on the floorboards.\n\nThe soup was on. The book was good. The cat had decided that your lap was, definitively, the best place in the world to be.\n\nNobody called. No notifications arrived that mattered. The afternoon gave a small, contented sigh, and stayed a little longer.`,
    },
  },
  mysterious: {
    poem: {
      title: 'The Door That Was Not There at Noon',
      text:  `By moonrise it appeared between
two houses that had stood for years —
a door of weathered driftwood blue,
no handle, just a ring of dew.

Those who knocked heard only their own heartbeat.
Those who listened heard the street
rearrange itself behind them.
Only the curious find the hymn within.`,
    },
    story: {
      title: 'The Library at the End of the Lane',
      text:  `No one remembered when the library appeared at the end of Hartfield Lane. The local council's records showed only a blank for that address, and the librarian — a woman with silver-ink fingers and a smile that arrived slightly before she did — could not recall opening day.\n\nThe books rearranged themselves overnight. Every patron found exactly what they needed, never quite what they expected. The return slot accepted items that had not come from the library at all.\n\nThe sign on the door read: *Hours: Whenever you need us.*`,
    },
  },
  funny: {
    poem: {
      title: 'Ode to the Meeting That Could Have Been an Email',
      text:  `O mighty gathering of seventeen,
convened to discuss the font size on a form —
your agenda PDF, fourteen pages long,
warned of nothing, foresaw no storm.

We sat. We nodded. Someone shared a screen.
The slide said "synergy." No one asked what it meant.
An hour dissolved into the conference room air.
The email was sent. It had always been there.`,
    },
    story: {
      title: 'The Day the Office Plant Filed a Complaint',
      text:  `HR received the complaint on a Wednesday. It was filed, rather neatly, by the large pothos in the corner of the open-plan office.\n\nThe complaint cited: insufficient watering, three years of overhearing competitive small talk about commutes, and — this was the part that required a second read — "a persistent belief among staff that I cannot hear them."\n\nHR convened a meeting. Nobody brought up the pothos's attendance record. The plant, for its part, seemed satisfied. Its leaves perked up noticeably by Thursday.`,
    },
  },
  romantic: {
    poem: {
      title: 'The Coffee You Made Before I Was Awake',
      text:  `You learned, somewhere between winter and spring,
exactly how I take it —
not written down, just held
in the quiet way you hold things.

By the time I reach the kitchen
the mug is warm, the spoon still resting,
and the whole ordinary morning
has become a love letter.`,
    },
    story: {
      title: 'First Lesson in Stargazing',
      text:  `She had no idea how to find a constellation. He had been looking for an excuse to show her.\n\nThey lay on the hill with a star map downloaded and immediately abandoned, because it turned out that describing the shape of Orion with your hands in the dark was funnier and warmer than getting it right.\n\nShe never did learn the constellations. She did learn that the best way to see the stars is with someone who points at the wrong ones enthusiastically.`,
    },
  },
  bittersweet: {
    poem: {
      title: 'What Stays After the Last Train Home',
      text:  `The platform empties, and the sound
of your departure hangs around —
not grief exactly, more the weight
of something good that couldn't wait.

The bench still holds the shape of us.
The coffee cups are on the bus.
And in the ordinary air,
a kind of sweetness, still, still there.`,
    },
    story: {
      title: 'The House at the End of the Summer',
      text:  `They had spent every July in that house for eleven years. The last morning, they moved through the rooms without speaking, each one doing the small ritual of goodbye — straightening a picture that had always hung slightly crooked, running a hand along the kitchen windowsill, looking out at the garden one extra time.\n\nThe keys were left on the counter. The door closed. Outside, it was the kind of morning the summer saves for endings: bright, and a little too quiet, and absolutely beautiful.`,
    },
  },
};

// ── Simulate realistic latency ────────────────────────────────
function mockDelay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ── POST /generate ────────────────────────────────────────────
app.post('/generate', async (req, res) => {
  const {
    name   = 'a curious traveler',
    theme  = 'a rainy afternoon',
    mood   = 'whimsical',
    format = 'poem',
    length = 'short',
  } = req.body || {};

  console.log(`[generate] mood=${mood} format=${format} length=${length} name="${name}" theme="${theme}"`);

  // Simulate ~1.5 – 2.5 s generation time (like real Bedrock)
  const delay = 1500 + Math.random() * 1000;
  await mockDelay(delay);

  // Pick mock content
  const moodData   = MOCK_POEMS[mood]   || MOCK_POEMS.whimsical;
  const formatData = moodData[format]   || moodData.poem;

  // Personalise slightly with the user's name/theme
  const nameHint  = name  !== 'a curious traveler' ? ` (for ${name})` : '';
  const themeHint = theme !== 'a rainy afternoon'   ? ` — ${theme}`   : '';

  const response = {
    id:        `mock-${Date.now()}`,
    title:     formatData.title + (nameHint  ? nameHint  : ''),
    text:      formatData.text  + (themeHint ? `\n\n[theme: ${theme}]` : ''),
    format,
    createdAt: Math.floor(Date.now() / 1000),
    _mock:     true,   // useful flag so you can tell this is mock data
  };

  res.json(response);
});

// ── Fallback: serve index.html for any unmatched route ────────
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'frontend', 'index.html'));
});

// ── Start ─────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log('');
  console.log('  ✦  Inkling dev server running');
  console.log(`  →  http://localhost:${PORT}`);
  console.log('');
  console.log('  This is a MOCK server — no AWS calls are made.');
  console.log('  To use real Bedrock, update API_URL in frontend/app.js');
  console.log('  to your Lambda function URL.');
  console.log('');
});
