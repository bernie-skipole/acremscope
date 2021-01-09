# Container build documentation

This documents creating a container on webparametrics.co.uk, for the full build of the server, see

[https://bernie-skipole.github.io/webparametrics/](https://bernie-skipole.github.io/webparametrics/)

This container will serve the acremscope web site for remote telescope control.

On server webparametrics.co.uk, as user bernard

lxc launch ubuntu:20.04 acremscope

lxc list

This gives container ip address 10.105.192.83

lxc exec acremscope -- /bin/bash

This gives a bash console as root in the acremscope container. Update, install pip and add a user, in this case 'bernard'.

apt-get update

apt-get upgrade

apt-get install python3-pip

apt-get install unzip

apt-get install postgresql-client

psycopg2 is the python client for the postgresql database. Obtain this using apt-get rather than pip, so the binaries are installed without any build problems.

apt-get install python3-psycopg2

apt-get install redis

adduser bernard

record the password

## Install git, and clone skitest repository

Then as user bernard create an ssh key

runuser -l bernard

ssh-keygen -t rsa -b 4096 -C "bernie@skipole.co.uk"

copy contents of .ssh/id_rsa.pub to github

clone any required repositories

git clone git@github.com:bernie-skipole/acremscope.git

copy /home/bernard/acremscope to /home/bernard/www without the .git and .gitignore
(this rsync command can be used to update /www whenever git pull is used to update /acremscope)

rsync -ua --exclude=".*" ~/acremscope/ ~/www/


## Install dependencies


As user bernard in the container

From the 'releases' part of this repository, upload files using:

cd /home/bernard/www/astrodata

curl -L https://github.com/bernie-skipole/acremscope/releases/download/v2.0.0/gsc1.2.tar.gz --output gsc1.2.tar.gz

note - the above is still provisional

extract with

tar -xvf gsc1.2.tar.gz

to create directory /home/bernard/www/astrodata/gsc1.2 with db files within it.

Of the other files under the astrodata directory IERS_A.py will be run by a cron job to regularly update earth location data.

make_planets.py will be run by a cron job to pre - calculate planet positions which will be placed in an sqlite file /home/bernard/www/astrodata/planet.db

Edit make_planets.py, so it refers to the correct file name location.

builddb.py is unused, and can be left where it is. It is included for information only. It was initially used to create the sqlite databases which make up gsc1.2.tar.gz from a downloaded set of files of the GSC1.2 star catalog. The python file builddb.py is heavily commented and describes how the GSC files are read, the data extracted, and placed into a set of sqlite databases.

Load dependencies from pypi

python3 -m pip install --user skipole

python3 -m pip install --user waitress

python3 -m pip install --user redis

python3 -m pip install --user paho-mqtt

python3 -m pip install --user astropy

python3 -m pip install --user astroquery

python3 -m pip install --user jplephem

python3 -m pip install --user astroplan


Run make_planets.py, so in /home/bernard/www/astrodata

python3 make_planets.py

This could take some time, and will create the database planets.db



