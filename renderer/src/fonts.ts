// src/fonts.ts
// Loads a handful of bold, readable Google Fonts good for caption text.
// loadFont() fetches and registers the font so it's usable in CSS —
// each one returns an object with a `fontFamily` string to reference.

import { loadFont as loadMontserrat } from '@remotion/google-fonts/Montserrat';
import { loadFont as loadPoppins } from '@remotion/google-fonts/Poppins';
import { loadFont as loadInter } from '@remotion/google-fonts/Inter';
import { loadFont as loadBebasNeue } from '@remotion/google-fonts/BebasNeue';

const montserrat = loadMontserrat();
const poppins = loadPoppins();
const inter = loadInter();
const bebasNeue = loadBebasNeue();

// A lookup table: the name we'll use in our style config -> the actual
// CSS font-family string Remotion generated for it.
export const FONT_FAMILIES: Record<string, string> = {
  Montserrat: montserrat.fontFamily,
  Poppins: poppins.fontFamily,
  Inter: inter.fontFamily,
  'Bebas Neue': bebasNeue.fontFamily,
};
