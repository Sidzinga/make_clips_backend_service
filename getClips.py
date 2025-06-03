# from humanfriendly.terminal import output
from moviepy import VideoFileClip, CompositeVideoClip, vfx, afx
#     CompositeAudioClip, clips_array
# import os
# from TranscribeVideo import transcribe_and_highlight
# import re
import cv2
from sympy.printing.pretty.pretty_symbology import center
from TranscribeVideo import transcribe_and_highlight
# from moviepy.video.fx import Crop
from EditVideo import remove_black_bars


# file = "Static/testing.mp4"
# final_path = "testing/output_test7.mp4"
# video_clip = VideoFileClip(file)
# sub = video_clip.subclipped(0,video_clip.duration)
# sub = remove_black_bars(sub)
# sub = transcribe_and_highlight(load_video=sub)


# video_clip.close()
# files = os.listdir('.')
# file = "Static/testing.mp4"
# dr_name = re.search("/.*mp4",file).group()[1:-4]
# video_clip.wi
# if dr_name in files:
#     last_char = dr_name[-1]
#     if last_char.isdigit():
#
#         add = int(last_char) + 1
#         dr_name = dr_name + str(add)
#     dr_name = dr_name + "1"
#
# os.mkdir(dr_name)

# sub.get_fra

# clips = [{'clip':'clip1','start':'00','end':'10','order':0}]
def create_short(input_clip,output_clip=None):
    final_size = (1080, 1920)
    #remove black outline
    def remove_black_outline(clip):
        clip.save_frame("temp_frame1.png", t = clip.duration/2)


    #resize
    def resize_ends(clip,center_clip_size):
        y_size = ((final_size[1] - center_clip_size - (center_clip_size * 0.1)) / 2)
        resized = clip.with_effects([vfx.Resize((clip.size[0],y_size))])
        return resized

    #blur,crop, create split screen clip
    def blur(img):
        return cv2.blur(img,(15,15))

    def blur_clip(clip):
        blurred = clip.image_transform( blur )
        return blurred

    def split_screen(clip):
        clip1 = blur_clip( clip )
        w,h = clip1.size
        cropped1 = clip1.cropped(x_center=w * 0.5,y_center=h * 0.125,width=w,height=h * 0.25)
        cropped2 = clip1.cropped(x_center=w * 0.5,y_center=h * 0.875,width=w,height=h * 0.25)
        return [cropped1,cropped2]



    #combine clips
    def combine_clips(clip):
        center_clip = clip.subclipped(0,clip.duration)
        blurred = blur_clip(clip)
        cropped = split_screen(blurred)
        top = cropped[0]
        bottom = cropped[1]
        y_size = top.size[1] + bottom.size[1] + center_clip.size[1]

        center_clip = center_clip.with_position("center","center").with_duration(clip.duration)
        # center_pos = center_clip.pos(center_clip.duration * 0.5)
        top = resize_ends(top,center_clip.size[1])
        bottom = resize_ends(bottom,center_clip.size[1])
        top = top.with_position("top").with_duration(clip.duration).with_effects([afx.MultiplyVolume(0)])
        bottom = bottom.with_position("bottom").with_duration(clip.duration).with_effects([afx.MultiplyVolume(0)])

        clips = [center_clip,top,bottom]
        final_clip = CompositeVideoClip(clips=clips,size=final_size)


        return final_clip




    # def output_video(video_file,path=output_clip):
    #     video_file.write_videofile(path)

    return combine_clips(input_clip)





# create_short(final_path,sub)