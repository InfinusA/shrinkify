#!/usr/bin/env python3
import re
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from io import BytesIO

from ..config import ShrinkifyConfig
def match_yt_id(filename):
    yt_match = re.search('\-([a-zA-Z0-9\-_]{11})\.', str(filename))
    if not yt_match:
        yt_match = re.search('\[([a-zA-Z0-9\-_]{11})\].', str(filename))
    if not yt_match:
        return yt_match
    else:
        yt_id = yt_match.group(1)
        return yt_id

def custom_thumbnail_generator(title, font=None, font_size=100, base_image=None):
    base_image = str(base_image)
    try:
        font = ImageFont.load_default() if font is None else ImageFont.truetype(font, font_size)
    except OSError:
        font = ImageFont.load_default()
    try:
        final_thumbnail = Image.new('RGBA', (1000, 1000), color='#525252') if base_image is None else Image.open(base_image)
    except FileNotFoundError:
        final_thumbnail = Image.new('RGBA', (1000, 1000), color='#525252')
    ftd = ImageDraw.Draw(final_thumbnail)
    title_text = title[:14]
    if len(title) > 14:
        title_text += '...'
    text_w, text_h = ftd.textsize(title_text, font=font)
    real_coord = (
        60  + ((880-text_w)//2),
        800 + ((150-text_h)//2)
    )
    ftd.text(real_coord, title_text, fill=(207, 207, 207), font=font)
    return final_thumbnail

def center_crop(img):
    #crop off borders
    img = smart_crop(img)
    if img.size[0] > img.size[1]: #wide
        diff = (img.size[0] - img.size[1]) // 2
        left_x = diff
        right_x = img.size[1] + diff
        return img.crop((left_x, 0, right_x, img.size[1]))
    elif img.size[1] > img.size[0]: #tall (uncommon?)
        diff = (img.size[1] - img.size[0]) // 2
        top_x = diff
        bottom_x = img.size[1] + diff
        return img.crop((0, top_x, img.size[0], bottom_x))
    else: #same
        return img

def smart_crop(img, threshold=5):
    #if the image is perfectly square, assume it is already pre-scaled
    if img.size[0] == img.size[1]:
        return img
    img_array = np.array(img)
    #strange case, if the whole array is the same color
    #in this case, just leave it alone as we probably don't want the whole thing cropped
    if np.all(img_array[:,:] == img_array[0,0]):
        return img
    
    # y_nonzero, x_nonzero, _ = np.nonzero(img_array>5)
    # img_array = img_array[np.min(y_nonzero):np.max(y_nonzero), np.min(x_nonzero):np.max(x_nonzero)]
    
    #if the image can be cropped to a square and the only color cropped is a single color, (eg logos in 16:9), don't crop all the color
    #TODO: detect large borders (see "4v0kjleYTKY")
    tall = img_array.shape[1] < img_array.shape[0]
    if tall: # lazy fix (just rotate)
        img_array = np.rot90(img_array)
    mask = np.ones(img_array.shape, dtype=bool)
    mask[:,img_array.shape[1]//2-img_array.shape[0]//2:img_array.shape[1]//2+img_array.shape[0]//2] = False
    dev = np.nanstd(img_array, axis=1, where=mask)
    dev = np.nan_to_num(dev)
    ok = np.all(dev.max() < 0.2)
    if ok:
        new_img = Image.fromarray(img_array[:,img_array.shape[1]//2-img_array.shape[0]//2:img_array.shape[1]//2+img_array.shape[0]//2])
        if tall:
            new_img = np.rot90(new_img, 3)
        return new_img

    for _ in range(2):
        #rotate 90 degrees and do the horizontal ones first, then rotate back and do vertical
        img_array = np.rot90(img_array)
        corner_array = np.asarray([[img_array[0,0]]])
        deleteflags = [False for _ in range(img_array.shape[0])]
        for colindex, col in enumerate(img_array):
            if np.all(np.sum(np.abs(col-corner_array), axis=-1)<15):
                # print(f"Column {colindex} will be deleted")
                deleteflags[colindex] = True
            # else:
                # print(colindex)
                # print(np.abs(col-corner_array))
        for flagindex, flag in enumerate(deleteflags):
            # print((False in deleteflags[:flagindex]) or (False in deleteflags[flagindex+1:]))
            # print(False in deleteflags[:flagindex], False in deleteflags[flagindex+1:])
            if flag:
                if not (sum([0 if f else 1 for f in deleteflags[:flagindex]]) == 0 or sum([0 if f else 1 for f in deleteflags[flagindex+1:]]) == 0):
                    # print(flagindex, 'is not valid')
                    deleteflags[flagindex] = False
        #actually delete the lines
        realindex = 0
        for deleteflag in deleteflags:
            if not deleteflag:
                realindex += 1
            else:
                img_array = np.delete(img_array, realindex, axis=0)
    
    #image is actually upside-down so invert it once more
    img_array = np.flip(img_array, [0, 1])

    cropped_img = Image.fromarray(img_array)
    # cropped_img.save('crop.tmp.png')
    return cropped_img

def data_to_thumbnail(raw_data, *args, **kwargs):
    '''wrapper for thumbnail_generator that converts raw bytes into a Pillow image'''
    filewrapper = BytesIO(raw_data)
    real_image = Image.open(filewrapper, formats=None)
    match ShrinkifyConfig.MetadataRuntime.ThumbnailGenerator.generator_mode:
        case 0:
            return thumbnail_generator(real_image, *args, **kwargs)
        case 1:
            return center_crop(real_image, *args, **kwargs)

def thumbnail_generator(thumbnail: Image, blur_radius=35):
    #if the thumbnail is square, just return it back
    if thumbnail.size[0] == thumbnail.size[1]:
        return thumbnail
    final_thumbnail = Image.new('RGBA', (1000, 1000))
    #crop thumbnail
    thumbnail = smart_crop(thumbnail)
    #format the thumbnail nicely into fit and fill versions
    if thumbnail.size[0] < thumbnail.size[1]: #landscape
        height_scale = 1000/thumbnail.size[1]
        fg_image = thumbnail.resize((1000, int(round(height_scale*thumbnail.size[0]))))
        width_scale = 1000/thumbnail.size[0]
        bg_image = thumbnail.resize((int(round(width_scale*thumbnail.size[1])), 1000))
    else: #portrait
        height_scale = 1000/thumbnail.size[0]
        fg_image = thumbnail.resize((1000, int(round(height_scale*thumbnail.size[1]))))
        width_scale = 1000/thumbnail.size[1]
        bg_image = thumbnail.resize((int(round(width_scale*thumbnail.size[0])), 1000))
    bg_blur = bg_image.filter(ImageFilter.GaussianBlur(blur_radius))

    bg_paste_coord = (
        (final_thumbnail.size[0]-bg_image.size[0])//2,
        0,
        (final_thumbnail.size[0]-bg_image.size[0])//2+bg_image.size[0],
        1000,)
    fg_paste_coord = (
        (final_thumbnail.size[0]-fg_image.size[0])//2,
        (final_thumbnail.size[1]-fg_image.size[1])//2,
        (final_thumbnail.size[0]-fg_image.size[0])//2+fg_image.size[0],
        (final_thumbnail.size[1]-fg_image.size[1])//2+fg_image.size[1],)
        
    final_thumbnail.paste(bg_blur, bg_paste_coord)
    final_thumbnail.paste(fg_image, fg_paste_coord)
    return final_thumbnail

