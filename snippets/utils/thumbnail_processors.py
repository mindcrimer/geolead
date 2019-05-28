from PIL import Image


def remove_alpha_processor(image, remove_alpha=None, **kwargs):
    if remove_alpha:
        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            alpha = image.convert('RGBA').split()[-1]
            new_image = Image.new('RGBA', image.size, (255,) * 4)
            new_image.paste(image, mask=alpha)
            return new_image.convert('RGB')

    return image
