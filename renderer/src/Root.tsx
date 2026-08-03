// src/Root.tsx
import { Composition } from 'remotion';
import { CaptionedVideo } from './CaptionedVideo';
import type { CaptionStyleConfig } from './Caption';

type WordTiming = { text: string; start: number; end: number };
type CaptionChunk = { text: string; start: number; end: number; words: WordTiming[] };
type Orientation = 'vertical' | 'horizontal';
type CaptionPosition = 'top' | 'center' | 'bottom';

const FALLBACK_FPS = 30;

// Crops to the target orientation's aspect ratio using the largest region that fits
// inside the source frame, instead of forcing a fixed 1080x1920/1920x1080 — so a
// high-resolution source keeps its resolution instead of being downscaled to match
// a preset, and a source that's already the requested orientation isn't touched at all.
function computeOutputDimensions(orientation: Orientation, sourceWidth: number, sourceHeight: number) {
  const targetAspect = orientation === 'vertical' ? 9 / 16 : 16 / 9;
  const sourceAspect = sourceWidth / sourceHeight;

  let width: number;
  let height: number;
  if (sourceAspect > targetAspect) {
    height = sourceHeight;
    width = Math.round(height * targetAspect);
  } else {
    width = sourceWidth;
    height = Math.round(width / targetAspect);
  }

  // h264 requires even dimensions.
  width -= width % 2;
  height -= height % 2;
  return { width, height };
}

// Fallback style used only for Studio's initial preview before real
// props are supplied — the real values come from Python/Gradio at render time.
const defaultCaptionStyle: CaptionStyleConfig = {
  fontFamily: 'Montserrat',
  fontSize: 76,
  textColor: '#ffffff',
  strokeColor: '#000000',
  strokeEnabled: true,
  background: 'none',
  animation: 'pop',
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="CaptionedVideo"
      component={CaptionedVideo}
      fps={FALLBACK_FPS}
      width={1920}
      height={1080}
      durationInFrames={150}
      defaultProps={{
        captions: [] as CaptionChunk[],
        videoFile: 'placeholder.mp4',
        orientation: 'horizontal' as Orientation,
        captionPosition: 'bottom' as CaptionPosition,
        captionStyle: defaultCaptionStyle,
        sourceWidth: 1920,
        sourceHeight: 1080,
        fps: FALLBACK_FPS,
      }}
      calculateMetadata={async ({ props }) => {
        const lastCaption = props.captions[props.captions.length - 1];
        const durationInSeconds = lastCaption ? lastCaption.end + 1 : 5;
        const fps = props.fps || FALLBACK_FPS;
        const { width, height } = computeOutputDimensions(props.orientation, props.sourceWidth, props.sourceHeight);
        return {
          durationInFrames: Math.round(durationInSeconds * fps),
          width,
          height,
          fps,
        };
      }}
    />
  );
};
