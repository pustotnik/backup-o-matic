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
