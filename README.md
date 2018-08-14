# backup-o-matic

### Brief
This script is for automation and simplifying of my own backups. It's just a wrapper for
borg (https://www.borgbackup.org/) with some extra functionality with rclone (https://rclone.org/).

###Why?
You can find different already ready to use wrappers for borg on internet. For example here: https://github.com/borgbackup/community. And I checked up almost all of them but did't find suitable for my requirements. So I decided to write my own version of a wrapper :)

###Main goals of this script:
 - send logs by email
 - simple enough but flexible configs (I selected python file as config file)
 - no extra dependencies, only python (>=2.7 or >=3.5), borgbackup, core
   linux tools and optional rclone to sync backups with cloud storages
 - upgrade of borgbackup or rclone should not require any change of the script,
   but may require some change of the configs

###I have NO goals:
 - to make the script user-friendly for everyone (for example, you should understand basic syntax of python)
 - to write the code with max performance (but it has good performance for me anyway)
 - to handle all sorts of errors and cases (but I try to fix all important cases)
 - to provide working script for not GNU/Linux platform (but it is OK if someone does it)
 - to write an ideal code

###Main features:
 - Python config files. It is flexible enough.
 - Supporting the use of several config files at once.
 - Sending reports by mail.  It can be set up to send them directly or with sendmail (ssmtp or similar).
 - Each command can be forced to run with the command line (without mail reports).
 - Supporting the run of any borg command.
 - Supporting the use of the rclone.
 - Supporting the use of any shell command.
 - Supporting the use of 'run-before' and 'run-after' actions for each command except a shell command (because it has no sense).
 - Supporting the adding of environment variables

###Usage
Example of config file you can see in config_test.py.

Typical run:
```
$ ./backup.py config_test.py
```
Run specific borg command only:
```
$ ./backup.py config_test.py -a "borg:create"
```
Example of crond file as /etc/cron.d/backup:
```
 45  5  * * *  root /home/backupuser/backup.sh >/dev/null 2>&1
```
Example of backup.sh from the previous example:
```
#!/bin/bash
  
# detect current directory
BASEDIR=`realpath "$0"`
BASEDIR=`dirname "$BASEDIR"`
cd "$BASEDIR/backup"

./backup.py config_myhost.py
```
Where `/home/backupuser/backup` is a directory with the backup-o-matic script `backup.py` (or symlink to it) and config files.

Example of using rsync command as shell command in my own config for some reason:
```
'borg' : {
    ...
},
'sync-to-myhost' : {
    'command-line' : \
        'ping -c 1 myhost &> /dev/null ;'
        ' REMOTE_HOST_ONLINE=$? ;'
        ' if [[ $REMOTE_HOST_ONLINE -ne 0 ]]; then exit; fi ;'
        ' rsync -av --delete-after -e "ssh -p22" ${BORG_REPO} backupuser@myhost:/path/to/backup/copy '
        ,
},
```