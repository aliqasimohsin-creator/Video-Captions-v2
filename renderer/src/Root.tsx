// src/Root.tsx
import { Composition } from 'remotion';
import { CaptionedVideo } from './CaptionedVideo';
import type { CaptionStyleConfig } from './Caption';

type WordTiming = { text: string; start: number; end: number };
type CaptionChunk = { text: string; start: number; end: number; words: WordTiming[] };
type Orientation = 'vertical' | 'horizontal';
type CaptionPosition = 'top' | 'center' | 'bottom';

const FPS = 30;

const DIMENSIONS: Record<Orientation, { width: number; height: number }> = {
  vertical: { width: 1080, height: 1920 },
  horizontal: { width: 1920, height: 1080 },
};

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
      fps={FPS}
      width={1920}
      height={1080}
      durationInFrames={150}
      defaultProps={{
        captions: [] as CaptionChunk[],
        videoFile: 'placeholder.mp4',
        orientation: 'horizontal' as Orientation,
        captionPosition: 'bottom' as CaptionPosition,
        captionStyle: defaultCaptionStyle,
      }}
      calculateMetadata={async ({ props }) => {
        const lastCaption = props.captions[props.captions.length - 1];
        const durationInSeconds = lastCaption ? lastCaption.end + 1 : 5;
        const { width, height } = DIMENSIONS[props.orientation];
        return {
          durationInFrames: Math.round(durationInSeconds * FPS),
          width,
          height,
        };
      }}
    />
  );
};
