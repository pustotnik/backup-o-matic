# backup-o-matic

### Brief
This script is for automation and simplifying of my own backups. It's just a wrapper for
borg (https://www.borgbackup.org/) with some extra functionality with rclone (https://rclone.org/).

### Why?
You can find different already ready to use wrappers for borg on internet. For example here: https://github.com/borgbackup/community. And I checked up almost all of them but did't find suitable for my requirements. So I decided to write my own version of a wrapper :)

UPD: There is much more choice now.

### Main goals of this script:
 - Send logs by email
 - Simple enough but flexible configs (I selected python file as config file)
 - There is no extra dependencies, only python (>=2.7 or >=3.5), borgbackup, core
   linux tools and optional rclone to sync backups with cloud storages
 - Upgrade of borgbackup or of rclone should not require any change of the script,
   but may require some changes of the config file(s)

### Main features:
 - Python config files. It is flexible enough.
 - Several config files can be used at the same time.
 - Email reports.  It can be configured to send reports directly or with sendmail (ssmtp or similar).
 - Each command can be forced to run with the command line (without mail reports).
 - Any borg command can be used.
 - Rclone can be used.
 - Any shell command can be used.
 - There are actions 'run-before' and 'run-after' for each command excluding a shell command (because it has no sense).
 - Environment variables.

### Usage
Example of config file you can see in config_test.py.

Typical run:
```
$ ./backup.py config_test.py
```
Run specific borg command only:
```
$ ./backup.py config_test.py -a borg:create
$ ./backup.py config_test.py -a borg:list
$ ./backup.py config_test.py -a borg:mount:"-v --debug -o allow_other"
$ ./backup.py config_test.py -a borg:umount
```
Example of crond file as /etc/cron.d/backup:
```
 45  5  * * *  root /home/backupuser/backup.sh >/dev/null 2>&1
```
Example of backup.sh from the previous example:
```
#!/bin/bash

# detect right directory and go into it
cd "$( dirname "$(realpath ${BASH_SOURCE[0]:-$0})" )/backup"

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

If you want to get mail reports only for errors you can just set EMAIL_LOG_LEVEL in config file to the logging.ERROR.
