# Container build documentation

This documents creating a container on webparametrics.co.uk, for the full build of the server, see

[https://bernie-skipole.github.io/webparametrics/](https://bernie-skipole.github.io/webparametrics/)

This container will serve the acremscope web site for remote telescope control.

On server webparametrics.co.uk, as user bernard

lxc launch ubuntu:20.04 skitest

lxc list

This gives container ip address 10.105.192.???

lxc exec acremscope -- /bin/bash

This gives a bash console as root in the acremscope container. Update, install pip and add a user, in this case 'bernard'.

apt-get update

apt-get upgrade

apt-get install python3-pip

adduser bernard

record the password
