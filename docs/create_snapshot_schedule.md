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

- -o scheduleName=x           This option is mandatory. x is a string which indicates name for the schedule on 3PAR.
- -o retentionHours=x         This option is not mandatory option. x is an integer, indicates number of hours this snapshot will be retained.
- -o snaphotPrefix=x          This option is mandatory. x is prefix string for the scheduled snapshots which will get created on 3PAR
- -o expHrs=x                 This option is not mandatory option. x is an integer, indicates number of hours after which snapshot created
                              via snapshot schedule will be deleted from 3PAR.
- -o retHrs=x                 This option is not mandatory option. x is an integer, indicates number of hours this snapshot will be retained.

docker command to create a snapshot schedule:
```
docker volume create -d hpe --name <snapshot_name> -o virtualCopyOf=volume1 
-o scheduleFrequency="10 2 * * *" -o scheduleName=dailyOnceSchedule -o retentionHours=58 
-o snapshotPrefix=pqr -o expHrs=5 -o retHrs=3
```

#### Note:
1. Above command creates a docker snapshot with name snapshot_name.
2. It creates a snapshot schedule on 3PAR with name for schedule as dailyOnceSchedule. 
3. scheduleFrequency string specifies that task has to be created daily for each month and on each day at 10 minutes passed 2 O'clock.
4. Docker snapshot has retentionHours of 58
5. Snapshot created via scheduled snapshots will have prefix 'pqr' to its name and these snapshots will have ratiantion period of 3 hours
as well expiration period of 5 hours

###Inspect on volume and snapshot having a schedule associated with it.
Consider volume1 is a volume for which snapshot schedule with name "ThisNewSnapSchedule" is created, for creating this schedule
a docker snapshot with name snapshot1 is created.

```
docker volume inspect volume1
````
Output:
```json
[
    {
        "CreatedAt": "0001-01-01T00:00:00Z",
        "Driver": "hpe:latest",
        "Labels": {},
        "Mountpoint": "/var/lib/docker/plugins/b31d0cf162f23852b2733671de48a81aacf078ec6e529d936ae99f2aec0a57d6/rootfs ",
        "Name": " volume1",
        "Options": {
            "size": "9"
        },
        "Scope": "global",
        "Status": {
            "Snapshots": [
                {
                    "Name": "snapshot1",
                    "ParentName": "volume1",
                    "snap_schedule": {
                      "schedule_name": "ThisNewSnapSchedule",
                      "sched_frequency": "5 2 * * *",
                      "snap_name_prefix": "pqr",
                      "sched_snap_exp_hrs": null,
                      "sched_snap_exp_hrs": null
                    }
                }
            ],
            "volume_detail": {
                "compression": null,
                "flash_cache": null,
                "mountConflictDelay": 30,
                "provisioning": "thin",
                "size": 9
            }
        }
    }
]
```
```
docker volume inspect snapshot1
````
Output:
``` json
[
    {
        "CreatedAt": "0001-01-01T00:00:00Z",
        "Driver": "hpe:latest",
        "Labels": {},
        "Mountpoint": "/var/lib/docker/plugins/b31d0cf162f23852b2733671de48a81aacf078ec6e529d936ae99f2aec0a57d6/rootfs",
        "Name": "snapshot1",
        "Options": {
            "virtualCopyOf": "volume1"
        },
        "Scope": "global",
        "Status": {
            "snap_detail": {
                "compression": null,
                "expiration_hours": null,
                "is_snap": true,
                "mountConflictDelay": 30,
                "parent_id": "36084710-851b-49db-93f2-5d9a71e49423",
                "parent_volume": "volume1",
                "provisioning": "thin",
                "retention_hours": null,
                "has_schedule": true,
                "size": 5,
                "snap_schedule": {
                  "schedule_name": "ThisNewSnapSchedule",
                  "sched_frequency": "5 2 * * *",
                  "snap_name_prefix": "pqr",
                  "sched_snap_exp_hrs": null,
                  "sched_snap_exp_hrs": null
                  }
            }
        }
    }
]
```

#### Note:

If the above snapshot snapshot1 is removed, associated schedule will also be removed from 3PAR. In other words, to remove the schedule 
"ThisNewSnapSchedule" use snapshot name associated with this schedule.

Removing a snapshot and associated schedule:

```
docker volume rm snapshot1
```
