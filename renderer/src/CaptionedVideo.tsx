// src/CaptionedVideo.tsx
import { AbsoluteFill, OffthreadVideo, Sequence, staticFile, useVideoConfig } from 'remotion';
import { Caption } from './Caption';
import type { CaptionStyleConfig } from './Caption';

type WordTiming = { text: string; start: number; end: number };
type CaptionChunk = { text: string; start: number; end: number; words: WordTiming[] };
type CaptionPosition = 'top' | 'center' | 'bottom';
type Orientation = 'vertical' | 'horizontal';

type CaptionedVideoProps = {
  captions: CaptionChunk[];
  videoFile: string;
  orientation: Orientation;
  captionPosition: CaptionPosition;
  captionStyle: CaptionStyleConfig;
  sourceWidth: number;
  sourceHeight: number;
  fps: number;
};

export const CaptionedVideo: React.FC<CaptionedVideoProps> = ({
  captions,
  videoFile,
  captionPosition,
  captionStyle,
}) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      <OffthreadVideo
        src={staticFile(videoFile)}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      {captions.map((chunk, index) => {
        const startFrame = Math.round(chunk.start * fps);
        const endFrame = Math.round(chunk.end * fps);
        return (
          <Sequence key={index} from={startFrame} durationInFrames={endFrame - startFrame}>
            <Caption
              text={chunk.text}
              start={chunk.start}
              words={chunk.words}
              position={captionPosition}
              style={captionStyle}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
