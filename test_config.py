# coding=utf8
#

import sys, os

"""
======================= ARCHIVES SETTINGS
"""

# This data is not used in backup script, just for convenience
default = {
    'borg' : {
        #'passphrase'      : '123456',
        'passcommand'     : 'cat test_pwd',
        #'passcommand'     : 'pass show backup',
        #'archive-name'    : '"{now:%Y-%m-%d.%H:%M}"', # optional, default '"{now:%Y-%m-%d.%H:%M}"',
        #'compression'     : 'zlib,4',                 # optional, default 'lz4'
        #'encryption-mode' : 'repokey',                # optional, default 'repokey'

        # Backup script already know and use some commands and its base args such as
        # 'repository' and etc, but here some extra args can be set. See borg manual.
        'commands-extra'  : {
            #'init'   : '',
            'create' : '--show-rc --stats',
            'prune'  : '-v --list {repository} --keep-daily=2 --keep-weekly=1 --keep-monthly=1',
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
                'create' : '--show-rc --stats -v',
                'prune'  : '-v --list --keep-daily=7 --keep-weekly=3 --keep-monthly=3',
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

#BORG_CMD = '/usr/bin/borg'
#LOG_LEVEL = ''

"""
======================= DEFAULT LIST OF ACTIONS IN ORDER OF RUNNING
"""

DEFAULT_ACTIONS = ( \
    'borg:init',
    'borg:create',
    'borg:check',
    'rclone:sync',
)
