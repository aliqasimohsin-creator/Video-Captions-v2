// src/CaptionedVideo.tsx
import { AbsoluteFill, OffthreadVideo, Sequence, staticFile } from 'remotion';
import { Caption } from './Caption';
import type { CaptionStyleConfig } from './Caption';

type WordTiming = { text: string; start: number; end: number };
type CaptionChunk = { text: string; start: number; end: number; words: WordTiming[] };
type CaptionPosition = 'top' | 'center' | 'bottom';

type CaptionedVideoProps = {
  captions: CaptionChunk[];
  videoFile: string;
  captionPosition: CaptionPosition;
  captionStyle: CaptionStyleConfig;
};

const FPS = 30;

export const CaptionedVideo: React.FC<CaptionedVideoProps> = ({
  captions,
  videoFile,
  captionPosition,
  captionStyle,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: 'black' }}>
      <OffthreadVideo
        src={staticFile(videoFile)}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      {captions.map((chunk, index) => {
        const startFrame = Math.round(chunk.start * FPS);
        const endFrame = Math.round(chunk.end * FPS);
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
