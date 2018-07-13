Following is an example to create a snapshot schedule for a volume of name volume1:
Below are the options which can be passed while creating a snapshot schedule.

- -o virtualCopyOf=x          This option is mandetory. x is the name of the volume for which snapshot schedule has to be created.
- -o scheduleFrequency=x      This option is mandetory. x is the string that indicates the snapshot schedule frequency.
                            This string will contain 5 values which are seperated by space. Example x can be replaced with "5 * * * *"
                            First field in the string represents the number of minutes that are passed scheduled hour to exucute the 
                            scheduled task. Second field in the string indicated hour at which task needs to be executed. Third field in
                            the string indicates day of the month on which scheduled task has to be executed. Fourth field in the string
                            indicates month in which the task needs to be executed. Fifth field in the string indicates day of a week on
                            which task should be executed. x has to be specified in double quotes. Valid values for these fields are:
                            
                              Field         Allowed Values
                              -----         --------------
                               minute        0-59
                               hour          * or 0-23
                               day-of-month  * or 1-31
                               month         * or 1-12
                               day-of-week   * or 0-6 (0 is Sunday)

- -o scheduleName=x           This option is mandetory. x is a string which indicates name for the schedule on 3PAR.
- -o retentionHours=x         This option is not mandetory option. x is an integer, indicates number of hours this snapshot will be retained.
- -o snaphotPrefix=x          This option is mandetory. x is prefix string for the scheduled snapshots which will get created on 3PAR
- -o expHrs=x                 This option is not mandetory option. x is an integer, indicates number of hours after which snapshot created
                              via snapshot schedule will be deleted from 3PAR.
- -o retHrs=x                 This option is not mandetory option. x is an integer, indicates number of hours this snapshot will be retained.

docker command to create a snapshot schedule:
```
docker volume create -d hpe --name <snapshot_name> -o virtualCopyOf=volume1 
-o scheduleFrequency="10 2 * * *" -o scheduleName=dailyOnceSchedule -o retentionHours=58 
-o snaphotPrefix=pqr -o expHrs=5 -o retHrs=3
```

#### Note:
1. Abvove command creates a docker snapshot with name snapshot_name.
2. It creates a snapshot schedule on 3PAR with name for schedule as dailyOnceSchedule. 
3. scheduleFrequency string specifies that task has to be created daily for each month and on each day at 10 minutes passed 2 O'clock.
4. Docker snapshot has retentionHours of 58
5. Snapshot created via scheduled snapshots will have prefix 'pqr' to its name and these snapshots will have ratiantion period of 3 hours
as well expiration period of 5 hours
