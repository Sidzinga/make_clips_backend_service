# from moviepy import VideoFileClip,CompositeVideoClip,concatenate_videoclips,TextClip,vfx,AudioFileClip,afx,CompositeAudioClip
# import os
#

from moviepy import VideoFileClip
import numpy as np


def detect_black_bars(frame: np.ndarray, threshold: int = 15) -> tuple:
    """Detect black bars using numpy vectorization for better performance."""
    # Convert to grayscale if color image
    if frame.ndim == 3:
        gray = np.mean(frame, axis=2).astype(np.uint8)
    else:
        gray = frame

    # Create mask of non-black pixels using vectorized operations
    non_black_mask = gray > threshold

    # Find boundaries using argmax for vectorized computation
    rows = np.any(non_black_mask, axis=1)
    cols = np.any(non_black_mask, axis=0)

    top = np.argmax(rows)
    bottom = len(rows) - np.argmax(rows[::-1])
    left = np.argmax(cols)
    right = len(cols) - np.argmax(cols[::-1])

    return top, bottom, left, right


def remove_black_bars(
        clip,
        sample_time: float = 2.0,
        margin: int = 1,
        analysis_frames: int = 3):
    """Remove black bars using modern MoviePy v2.0+ features."""
    # Analyze multiple frames for better accuracy
    sample_times = np.linspace(sample_time, clip.duration * 0.5, analysis_frames)
    boundaries = []
    for t in sample_times:
        frame = clip.get_frame(t)
        boundaries.append(detect_black_bars(frame))

        # Use median values to handle varying black bars
    top, bottom, left, right = np.median(boundaries, axis=0).astype(int)

    # Apply safety margin
    top = max(0, top - margin)
    bottom = min(clip.size[1], bottom + margin)
    left = max(0, left - margin)
    right = min(clip.size[0], right + margin)

    # Calculate crop parameters

    width = right - left
    height = bottom - top
    x_center = (left + right) / 2
    y_center = (top + bottom) / 2

    # Apply crop with modern MoviePy syntax
    cropped_clip = clip.cropped(
        x_center=x_center,
        y_center=y_center,
        width=width,
        height=height
    )
    # Write output using modern codec options
    return cropped_clip




# remove_black_bars(vid)