## Overview

In 3PAR WSAPI , there is no way currently to treat array(s) which are part of federation to be treated as a single entity.
Due to this restriction, the top level consumers (like EcoStor) of WSAPI need to trace 3PAR resource (like a volume which is part of federated setup) 
in each and every array which is in federation.

Ask here is to give an unified way of looking at all the arrays which are part of federation.
May be 3PAR WSAPI team, can give us a cluster IP from which all the requests are underneath re-routed to the appropriate array which serves the volume 
(like GET volume API, Create Snapshot etc.)

Additionally, the Get Volume API can return the array name on which the volume currently resides as a new JSON attribute
"hostingArray" as shown below.

Eg.

``` GET on /volumes/v1```
returns

```
{
   .
   .
   .
   .
  "hostingArray" : "system id of array hosting this resource"  
  .
  .
  .
}

```



## Usecase in case of Docker Container

- Array1,2,3,4 are part of a federated setup. Let's call the array in short form notation of A1,A2,A3,A4 
- Let's assume volume V1 is part of A1 (Array 1) is now moved as part of workload re-balancing (or) for disaster recovery to array 2 (A2)
- If the docker volume plugin wants to do further operations with the V1 (like say snapshot of V1), it has to first know 
  1. Which array now hosts the volume V1
  2. How to find the array which is hosting V1 , without doing a individual WSAPI GET volume call to each and every array which is part of federation



### Older approach

![Before Volume Movement](/docs/Slide1.JPG "Before Volume Movement")
![After Volume Movement](/docs/Slide2.JPG "After Volume Movement")
![Volume Tracing](/docs/Slide3.JPG "Volume Tracing")

### Newer Approach

![Clustered endpoint feature](/docs/Slide4.JPG "Clustered WSAPI Endpoint")

