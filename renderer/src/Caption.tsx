// src/Caption.tsx
import { useCurrentFrame, useVideoConfig, spring, interpolate, AbsoluteFill } from 'remotion';
import { FONT_FAMILIES } from './fonts';

type CaptionPosition = 'top' | 'center' | 'bottom';
type BackgroundStyle = 'none' | 'box' | 'highlight-word';
type AnimationStyle = 'pop' | 'fade' | 'slide';

// A single word's own absolute timing (in seconds, on the whole video's
// timeline) — needed for the "highlight current word" background mode.
type WordTiming = { text: string; start: number; end: number };

// THE STYLE CONFIG OBJECT — every visual caption setting lives in one
// place with one shape. Everything downstream (Gradio -> Python -> JSON
// -> here) passes this whole object around instead of separate values.
export type CaptionStyleConfig = {
  fontFamily: string; // a key into FONT_FAMILIES, e.g. "Montserrat"
  fontSize: number;
  textColor: string; // hex string, e.g. "#ffffff"
  strokeColor: string;
  strokeEnabled: boolean;
  background: BackgroundStyle;
  animation: AnimationStyle;
};

type CaptionProps = {
  text: string;
  start: number; // this chunk's absolute start time in seconds
  words: WordTiming[]; // the individual words inside this chunk, with their own timing
  position: CaptionPosition;
  style: CaptionStyleConfig;
};

const POSITION_STYLES: Record<CaptionPosition, React.CSSProperties> = {
  top: { justifyContent: 'flex-start', paddingTop: 140 },
  center: { justifyContent: 'center' },
  bottom: { justifyContent: 'flex-end', paddingBottom: 140 },
};

export const Caption: React.FC<CaptionProps> = ({ text, start, words, position, style }) => {
  const frame = useCurrentFrame(); // relative to this chunk's own Sequence
  const { fps } = useVideoConfig();

  // ---- 1. Compute the entrance animation as a style object ----
  // Each branch calculates different CSS properties from the same `frame`
  // input — this is the same interpolate()/spring() pattern from before,
  // just picked based on which animation the user chose.
  let animatedStyle: React.CSSProperties = {};

  if (style.animation === 'pop') {
    // Softer, more heavily-damped spring than a snappy motion-graphics
    // pop: low stiffness + higher damping means it eases into place over
    // more frames instead of slamming to scale 1 and bouncing. Scaling
    // from 0.85 (not 0) and fading opacity in over the first few frames
    // avoids the "materializing out of nowhere" jump-cut feel.
    const rawScale = spring({ frame, fps, config: { damping: 18, stiffness: 90, mass: 0.7 } });
    const scale = 0.85 + rawScale * 0.15;
    const opacity = interpolate(frame, [0, 6], [0, 1], { extrapolateRight: 'clamp' });
    animatedStyle = { transform: `scale(${scale})`, opacity };
  } else if (style.animation === 'fade') {
    const opacity = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: 'clamp' });
    animatedStyle = { opacity };
  } else if (style.animation === 'slide') {
    const translateY = interpolate(frame, [0, 8], [30, 0], { extrapolateRight: 'clamp' });
    const opacity = interpolate(frame, [0, 8], [0, 1], { extrapolateRight: 'clamp' });
    animatedStyle = { transform: `translateY(${translateY}px)`, opacity };
  }

  // ---- 2. Build the outline effect (or skip it) ----
  const strokeShadow = style.strokeEnabled
    ? `-3px -3px 0 ${style.strokeColor}, 3px -3px 0 ${style.strokeColor}, -3px 3px 0 ${style.strokeColor}, 3px 3px 0 ${style.strokeColor}, 0px 4px 8px rgba(0,0,0,0.5)`
    : '0px 4px 8px rgba(0,0,0,0.5)';

  const baseTextStyle: React.CSSProperties = {
    color: style.textColor,
    fontSize: style.fontSize,
    fontFamily: FONT_FAMILIES[style.fontFamily],
    fontWeight: 900,
    textShadow: strokeShadow,
  };

  // ---- 3. Figure out which word is "currently spoken" (highlight mode only) ----
  // `start` (the chunk's own absolute start time) + how far we are into
  // this Sequence (frame / fps) = our real position on the whole video's
  // timeline. Compare that against each word's own start/end.
  const currentSeconds = start + frame / fps;

  return (
    <AbsoluteFill style={{ alignItems: 'center', ...POSITION_STYLES[position] }}>
      <div
        style={{
          textAlign: 'center',
          maxWidth: '85%',
          padding: style.background === 'box' ? '12px 24px' : 0,
          backgroundColor: style.background === 'box' ? 'rgba(0,0,0,0.6)' : 'transparent',
          borderRadius: style.background === 'box' ? 12 : 0,
          // The animation (pop/fade/slide) applies to this whole wrapper,
          // so the box (if any) and the text move together as one unit.
          ...animatedStyle,
        }}
      >
        {style.background === 'highlight-word' ? (
          // Render each word as its own span so we can give just the
          // currently-spoken one a pill-shaped highlight behind it.
          words.map((word, i) => {
            const isActive = currentSeconds >= word.start && currentSeconds <= word.end;
            return (
              <span
                key={i}
                style={{
                  ...baseTextStyle,
                  backgroundColor: isActive ? 'rgba(255, 220, 0, 0.85)' : 'transparent',
                  borderRadius: 8,
                  padding: '2px 8px',
                  marginRight: 8,
                  display: 'inline-block',
                }}
              >
                {word.text}
              </span>
            );
          })
        ) : (
          <span style={baseTextStyle}>{text}</span>
        )}
      </div>
    </AbsoluteFill>
  );
};
