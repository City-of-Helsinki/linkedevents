# Linked events

REST JSON API

Installation
------------

Install required Python packages

```
(sudo) pip install -r requirements.txt
```

Create the database

```
sudo -u postgres createuser -L -R -S linkedevents
sudo -u postgres createdb -Olinkedevents linkedevents
sudo -u postgres psql linkedevents -c "CREATE EXTENSION postgis;"
```

Fetch and import the database dump
```
wget -O - http://api.hel.fi/linkedevents/static/linkedevents.dump.gz | gunzip -c > linkedevents.dump
sudo -u postgres psql linkedevents < linkedevents.dump
```
