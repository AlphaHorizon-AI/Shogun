# Team Mode telemetry authority

Installation telemetry represents one Shogun deployment, not its members. It
collects neither member identity nor member count.

All status and write endpoints use the infrastructure administration guard. On a
desktop loopback connection this represents the local Primary Admin. On a server
deployment the caller must supply the dedicated infrastructure token. Do not
distribute that token to ordinary members.
