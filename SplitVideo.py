from moviepy import VideoFileClip, CompositeVideoClip, vfx, afx,concatenate_videoclips

# split_vid = VideoFileClip("http://localhost:3000/videos/testing.mp4")


def sort_by_order(e):
    return e['order']

def split_clip(clip,points_to_split):
    clips_to_combine = []
    points_to_split.sort(key = sort_by_order)
    for point in points_to_split:
        sub = clip.subclipped(point['start'],point['end'])
        clips_to_combine.append(sub)

    return concatenate_videoclips(clips_to_combine)

