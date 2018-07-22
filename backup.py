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

BORG_BIN = find_executable('borg')

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

    def isBorgRepo(self, path):
        if not os.path.isdir(path):
            return False
        if not os.path.isfile(os.path.join(path, 'config')):
            return False

        readmeFilePath = os.path.join(path, 'README')
        if not os.path.isfile(readmeFilePath):
            return False

        """
        From docs:
        README - simple text file telling that this is a Borg repository
        """
        import re
        with open(readmeFilePath) as readmeFile:
            for line in readmeFile:
                m = re.search("borg\s+backup\s+repository", line, re.IGNORECASE)
                if m:
                    return True

        return False

    def _prepareConfig(self):
        for archiveConf in self._config.archives:
            if 'borg' not in archiveConf:
                raise KeyError("Field 'borg' not found in config of archive")
            borgConf = archiveConf['borg']
            if 'do-if' not in borgConf:
                borgConf['do-if'] = None
            if 'archive-name' not in borgConf:
                borgConf['archive-name'] = '"{now:%Y-%m-%d.%H:%M}"'
            if 'compression' not in borgConf:
                borgConf['compression'] = 'lz4'
            if 'encryption-mode' not in borgConf:
                borgConf['encryption-mode'] = 'repokey'
            if 'commands-extra' not in borgConf:
                borgConf['commands-extra'] = dict()
            if 'env-vars' not in borgConf:
                borgConf['env-vars'] = dict()

            for name in ('archive-name', 'compression', 'encryption-mode'):
                borgConf[name] = borgConf[name].strip()

            for cmd in borgConf['commands-extra']:
                borgConf['commands-extra'][cmd] = ' ' + borgConf['commands-extra'][cmd]
            borgConf['commands-extra'] = defaultdict(str, borgConf['commands-extra'])

    def _doAction(self, action):

        parts = action.split(':', 2)
        if len(parts) < 2:
            raise Error('Unknown command format, should be format "prefix:command[:\"params\"]"')
        prefix = parts[0]
        command = parts[1]
        params = ''
        if len(parts) == 3:
            params = parts[2]

        methodName = '_do' + prefix[0].upper() + prefix[1:] + command[0].upper() + command[1:]

        if not hasattr(self, methodName):
            if prefix == 'borg':
                methodCall = lambda conf, params: self._doBorgDefault(conf, command, params)
            elif prefix == 'rclone':
                methodCall = lambda conf, params: self._doRcloneDefault(conf, command, params)
            else:
                raise Error('Unknown prefix of command, should be "borg" or "rclone"')
        else:
            methodCall = getattr(self, methodName)

        for archiveConf in self._config.archives:
            doIf = archiveConf['borg']['do-if'] if prefix == 'borg' else archiveConf['rclone']['do-if']
            doCall = False
            if doIf is None:
                doCall = True
            elif callable(doIf):
                doCall = doIf()
                self.logger.info("Param 'do-if' from '%s' section is function and result is '%s'",
                    prefix, doCall)
            elif isinstance(doIf, str):
                doCall = subprocess.call(doIf, shell = True) == 0
                self.logger.info("Param 'do-if' from '%s' section is string to "
                    "run command '%s' and result is '%s'",
                    prefix, doIf, doCall)

            if doCall:
                methodCall(archiveConf, params)

    def _doBorgDefault(self, archiveConf, cmd, params):
        self.logger.debug("Default command handler is using for borg command '%s'", cmd)

        borgConf = archiveConf['borg']
        cmd = cmd + borgConf['commands-extra'][cmd]
        self._runBorgCmd(borgConf, cmd + ' ' + params)

    def _doBorgInit(self, archiveConf, params):
        self.logger.debug("Borg command: init")
        borgConf = archiveConf['borg']

        if self.isBorgRepo(borgConf['repository']):
            self.logger.info("A repository already exists at %s. Command 'borg init' will not be used.",
                borgConf['repository'])
            return

        cmd = 'init --encryption=%s %s' % (borgConf['encryption-mode'], borgConf['repository'])
        cmd = cmd + borgConf['commands-extra']['init']

        self._runBorgCmd(borgConf, cmd + ' ' + params)

    def _doBorgCreate(self, archiveConf, params):
        self.logger.debug("Borg command: create")
        borgConf = archiveConf['borg']

        cmd = 'create --compression %s ::%s' % \
            (borgConf['compression'], borgConf['archive-name'])
        for src in borgConf['source']:
            cmd = cmd + ' ' + src
        for exclude in borgConf['exclude']:
            cmd = cmd + " --exclude '%s'" % exclude
        cmd = cmd + borgConf['commands-extra']['create']

        self._runBorgCmd(borgConf, cmd + ' ' + params)

    def _doRcloneDefault(self, archiveConf, cmd, params):
        self.logger.debug("Default command handler is using for rclone command '%s'", cmd)

    def _runBorgCmd(self, borgConf, cmd):

        borgBin = self._config.BORG_BIN if hasattr(self._config, 'BORG_BIN') else BORG_BIN

        cmd = borgBin + ' ' + cmd
        self.logger.debug("Borg command line: %s", cmd)

        # We must do copy here otherwise we will show all our env variables in current process
        env = os.environ.copy()
        env['BORG_REPO'] = borgConf['repository']
        env.update(borgConf['env-vars'])

        # Redirect stderr to stdout, see:
        # https://github.com/borgbackup/borg/issues/520
        proc = subprocess.Popen(
            cmd, stdout = subprocess.PIPE, stderr = subprocess.STDOUT,
            env = env, universal_newlines = True, shell = True)

        stdout, stderr = proc.communicate()
        if stderr:
            self.logger.error('BORG ERRORS:\n')
            self.logger.error(stderr)
        self.logger.info('BORG OUTPUT:\n' + stdout)
        self._handleProcRetCode(proc.returncode)

    def _handleProcRetCode(self, returncode):
        if returncode != 0:
            raise Exception("Borg process terminated with error code %s" % returncode)

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("configFiles", nargs = '+', metavar = 'configfile', \
        help = "path to config file, file should have python format")
    parser.add_argument('-a', '--actions', nargs = '*', \
        help = "actions in order of running, optional, format: prefix:command[:\"command params\"]")

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
