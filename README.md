# backup-o-matic

### Brief
This script is for automation and simplifying of my own backups. It's just wrapper for
borg (https://www.borgbackup.org/) with some extra functionality with rclone (https://rclone.org/).

###Main goals of this script:
 - send logs by email
 - simple enough but flexible configs (I selected python file as config file)
 - no extra dependencies, only python (>=2.7 or >=3.5), borgbackup, core
   linux tools and optional rclone for sync to cloud storages
 - upgrade of borgbackup or rclone should not require change of the script,
   but may require change of the configs

###I have NO goals:
 - to make script to use for everyone (for example, you should understand basic syntax of python)
 - to write code with max performance (but it has good performance for me anyway)
 - to handle all sorts of errors and cases (but I try to fix all important cases)
 - to provide working script for not GNU/Linux platform (but it is OK if someone do it)
 - to write ideal code

###Main features:
 - Python config files. It is flexible enough.
 - Supporting use of several config files at once.
 - Sending reports with mail. It can be set up to send directly or with sendmail (ssmtp or similar).
 - Each command can be forced to run with command line.
 - Supporting run of any borg command.
 - Supporting use of the rclone.
 - Supporting use of any shell command.
 - Supporting use of 'run-before' and 'run-after' actions for each command except shell command (because it has no sense).
 - Supporting adding of environment variables

###Using
Example of config file you can see in config_test.py.

Typical run:
```bash
$ ./backup.py config_test.py
```
Run specific borg command:
```
$ ./backup.py config_test.py -a "borg:create"
```
Example of crond file as /etc/cron.d/backup:
```
 45  5  * * *  root /home/backupuser/backup.sh >/dev/null 2>&1
```
Example of backup.sh from previous example:
```
#!/bin/bash
  
# detect current directory
BASEDIR=`realpath "$0"`
BASEDIR=`dirname "$BASEDIR"`
cd "$BASEDIR/backup"

./backup.py config_myhost.py
```
Where `/home/backupuser/backup` is a directory with backup-o-matic script (or symlink to it) and config files.