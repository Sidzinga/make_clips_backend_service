import os
from TranscribeVideo import transcribe_and_highlight
from getClips import  create_short
from SplitVideo import split_clip
from moviepy import VideoFileClip, CompositeVideoClip

download = os.getenv("DOWNLOAD_PATH")

def make_vid(points_to_split,vid,filename):
    new_vid = VideoFileClip(vid)
    new_vid = split_clip(new_vid,points_to_split)
    new_vid = create_short(new_vid)
    new_vid= transcribe_and_highlight(load_video = new_vid)
    filename = f"Short-{filename}.mp4"
    download_path = f"{download}/{filename}"
    new_vid.write_videofile(download_path)
    return download_path

# make_vid(clips,video_file)