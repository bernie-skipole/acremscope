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

apt-get install indi-bin

adduser bernard

record the password

## Install git, and clone acremscope repository

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

curl -L https://github.com/bernie-skipole/acremscope/releases/download/v0.0.1/dbases.tar.gz --output dbases.tar.gz

extract with

tar -xvf dbases.tar.gz

to create directory /home/bernard/www/astrodata/dbases with three files within it.

dbases/HP48.db

dbases/HP192.db

dbases/HP768.db

These are sqlite database files holding the GSC v1.2 star catalogue with Healpix indexes, and are used to plot the finder charts.

HP48.db has stars to magnitude 6, organised in 48 healpix pixels

HP192.db has stars to magnitude 9, organised in 192 healpix pixels

HP768.db has all stars, organised in 768 healpix pixels

Each database has a table 'stars', with columns

HP INTEGER, GSC_ID TEXT, RA REAL, DEC REAL, MAG REAL

Where HP is the Healpix number, GSC_ID is the index number from the GSC catalog, RA and DEC are in degrees, and MAG is the star magnitude.

The files builddb.py, dbquery.py and cleandb.py in the astrodata directory are unused by the running system but are included for information, they were used in the development of the above three databases.

builddb.py was initially used to create the sqlite databases from a downloaded set of files of the GSC1.2 star catalog. The python file builddb.py is heavily commented and describes how the GSC files are read, the data extracted, and placed into the set of sqlite databases.

dbquery.py is manually edited and used to identify the GSC index of a star in these databases if a spurious point is suspected in the catalog, perhaps due to a satelite or imperfection being recorded.

cleandb.py is used to delete any spurious items - it is manually edited to hold a list of unwanted GSC indexes, and to delete them from each of the sqlite files.

Of the other files under the astrodata directory IERS_A.py will be run by a cron job to regularly update earth location data.

make_planets.py will be run by a cron job to pre - calculate planet positions which will be placed in an sqlite file /home/bernard/www/astrodata/planet.db

Edit make_planets.py, so it refers to the correct file name location.


Load dependencies from pypi

python3 -m pip install --user skipole

python3 -m pip install --user waitress

python3 -m pip install --user redis

python3 -m pip install --user paho-mqtt

python3 -m pip install --user indiredis

python3 -m pip install --user astropy

python3 -m pip install --user astroquery

python3 -m pip install --user jplephem

python3 -m pip install --user astroplan

Note: this gave an astroquery problem, the following sorted it:

python3 -m pip install --user --pre --upgrade astroquery

python3 -m pip install --user astropy-healpix


Run make_planets.py, so in /home/bernard/www/astrodata

python3 make_planets.py

This could take some time, and will create the database planets.db

## Edit the acremscope web service

As user bernard 

Edit the file /home/bernard/www/acremscope_packages/cfg.py to have the correct database ip, usernames passwords.

In particular set the line in the _CONFIG directory:

postgresql_ip : 10.105.192.252

This informs the web service how to connect to these servers.

Edit the file /home/bernard/www/astrodata/metoffice.py to contain the correct met office api keys, so the file can download
weather data.

## Install acremscope.service

as root, copy the file

cp /home/bernard/www/acremscope.service /lib/systemd/system

Enable the service with

systemctl daemon-reload

systemctl enable acremscope.service

systemctl start acremscope

This starts /home/bernard/www/acremscope.py on boot up.

The site will be visible at.

[https://webparametrics.co.uk/acremscope](https://webparametrics.co.uk/acremscope)


## Install indidrivers.service

This runs an indi client, pulling data from MQTT and storing it in redis. I may rename it indiclient in future since its name is misleading.

The python script /home/bernard/www/indidrivers.py is to be started on boot up. First view the file, it sets the ip addresses of redis and mqtt servers, ensure these point to the correct addresses.

It is started with a service.

as root, copy the file

cp /home/bernard/www/indidrivers.service /lib/systemd/system

Enable the service with

systemctl daemon-reload

systemctl enable indidrivers.service

systemctl start indidrivers

This starts /home/bernard/www/indidrivers.py on boot up.

## Set up CRON Jobs

As root create a cron table with:

crontab -u bernard -e

30 10 * * * /usr/bin/python3 /home/bernard/www/astrodata/make_planets.py >/dev/null 2>&1

0 9 * * 6 /usr/bin/python3 /home/bernard/www/astrodata/IERS_A.py >/dev/null 2>&1

15 10 * * * /usr/bin/python3 /home/bernard/www/astrodata/clientrequests.py >/dev/null 2>&1

30 9,16 * * * /usr/bin/python3 /home/bernard/www/astrodata/metoffice.py >/dev/null 2>&1

make_planets.py is run at 10:30 each day, which populates planet.db with planetary positions

IERS_A.py is run at 9:00 every Saturday, It downloads the IERS bulletin A for Astroplan earth location

clientrequests.py is run at 10:15 each day, which requests dome door closure

metoffice.py is run at 9:30 and 16:30 each day, and calls a met office api to obtain weather data which is sets into file weather.json.



