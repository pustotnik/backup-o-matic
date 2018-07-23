# coding=utf8
#

#import sys, os

"""
======================= ARCHIVES SETTINGS
"""

# This data is not used in backup script, just for convenience. See section 'archives' below.
default = {
    # Values in this section refer to borg values. See borg docs for details.
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

def doIf():
    # Just example
    return True

"""
Config for list of archives

I use this hack with ** symbols to have short way to inherit values from 'default' dictionary,
but it is not necessary. It just works in this case.
See https://stackoverflow.com/questions/38987/how-to-merge-two-dictionaries-in-a-single-expression

It can be used with more than one archive.
"""
archives = (
    {
        # Values in this section refer to borg values. See borg docs for details.
        'borg' : dict(default['borg'], **{
            # 'do-if' can be used as condition to run any command with current archive
            # It can be function or any command for shell. It is None by default
            #'do-if'        : doIf,
            'do-if'        : 'ping -c 1 localhost &> /dev/null',
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
            # See description for the same param in borg section above
            'do-if'        : doIf,
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

# Usually it is not necessery, backup script tries to find path by itself
#BORG_BIN = '/usr/bin/borg'

# Custom level of logging. This level will be applied to console and email logging.
# It is logging.INFO by default
import logging
LOG_LEVEL = logging.DEBUG
#LOG_LEVEL = logging.ERROR
#LOG_LEVEL = logging.CRITICAL

"""
======================= DEFAULT LIST OF ACTIONS IN ORDER OF RUNNING
"""

DEFAULT_ACTIONS = ( \
    'borg:init',
    'borg:create',
    'borg:check',
    'rclone:sync',
)
