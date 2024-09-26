# 2024 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import logging

from odoo import models


class CommonLog(models.AbstractModel):
    _name = 'common.log'
    _description = 'Common functions related to logging'

    def register_in_log(self, message, source='',  module='', model='', method='',
                        message_type='INFO'):
        if (message and (message_type == 'INFO' or
                         message_type == 'DEBUG' or
                         message_type == 'WARNING' or
                         message_type == 'ERROR' or
                         message_type == 'CRITICAL')):
            if source:
                _logger = logging.getLogger(source)
            else:
                _logger = logging.getLogger(__name__)
            if module or model or method:
                suffix = ''
                if module:
                    suffix = suffix + 'module:' + ' ' + module + ', '
                if model:
                    suffix = suffix + 'model:' + ' ' + model + ', '
                if method:
                    suffix = suffix + 'method:' + ' ' + method + ', '
                suffix = suffix[:-2]
                message = message + ' (' + suffix + ')'
            if message_type == 'INFO':
                _logger.info(message)
            elif message_type == 'DEBUG':
                _logger.debug(message)
            elif message_type == 'WARNING':
                _logger.warning(message)
            elif message_type == 'ERROR':
                _logger.error(message)
            elif message_type == 'CRITICAL':
                _logger.critical(message)
