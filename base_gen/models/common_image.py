# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import io

from PIL import Image

from odoo import models


class CommonImage(models.AbstractModel):
    _name = 'common.image'
    _description = 'Common functions related to image management'

    def merge_img(self, background_img, foreground_png,
                  format_output_img='png'):
        resp = None
        if background_img and foreground_png:
            image_background = Image.open(background_img).convert('RGBA')
            image_foreground = Image.open(foreground_png).convert('RGBA')
            image_background.paste(image_foreground, (0, 0),
                                   image_foreground)
            byte_array = io.BytesIO()
            image_background.save(byte_array, format=format_output_img)
            resp = byte_array
        return resp
