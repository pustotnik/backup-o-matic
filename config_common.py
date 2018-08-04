# coding=utf8
#

import platform


"""
======================= EMAIL SETTINGS
smtp parameter 'to' can be list or tuple
"""


""" Example how to use with gmail
email = {
    'use'     : True, # optional, can be used to disable email
    'from'    : 'you@gmail.com',
    'to'      : 'you@gmail.com',
    #'to'      : ('you@gmail.com', 'friend@gmail.com'),
    'subject': 'Backups (%s)' % platform.node(),
    'smtp': {
        'useSTARTTLS': True,
        'host'       : 'smtp.gmail.com',
        'port'       : 587,
        'password'   : 'yourpassword' # for SMTP with authentication
    },
}
"""

# This version without 'smtp' section does try to use sendmail tool.
# It's useful with ssmtp tool for example
email = {
    'use'    : False, # optional, can be used to disable email
    'from'   : 'root',
    'to'     : 'root',
    'subject': 'My backups (%s)' % platform.node(),
}
