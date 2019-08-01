HPE 3PAR Priority Optimization software provides quality-of-service rules to manage and control the I/O capacity of an HPE 3PAR 
StoreServ Storage system across multiple workloads.
The use of QoS rules stabilizes performance in a multi-tenant environment.
HPE 3PAR Priority Optimization operates by applying upper-limit control on I/O traffic to and from hosts connected to an HPE 
3PAR StoreServ Storage system. These limits, or QoS rules, are defined for front-end input/output operations per second (IOPS) and
for bandwidth.
QoS rules are applied using autonomic groups. Every QoS rule is associated with one (and only one) target object. 
The smallest target object to which a QoS rule can be applied is a virtual volume set (VVset) or a virtual domain. 
Because a VVset can consist of a single VV, a QoS rule can target a single VV.
Every QoS rule has six attributes:
 
1.	Name: The name of the QoS rule is the same as the name of the VVset.
2.	State: The QoS rule can be active or disabled.
3.	I/O: Sets the Min Goal and the Max Limit on IOPS for the target object.
4.	Bandwidth: Sets the Min Goal and the Max Limit in bytes-per-second transfer rate for the target objective.
5.	Priority: The limit for the target object can be set to low, normal, or high.
6.	Latency Goal: The goals for the target object are determined in milliseconds.
 
 
HPE 3PAR Priority Optimization sets the values for IOPS and bandwidth in QoS rules in absolute numbers, not in percentages.
The IOPS number is stated as an integer between 0 and 231-1, although a more realistic upper limit is the number of IOPS that the
particular array in question is capable of providing, given its configuration. The value for bandwidth is stated as an integer between
0 and 263-1, expressed in KB/second, although a more realistic upper limit is the throughput in KB/second that the particular array in 
question is capable of providing, given its configuration.
 
```
Note: We recommend user/administrator to set QoS rules based on Priority and Latency Goal, so that I/O and Bandwidth can be adjusted 
automatically. If there are multiple volumes in VVSet and QoS rules are applied based on I/O or Bandwidth values, this will not guarantee
that each volume in vvset will have minimum/max I/O or Bandwidth as per set limit (These limits are at vvset level).
```
 
Example: Consider QoS rules for vvset ‘volumeset1’ is set to minimum Bandwidth of X KB/second and max bandwidth of Y KB/second. 
If this vvset has 2 volumes volume1 and volume2, this does guarantee both volumes volume1 and volume2 will have minimum and maximum 
bandwidth of X and Y KB/s respectively.
 
Current implementation of Docker volume plugin only associates the docker created volume with Vvset specified in -o qos-name "vvsetname",
we recommend to be same QoS instead tweaking at docker volume plugin level.
 
Please do refer the 3PAR Store Serv QoS Best practice whitepaper from  https://h20195.www2.hpe.com/v2/GetPDF.aspx/4AA4-4524ENW.pdf
