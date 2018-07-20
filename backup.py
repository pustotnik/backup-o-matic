#!/usr/bin/env python
# coding=utf8
#

import sys, os
if sys.hexversion < 0x2070ef0:
    raise ImportError('Python >= 2.7 is required')

import argparse
import subprocess
import logging, logging.handlers
import smtplib
from collections import defaultdict
from email.mime.text import MIMEText
from distutils.spawn import find_executable

BORG_CMD = find_executable('borg')

#USER_HOMEDIR = os.path.expanduser('~')

LOG_FORMATTER = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt='%Y-%m-%d %H:%M:%S')

def setupDefaultLogger():
    logger = logging.getLogger(__name__)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(LOG_FORMATTER)
    logger.addHandler(ch)
    #logger.setLevel(logging.INFO)
    logger.setLevel(logging.DEBUG)
    return logger

# Default logger
setupDefaultLogger()

class BufferingSMTPHandler(logging.handlers.BufferingHandler):
    def __init__(self, emailConf):
        # capacity here is number of the log records
        super(BufferingSMTPHandler, self).__init__(capacity = 1024)
        self.emailConf = defaultdict(str, emailConf)

        if 'to' not in emailConf:
            raise KeyError("Field 'to' not found in email config")

        if isinstance(self.emailConf['to'], list) or isinstance(self.emailConf['to'], tuple):
            self.emailConf['to'] = ', '.join(self.emailConf['to'])

        self.useSendmail = 'smtp' not in self.emailConf
        if not self.useSendmail:
            smtpConf = self.emailConf['smtp']
            if 'port' not in smtpConf:
                raise KeyError("SMTP port not found in email config")
            if 'host' not in smtpConf:
                raise KeyError("SMTP host not found in email config")
            if 'useSTARTTLS' not in smtpConf:
                self.emailConf['smtp']['useSTARTTLS'] = False
            if 'password' not in smtpConf:
                self.emailConf['smtp']['password'] = ''

    def flush(self):

        log = logging.getLogger(__name__)

        try:
            if not self.buffer:
                return

            body = ""
            for record in self.buffer:
                body = body + self.format(record) + "\r\n"

            msg = MIMEText(body.encode('utf-8'), _charset="utf-8")
            msg['Subject'] = self.emailConf['subject']
            msg['From']    = self.emailConf['from']
            msg['To']      = self.emailConf['to']

            if self.useSendmail:
                sendmail = find_executable('sendmail')
                p = subprocess.Popen([sendmail, "-t", "-oi"],
                        stdin = subprocess.PIPE, universal_newlines = True)
                p.communicate(msg.as_string())

            else:
                smtpConf = self.emailConf['smtp']
                smtp = smtplib.SMTP(smtpConf['host'], smtpConf['port'])
                if smtpConf['useSTARTTLS']:
                    smtp.starttls()
                if smtpConf['password']:
                    smtp.login(self.emailConf['from'], smtpConf['password'])
                smtp.sendmail(self.emailConf['from'],
                            self.emailConf['to'].split(','), msg.as_string())
                smtp.quit()

            log.info('Email was sent')
            self.buffer = []
        except Exception as exc:
            log.error("Error during mail sending:\n%s", exc)

class UnitLogger(object):

    def __init__(self, config):
        # get ready to use default logger
        self.consoleLog = logging.getLogger(__name__)

        # setup mail logger
        self.mailLog = None
        useMail = hasattr(config, 'email')
        if useMail and 'use' in config.email:
            useMail = config.email['use']
        if useMail:
            self.mailLog = logging.getLogger('mail')
            self.mailLog.setLevel(logging.INFO)
            smtpHandler = BufferingSMTPHandler(config.email)
            smtpHandler.setLevel(logging.INFO)
            smtpHandler.setFormatter(LOG_FORMATTER)
            self.mailLog.addHandler(smtpHandler)

    def debug(self, *k, **kw):
        self.consoleLog.debug(*k, **kw)
        if self.mailLog:
            self.mailLog.debug(*k, **kw)

    def info(self, *k, **kw):
        self.consoleLog.info(*k, **kw)
        if self.mailLog:
            self.mailLog.info(*k, **kw)

    def warning(self, *k, **kw):
        self.consoleLog.warning(*k, **kw)
        if self.mailLog:
            self.mailLog.warning(*k, **kw)

    def error(self, *k, **kw):
        self.consoleLog.error(*k, **kw)
        if self.mailLog:
            self.mailLog.error(*k, **kw)

    def critical(self, *k, **kw):
        self.consoleLog.critical(*k, **kw)
        if self.mailLog:
            self.mailLog.critical(*k, **kw)

class Backupper(object):

    def __init__(self, config, actions):
        self._config = config
        self._actions = actions if actions else config.DEFAULT_ACTIONS
        self.logger = UnitLogger(config)
        self._prepareConfig()

    def run(self):
        for act in self._actions:
            self._doAction(act)

    def _prepareConfig(self):
        for archiveConf in self._config.archives:
            if 'borg' not in archiveConf:
                raise KeyError("Field 'borg' not found in config of archive")
            borgConf = archiveConf['borg']
            if 'passphrase' not in borgConf:
                borgConf['passphrase'] = ''
            if 'archive-name' not in borgConf:
                borgConf['archive-name'] = '"{now:%Y-%m-%d.%H:%M}"'
            if 'compression' not in borgConf:
                borgConf['compression'] = 'lz4'
            if 'encryption-mode' not in borgConf:
                borgConf['encryption-mode'] = 'repokey'
            if 'commands-extra' not in borgConf:
                borgConf['commands-extra'] = dict()

            for name in ('archive-name', 'compression', 'encryption-mode'):
                borgConf[name] = borgConf[name].strip()

            borgConf['commands-extra'] = defaultdict(str, borgConf['commands-extra'])

    def _doAction(self, action):

        (prefix, command) = action.split(':')
        if not (prefix and command):
            raise Error('Unknown command format, should be format "prefix:command"')

        methodName = '_do' + prefix[0].upper() + prefix[1:] + command[0].upper() + command[1:]

        if not hasattr(self, methodName):
            if prefix == 'borg':
                methodCall = lambda conf: self._doBorgDefault(conf, command)
            elif prefix == 'rclone':
                methodCall = lambda conf: self._doRcloneDefault(conf, command)
            else:
                raise Error('Unknown prefix of command, should be "borg" or "rclone"')
        else:
            methodCall = getattr(self, methodName)

        for archiveConf in self._config.archives:
            methodCall(archiveConf)

    def _doBorgDefault(self, archiveConf, cmd):
        print("BORG: default")

    def _doBorgInit(self, archiveConf):
        print("BORG: init")
        borgConf = archiveConf['borg']
        print(borgConf)
        cmd = 'init --encryption=%s %s' % (borgConf['encryption-mode'], borgConf['repository'])
        cmd = cmd + borgConf['commands-extra']['init']

        self._runBorgCmd(borgConf, cmd)

    def _doRcloneDefault(self, archiveConf, cmd):
        print("RCLONE: default")

    def _runBorgCmd(self, borgConf, cmd):

        borgCmd = self._config.BORG_CMD if hasattr(self._config, 'BORG_CMD') else BORG_CMD

        cmd = borgCmd + ' ' + cmd
        self.logger.debug("BORG command: %s", cmd)

        # We must do copy here otherwise we will show all our env variables in current process
        env = os.environ.copy()
        if 'passcommand' in borgConf:
            env['BORG_PASSCOMMAND'] = borgConf['passcommand']
        else:
            env['BORG_PASSPHRASE'] = borgConf['passphrase']

        #TODO: cwd ???

        # Redirect stderr to stdout, see:
        # https://github.com/borgbackup/borg/issues/520
        proc = subprocess.Popen(
            cmd.split(), stdout = subprocess.PIPE, stderr = subprocess.STDOUT,
            env = env, universal_newlines = True)

        stdout, stderr = proc.communicate()
        if stderr:
            self.logger.error('BORG ERRORS:\n')
            self.logger.error(stderr)
        self.logger.info('BORG STDOUT:\n' + stdout)
        self._handleProcRetCode(proc.returncode)

    def _handleProcRetCode(self, returncode):
        if returncode != 0:
            raise Exception("Borg process terminated with error code %s" % returncode)

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("configFiles", nargs = '+', metavar = 'configfile', \
        help = "path to config file, file should have python format")
    #parser.add_argument('-a', '--actions', nargs = '*', choices = ['init', 'archive'], \
    #    help = "actions in order of running, optional")
    parser.add_argument('-a', '--actions', nargs = '*', \
        help = "actions in order of running, optional")

    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    # To be sure we have no dups
    seen = set()
    configFiles = [x for x in args.configFiles if x not in seen and not seen.add(x)]

    # load all configs as python files
    configs = map(lambda m: __import__(m[:-3]),
            filter(lambda f: f.endswith(".py"), configFiles))

    log = logging.getLogger(__name__)
    try:
        for cfg in configs:
            backupper = Backupper(cfg, args.actions)
            backupper.run()
    except Exception as exc:
        log.error("Error: %s", exc)
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
