#!/usr/bin/env python
# coding=utf8
#

import sys, os
if sys.hexversion < 0x2070000:
    raise ImportError('Python >= 2.7 is required')

import traceback
import argparse
import subprocess
import logging, logging.handlers
import smtplib
from copy import deepcopy
from collections import defaultdict
from email.mime.text import MIMEText
from distutils.spawn import find_executable

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] >= 3

if PY3:
    string_types = str
else:
    string_types = basestring

# Avoid writing .pyc files
sys.dont_write_bytecode = True

ALLOWED_PREFIXES = ('borg', 'rclone', 'shell')

BORG_BIN   = find_executable('borg')
RCLONE_BIN = find_executable('rclone')

LOG_FORMATTER = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt='%Y-%m-%d %H:%M:%S')
LOG_DEFAULT_LEVEL = logging.INFO

def setupDefaultLogger():
    logger = logging.getLogger(__name__)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(LOG_FORMATTER)
    logger.addHandler(ch)
    logger.setLevel(LOG_DEFAULT_LEVEL)
    return logger

# Default logger
setupDefaultLogger()

def makeDir(path):
    if not path:
        raise IOError("Path can not be empty")
    path = os.path.expandvars(path)
    path = os.path.expanduser(path)
    path = os.path.realpath(path)
    if os.path.isdir(path):
        return
    os.makedirs(path)

class BufferingSMTPHandler(logging.handlers.BufferingHandler):

    def __init__(self, emailConf):
        # capacity here is number of the log records
        super(BufferingSMTPHandler, self).__init__(capacity = 2000)
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

            #msg = MIMEText(body.encode('utf-8'), _charset="utf-8")
            msg = MIMEText(body, _charset="utf-8")
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
        commonLogLevel = config.LOG_LEVEL if hasattr(config, 'LOG_LEVEL') else LOG_DEFAULT_LEVEL
        consoleLogLevel = config.CONSOLE_LOG_LEVEL \
                            if hasattr(config, 'CONSOLE_LOG_LEVEL') else commonLogLevel
        emailLogLevel = config.EMAIL_LOG_LEVEL \
                            if hasattr(config, 'EMAIL_LOG_LEVEL') else commonLogLevel

        # get ready to use default logger
        self.consoleLog = logging.getLogger(__name__)
        self.consoleLog.setLevel(consoleLogLevel)

        # setup mail logger
        self.mailLog = None
        useMail = hasattr(config, 'email')
        if useMail and 'use' in config.email:
            useMail = config.email['use']
        if useMail:
            self.mailLog = logging.getLogger('mail')
            self.mailLog.setLevel(emailLogLevel)
            smtpHandler = BufferingSMTPHandler(config.email)
            smtpHandler.setLevel(emailLogLevel)
            smtpHandler.setFormatter(LOG_FORMATTER)
            self.mailLog.addHandler(smtpHandler)

        self.enableMail = True

    def debug(self, *k, **kw):
        self.consoleLog.debug(*k, **kw)
        if self.enableMail and self.mailLog:
            self.mailLog.debug(*k, **kw)

    def info(self, *k, **kw):
        self.consoleLog.info(*k, **kw)
        if self.enableMail and self.mailLog:
            self.mailLog.info(*k, **kw)

    def warning(self, *k, **kw):
        self.consoleLog.warning(*k, **kw)
        if self.enableMail and self.mailLog:
            self.mailLog.warning(*k, **kw)

    def error(self, *k, **kw):
        self.consoleLog.error(*k, **kw)
        if self.enableMail and self.mailLog:
            self.mailLog.error(*k, **kw)

    def critical(self, *k, **kw):
        self.consoleLog.critical(*k, **kw)
        if self.enableMail and self.mailLog:
            self.mailLog.critical(*k, **kw)

class ToolResultException(Exception):
    pass

class Backupper(object):

    def __init__(self, config, cmdLineActions):
        self._config = config
        self.logger = UnitLogger(config)
        self.logger.enableMail = not cmdLineActions
        self._actions = cmdLineActions or config.DEFAULT_ACTIONS

        self.borgBin = config.BORG_BIN if hasattr(config, 'BORG_BIN') else BORG_BIN
        self.rcloneBin = config.RCLONE_BIN if hasattr(config, 'RCLONE_BIN') else RCLONE_BIN

    def _prepare(self):

        for archiveConf in self._config.archives:

            # fix problem of changing of shallow copies of dicts
            for key in archiveConf:
                archiveConf[key] = deepcopy(archiveConf[key])

            if 'borg' not in archiveConf:
                raise KeyError("Section 'borg' not found in config of archive")
            borgConf = archiveConf['borg']

            if 'repository' not in borgConf or not borgConf['repository']:
                raise KeyError("Field 'repository' not found in 'borg' section or empty")

            if 'rclone' not in archiveConf:
                archiveConf['rclone'] = dict()
            rcloneConf = archiveConf['rclone']
            rcloneConf['use'] = bool(rcloneConf)

            self._setupDefaultConfigValues(archiveConf)

            for name in ('archive-name', 'compression', 'encryption-mode'):
                borgConf[name] = borgConf[name].strip()
            for prefix in ('borg', 'rclone'):
                conf = archiveConf[prefix]
                for cmd in conf['commands-extra']:
                    conf['commands-extra'][cmd] = ' ' + conf['commands-extra'][cmd]
                conf['commands-extra'] = defaultdict(str, conf['commands-extra'])

            repo = borgConf['repository']
            # set 'source' as 'repository' from borg config
            rcloneConf['source'] = repo

            # to simplify work with borg commands
            borgConf['env-vars']['BORG_REPO'] = repo

            if repo.find('@') == -1:
                # only for local path
                makeDir(repo)

    def _setupDefaultConfigValues(self, archiveConf):

        defaultConfValues = {
            'borg': {
                'archive-name'    : '"{now:%Y-%m-%d.%H:%M}"',
                'compression'     : 'lz4',
                'encryption-mode' : 'repokey',
                'exclude'         : tuple(),
                'commands-extra'  : dict(),
                'ignore-commands' : tuple(),
                'env-vars'        : dict(),
                'run-before'      : None,
                'run-after'       : None,
            },
            'rclone' : {
                'with-lock'       : False,
                'destination'     : None,
                'commands-extra'  : dict(),
                'ignore-commands' : tuple(),
                'env-vars'        : dict(),
                'run-before'      : None,
                'run-after'       : None,
            },
        }

        for prefix in ('borg', 'rclone'):
            conf = archiveConf[prefix]
            for name in defaultConfValues[prefix]:
                if name not in conf:
                    conf[name] = defaultConfValues[prefix][name]

    def _doAction(self, action):

        parts = action.split(':', 2)
        if len(parts) < 2:
            raise Exception('Unknown command format, should be format "prefix:command[:\"params\"]"')
        prefix = parts[0]
        command = parts[1]
        params = ''
        if len(parts) == 3:
            params = parts[2]

        if prefix not in ALLOWED_PREFIXES:
            raise Exception('Unknown prefix of command, should be one from list: %s'
                            % ', '.join(allowedPrefixes))

        methodName = '_do' + prefix[0].upper() + prefix[1:] + command[0].upper() + command[1:]

        if not hasattr(self, methodName):
            if prefix == 'borg':
                methodCall = lambda conf, params: self._doBorgDefault(conf, command, params)
            elif prefix == 'rclone':
                methodCall = lambda conf, params: self._doRcloneDefault(conf, command, params)
            elif prefix == 'shell':
                methodCall = lambda conf, params: self._doShell(conf, command, params)
        else:
            methodCall = getattr(self, methodName)

        for archiveConf in self._config.archives:

            repo = archiveConf['borg']['repository']
            doCall = True

            if prefix != 'shell' and command in archiveConf[prefix]['ignore-commands']:
                self.logger.info("%s command '%s' in list of ignored commands for repo '%s'",
                                prefix[0].upper() + prefix[1:], command, repo)
                continue

            if prefix != 'shell':
                runBefore = archiveConf[prefix]['run-before']
                runAfter  = archiveConf[prefix]['run-after']
                if runBefore:
                    doCall = self._doBeforeAfterCall(runBefore, archiveConf[prefix]['env-vars'],
                                "Param 'run-before' from '%s' section for repo '%s'" % (prefix, repo))
            if doCall:
                self.logger.info("Try to run %s command '%s' for repo '%s'",
                                prefix, command, repo)
                methodCall(archiveConf, params)
                self.logger.info("%s command '%s' for repo '%s' has done",
                                prefix[0].upper() + prefix[1:], command, repo)

            if prefix != 'shell' and runAfter:
                self._doBeforeAfterCall(runAfter, archiveConf[prefix]['env-vars'],
                                "Param 'run-after' from '%s' section for repo '%s'" % (prefix, repo))

    def _doBeforeAfterCall(self, callEntity, envVars, paramDesc):
        result = None
        if callable(callEntity):
            result = callEntity()
            self.logger.debug("%s is function and result is '%s'", paramDesc, result)
        elif isinstance(callEntity, string_types):
            env = os.environ.copy()
            env.update(envVars)
            result = self._runCmdInSystem(callEntity, 'shell', env, raiseException = False)
            result = bool(result[0] == 0)
            self.logger.debug("%s is string to run command '%s' and result is '%s'",
                    paramDesc, callEntity, result)
        return result

    def _doBorgDefault(self, archiveConf, cmd, params):
        self.logger.debug("Default command handler is using for borg command '%s'", cmd)

        borgConf = archiveConf['borg']
        cmd = cmd + borgConf['commands-extra'][cmd]
        self._runBorgCmd(archiveConf, cmd + ' ' + params)

    def _doBorgInit(self, archiveConf, params):
        borgConf = archiveConf['borg']

        cmd = 'init --encryption=%s %s' % (borgConf['encryption-mode'], borgConf['repository'])
        cmd = cmd + borgConf['commands-extra']['init']

        (rc, stdout, stderr) = self._runBorgCmd(archiveConf, cmd + ' ' + params, raiseException = False)
        if rc == 0:
            return
        if rc == 2:
            # It's useful to ignore error of already existing repository
            import re
            m = re.search("repository\s+already\s+exists", stdout, re.IGNORECASE)
            if m:
                return

        raise ToolResultException("BORG process terminated with error code %s" % rc)

    def _doBorgCreate(self, archiveConf, params):
        borgConf = archiveConf['borg']

        cmd = 'create --compression %s ::%s' % \
            (borgConf['compression'], borgConf['archive-name'])
        for src in borgConf['source']:
            cmd = cmd + ' ' + src
        for exclude in borgConf['exclude']:
            cmd = cmd + " --exclude '%s'" % exclude
        cmd = cmd + borgConf['commands-extra']['create']

        self._runBorgCmd(archiveConf, cmd + ' ' + params)

    def _doRcloneDefault(self, archiveConf, cmd, params):
        self.logger.debug("Default command handler is using for rclone command '%s'", cmd)

        rcloneConf = archiveConf['rclone']
        borgConf   = archiveConf['borg']

        if not rcloneConf['use']:
            self.logger.info("No section 'rclone' for repository '%s', command '%s' won't be run",
                                borgConf['repository'], cmd)
            return

        requireSource      = ('sync', 'copy', 'move', 'check', 'copyto')
        requireDestination = ('sync', 'copy', 'move', 'delete', 'purge',
                            'mkdir', 'rmdir', 'rmdirs', 'check', 'ls',
                            'lsd', 'lsl', 'size', 'cleanup', 'dedupe', 'copyto')
        cmdLine = cmd

        if cmd in requireSource:
            cmdLine = cmdLine + ' ' + rcloneConf['source']
        if cmd in requireDestination:
            if not rcloneConf['destination']:
                self.logger.error("No 'destination' for repository '%s', command '%s' won't be run",
                                borgConf['repository'], cmd)
                return
            cmdLine = cmdLine + ' ' + rcloneConf['destination']
        cmdLine = cmdLine + rcloneConf['commands-extra'][cmd]

        if rcloneConf['with-lock']:
            env = os.environ.copy()
            env.update(rcloneConf['env-vars'])
            env.update(borgConf['env-vars'])
            cmdLine = '%s with-lock %s %s %s' % (self.borgBin, borgConf['repository'],
                                                self.rcloneBin, cmdLine)
            self._runCmdInSystem(cmdLine + ' ' + params, 'borg', env)
        else:
            self._runRcloneCmd(archiveConf, cmdLine + ' ' + params)

    def _doShell(self, archiveConf, cmdLable, params):
        repo = archiveConf['borg']['repository']
        if cmdLable not in archiveConf:
            self.logger.info("Label '%s' for custom shell command not found for repo '%s', ignored",
                            cmdLable, repo)
            return

        cmdConf = archiveConf[cmdLable]
        self.logger.debug("Command handler for custom shell command labeled as '%s': '%s'",
            cmdLable, cmdConf['command-line'])

        if 'env-vars' not in cmdConf:
            cmdConf['env-vars'] = dict()
        cmdConf['env-vars']['BORG_REPO'] = repo

        # We must do copy here otherwise we will show all our env variables in current process
        env = os.environ.copy()
        env.update(cmdConf['env-vars'])

        return self._runCmdInSystem(cmdConf['command-line'], 'shell', env)

    def _runBorgCmd(self, archiveConf, cmdLine, raiseException = True):
        # We must do copy here otherwise we will show all our env variables in current process
        env = os.environ.copy()
        env.update(archiveConf['borg']['env-vars'])
        return self._runCmdInSystem(self.borgBin + ' ' + cmdLine, 'borg', env, raiseException)

    def _runRcloneCmd(self, archiveConf, cmdLine, raiseException = True):
        # We must do copy here otherwise we will show all our env variables in current process
        env = os.environ.copy()
        env.update(archiveConf['rclone']['env-vars'])
        return self._runCmdInSystem(self.rcloneBin + ' ' + cmdLine, 'rclone', env, raiseException)

    def _runCmdInSystem(self, cmdLine, prefix, env, raiseException = True):

        appLogName = prefix.upper()
        self.logger.debug("%s command line: `%s`", appLogName, cmdLine)

        # Redirect stderr to stdout, see also:
        # https://github.com/borgbackup/borg/issues/520
        proc = subprocess.Popen(
            cmdLine, stdout = subprocess.PIPE, stderr = subprocess.STDOUT,
            env = env, universal_newlines = True, shell = True)

        stdout, stderr = proc.communicate()
        if stderr:
            self.logger.error(appLogName + ' ERRORS:\n' + stderr)
        if stdout:
            self.logger.info(appLogName + ' OUTPUT:\n' + stdout)
        if proc.returncode != 0 and raiseException:
            raise ToolResultException("%s process terminated with error code %s" \
                                    % (appLogName, proc.returncode))
        return (proc.returncode, stdout, stderr)

    def run(self):
        try:
            self._prepare()
            for act in self._actions:
                self._doAction(act)
        except ToolResultException as exc:
            self.logger.error("Error: %s", exc)
            return False
        except Exception as exc:
            self.logger.error("Error: %s\n%s", exc, traceback.format_exc())
            return False

        return True

def main():

    parser = argparse.ArgumentParser(
        formatter_class = argparse.RawTextHelpFormatter)
    parser.add_argument('-a', '--action', nargs = '?', default='', \
        help = "action, optional, format:\nprefix:command[:\"command params\"]"
                "\nprefix is one of: %s" % str(ALLOWED_PREFIXES)[1:-1])
    parser.add_argument("configFiles", nargs = '+', metavar = 'configfile', \
        help = "path to config file, file should have python format")

    if len(sys.argv) == 1:
        parser.print_help()
        return 0

    args = parser.parse_args()

    # To be sure we have no dups
    seen = set()
    configFiles = [x for x in args.configFiles if x not in seen and not seen.add(x)]

    sys.path.insert(0, os.getcwd())

    # load all configs as python files
    configs = map(lambda m: __import__(m[:-3]),
            filter(lambda f: f.endswith(".py"), configFiles))

    for cfg in configs:
        backupper = Backupper(cfg, args.action.split())
        if not backupper.run():
            return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
