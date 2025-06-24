from moviepy import VideoFileClip, TextClip, CompositeVideoClip
import whisper
import os

# font = ''

def transcribe_and_highlight(video_path=None, output_path=None, load_video=None,font = "ComicRelief.ttf"):
    # Load video and extract audio

    def get_video():
        if load_video is not None:
            return load_video
        return VideoFileClip(video_path)


    video = get_video()
    audio = video.audio
    audio.write_audiofile("temp_audio.mp3")

    # Transcribe audio with word-level timestamps
    model = whisper.load_model("base")
    result = model.transcribe("temp_audio.mp3", word_timestamps=True)

    # Create list of overlay clips
    overlays = [video]

    # Process each word individually
    for segment in result['segments']:
        words = segment['words']
        if not words:
            continue

        for word in words:
            highlighted = word['word']
            start = word['start']
            end = word['end']
            duration = end - start

            # Create highlighted text

            # Create and configure text clip
            txt_clip = (
                TextClip(
                    text=highlighted,
                    size=(video.size[0], None),
                    font_size=28,
                    font=f'Fonts/{font}',
                    color='yellow',
                    stroke_color='black',
                    stroke_width=1,
                    method='label'
                )
                .with_duration(duration)
                .with_position('center')
                .with_start(start)
            )
            overlays.append(txt_clip)

    # Create final composition
    final_video = CompositeVideoClip(overlays)
    final_video = final_video.with_duration(video.duration)

    # Write output
    if load_video is not None:

        os.remove("temp_audio.mp3")
        return final_video
    else :
        final_video.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        threads=4,
        preset='fast'
    )
    os.remove("temp_audio.mp3")

# if __name__ == "__main__":
# transcribe_and_highlight("Static/testing.mp4", "output_video5.mp4")