# Replication: HPE 3PAR Docker Storage Plugin #

This feature allows Docker users to create replicated volume(s) using
HPE 3PAR Storage Plugin. Docker CLI does not directly support 
replication. HPE 3PAR Storage Plugin extends Docker's "volume create"
command interface via optional parameter in order to make it possible.

HPE 3PAR Storage Plugin assumes that an already working 3PAR Remote 
Copy setup is present. The plugin has to be configured with the 
details of this setup in a configuration file called hpe.conf.

On the 3PAR front, core to the idea of replication is the concept of 
remote copy group (RCG) that aggregates all the volumes that need to 
be replicated simultaneously to a remote site.

HPE 3PAR Storage Plugin extends Docker's "volume create" command via 
optional parameter 'replicationGroup'. This represents the name of the
RCG on 3PAR which may or may not exist. In the former case, it gets
created and the new volume is added to it. In the latter case, the 
newly created volume is added to the existing RCG.

'replicationGroup' flag is effective only if the backend in
the configuration file hpe.conf has been configured as a 
replication-enabled backend. Multiple backends with different 
permutations and combinations can be configured.

**Note:**

1. User can create non-replicated/standard volume(s) using
replication-enabled backend. In order to do so, 'replicationGroup' must
not be specified in the create volume command.
2. For a backend that is NOT replication-enabled, specifying 'replicationGroup'
is incorrect and results in error.
3. For a given RCG, mixed transport protocol is not supported. E.g. volumes v1, v2 and v3
 are part of RCG called TestRCG, then on primary array, if these volumes are exported via
 FC protocol then on secondary array those CANNOT be exported via ISCSI (after failover)
 and vice versa.
4. Cold remote site (e.g. ISCSI IPs on remote array not configured) is not supported.
For ISCSI based transport protocol, the ISCSI IPs on both primary and secondary arrays
MUST be defined upfront in hpe.conf.

HPE 3PAR Docker Storage Plugin supports two types of replication the details of 
which can be found at:
1. [Active/Passive Based Replication](active-passive-based-replication.md) and 
2. [Peer Persistence Based Replication](peer-persistence-based-replication.md).


[<< Back to Usage](usage.md#replication)
