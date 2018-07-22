# coding=utf8
#

import sys, os

"""
======================= ARCHIVES SETTINGS
"""

# This data is not used in backup script, just for convenience. See section 'archives' below.
default = {
    'borg' : {
        'archive-name'    : '"{now:%Y-%m-%d.%H:%M:%S}"', # optional, default '"{now:%Y-%m-%d.%H:%M}"',
        #'compression'     : 'zlib,4',                 # optional, default 'lz4'
        #'encryption-mode' : 'repokey',                # optional, default 'repokey'

        # Backup script already knows and uses some commands and its base args such as
        # 'repository' and etc, but here some extra args can be set. See borg manual for details.
        # It can be added args to any borg command even if it is new borg command.
        'commands-extra'  : {
            #'init'   : '',
            'create' : '--show-rc --stats -v --exclude-caches',
            #'prune'  : '-v --list --keep-daily=2 --keep-weekly=1 --keep-monthly=1',
            'check'  : '-v'
        },

        # Enviroment variables for borg. See borg manual for details.
        'env-vars' : {
            #'BORG_PASSPHRASE'  : '123456'
            'BORG_PASSCOMMAND' : 'cat test_pwd',
            #'BORG_PASSCOMMAND' : 'pass show backup',
        }
    },
    'rclone' : {
    }
}

"""
Config for list of archives

I use this hack with ** symbols to have short way to inherit values from 'default' dictionary,
but it is not necessary. It just works in this case.
See https://stackoverflow.com/questions/38987/how-to-merge-two-dictionaries-in-a-single-expression

It can be used with more than one archive.
"""
archives = (
    {
        'borg' : dict(default['borg'], **{
            'repository'   : '/tmp/borg-test-repo',
            'source'       : (
                'test-src',
            ),
            'exclude'      : (
                'test-src/exclude',
            ),
            'commands-extra' : dict(default['borg']['commands-extra'], **{
                'prune'  : '-v --list --keep-daily=7 --keep-weekly=3 --keep-monthly=3',
                'list'   : '-v'
            }),
        }),
        'rclone' : dict(default['rclone'], **{
        })
    },
    # one more archive and etc
)

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
    'subject' : 'Backups',
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
    'subject': 'Backups',
}

"""
======================= OVERRIDES (optional)
"""

#BORG_BIN = '/usr/bin/borg'

"""
======================= DEFAULT LIST OF ACTIONS IN ORDER OF RUNNING
"""

DEFAULT_ACTIONS = ( \
    'borg:init',
    'borg:create',
    'borg:check',
    'rclone:sync',
)
