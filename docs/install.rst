===============================
Linked Events API install guide
===============================

.. contents::

Introduction
------------

Linked Events API is a `Django <https://www.djangoproject.com/>`_
application, which uses
`Django Rest Framework <http://www.django-rest-framework.org/>`_
to provide Web API for Linked Events data.

System requirements
-------------------

Linked Events runs in unix-like systems and it has been tested in Ubuntu 14.04
and Mac Os X 10.10.

Hardware
________

Developing and testing
::::::::::::::::::::::

For just testing the system

- 2 GB RAM
- 10 GB free disk space
- 1 CPU core

Production environment
::::::::::::::::::::::

Minimum recommended setup for production system:

- 4 GB RAM or more
- 40 GB fast SSD disk space or more
- 2 CPU cores or more

OS related requirements
_______________________

Ubuntu 14.04
::::::::::::

All required libraries and applications are installable with a package manager
(apt-get, aptitude).

Mac Os X 10.10
::::::::::::::

The practical way to install required software is to use
`Homebrew <http://brew.sh/>`_.

Get the code
------------

The source code repository is in Github. You can clone the repository using
command:

.. code-block:: shell

    git clone https://github.com/City-of-Helsinki/linkedevents.git

or if you have set up a github account and you have SSH keys associated with it:

.. code-block:: shell

    git clone git@github.com:City-of-Helsinki/linkedevents.git

Install required software and libraries
---------------------------------------

Linked events API depends on:

- Python 3
- PostgreSQL and PostGIS
- Django (Python 3)
- Elastic search (Java 1.7)

Mac Os X
________

Using Homebrew
::::::::::::::

If you use Homebrew to install required software, issue following commands:

.. code-block:: shell

    brew install readline sqlite gdbm --universal
    brew install python3 --universal --framework
    brew install postgis  # will install postgresql too
    brew install elasticsearch
    brew install libvoikko

You may also try to use pre-compiled binaries. They may work, but are not
tested. See
`Python 3 <https://www.python.org/downloads/mac-osx/>`_ and
`PostgreSQL and PostGIS <http://www.kyngchaos.com/software/postgres>`_.

Java
::::

`Download and install JDK 7 <http://www.oracle.com/technetwork/java/javase/downloads/jdk7-downloads-1880260.html>`_.
Then check

.. code-block:: shell

    java -version  # Should print something like:
    java version "1.7.0_67"

Virtualenv
::::::::::

Now `install and configure Python virtualenv and virtualenvwrapper
<http://virtualenvwrapper.readthedocs.org/en/latest/install.html>`_.

Then create a virtualenv for Linked events:

.. code-block:: shell

    mkvirtualenv -p /usr/local/bin/python3 linkedevents3

Ubuntu 14.04
____________

Using Ansible playbook
::::::::::::::::::::::

There is
`Ansible <http://docs.ansible.com/>`_
playbook, which automates Linked events API server and Elasticsearch
installations into Ubuntu 14.04. It is highly recommended to use it
although it is possible to install both manually.

TODO: link to playbook

Upgrade installed packages
::::::::::::::::::::::::::

First update the package index and install the newest versions of all packages
currently installed:

.. code-block:: shell

    sudo apt-get update && sudo apt-get -y upgrade

Install mandatory packages
::::::::::::::::::::::::::

Then install Python 3, PostgreSQL and other mandatory packages:

.. code-block:: shell

    sudo apt-get install -y python3 python3-dev python3-pip python-virtualenv\
        libxslt1-dev gettext postgresql-9.3-postgis-2.1 libpq-dev python-gdal\
        uwsgi uwsgi-plugin-python3 nginx-full

Install Virtualenv
::::::::::::::::::

Use pip3 to install virtualenvwrapper.

.. code-block:: shell

    sudo pip3 install virtualenvwrapper

Remember to
`set up virtualenvwrapper
<http://virtualenvwrapper.readthedocs.org/en/latest/>`_
after installing it.

Install nginx and supervisor (Optional)
:::::::::::::::::::::::::::::::::::::::

If you are planning to run Linked events in production and use
nginx as a proxy and supervisor to control the process:

.. code-block:: shell

    sudo apt-get install -y nginx supervisor

Set up system
:::::::::::::

.. code-block:: shell

    # Create postgresql user for Linked events
    sudo -u postgres createuser linkedevents

    # Create postgresql database for Linked events
    sudo -u postgres createdb --owner=linkedevents linkedevents
    sudo -u postgres psql -d linkedevents -c "CREATE EXTENSION hstore"
    sudo -u postgres psql -d linkedevents -c "CREATE EXTENSION postgis"

    # Create system user for Linked events
    sudo useradd -m -r linkedevents

    # Switch to linkedevents user
    sudo -s -u linkedevents
    cd /home/linkedevents

    # Get the code
    git clone https://github.com/City-of-Helsinki/linkedevents.git /home/linkedevents/linkedevents

    # make virtualenv
    virtualenv -p /usr/bin/python3 /home/linkedevents/levenv
    source /home/linkedevents/levenv/bin/activate

    # install required python modules
    pip install -r /home/linkedevents/linkedevents/requirements.txt


Search engine: Elasticsearch (Optional)
:::::::::::::::::::::::::::::::::::::::

If you want to use `/search/` end-point in Linked events API
For Elasticsearch follow `the instructions in digitalocean.com
<https://www.digitalocean.com/community/tutorials/how-to-install-elasticsearch-on-an-ubuntu-vps>`_.
Currently the newest Elasticsearch version is `1.4.1
<https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-1.4.1.deb>`_,
but of course it would be a good idea to check newer version from
`Elasticsearch download page <http://www.elasticsearch.org/download>`_.

Simplified summary:

.. code-block:: shell

    # Download and install Java
    ###sudo add-apt-repository ppa:webupd8team/java
    ###sudo apt-get install oracle-java7-installer
    sudo apt-get install openjdk-7-jre

    # Download and install Elasticsearch
    sudo wget https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-1.4.1.deb -O /tmp/elasticsearch-1.4.1.deb
    sudo dpkg -i /tmp/elasticsearch-1.4.1.deb

Edit file `/etc/default/elasticsearch` and add this line:

`ES_JAVA_OPTS=-Djna.library.path=/usr/lib/x86_64-linux-gnu`

.. code-block:: shell

    # To start elasticsearch by default on bootup, please execute
    sudo update-rc.d elasticsearch defaults 95 10

    # In order to start elasticsearch, execute
    sudo /etc/init.d/elasticsearch start

Voikko
::::::

For proper indexing of Finnish words Linked events uses
`libvoikko <http://voikko.puimula.org/>`_.
In Ubuntu it is installable with apt-get:

.. code-block:: shell

    sudo apt-get install -y libvoikko1 libvoikko-dev

Install Voikko's morpho-dictionary (thanks to
`komu's dockerfile <https://registry.hub.docker.com/u/komu/elasticsearch-voikko/dockerfile/>`_

.. code-block:: shell

    sudo wget http://www.puimula.org/htp/testing/voikko-snapshot/dict-morpho.zip -O /tmp/dict-morpho.zip \
    && sudo mkdir -vp /usr/lib/voikko \
    && sudo unzip /tmp/dict-morpho.zip -d /usr/lib/voikko \
    && sudo rm -v /tmp/dict-morpho.zip

Install the Voikko plugin for Elasticsearch.

.. code-block:: shell

    mkvirtualenv -p /usr/local/bin/python3 linkedevents3

TODO: check if this is complete

Ansible
_______

There will be available an Ansible playbook, which installs everything
needed into Ubuntu 14.04.

.. TÄSTÄ SE ALKAA!

    # Puuttuvat depencencyt
    sudo apt-get install unzip openjdk-7-jre

    # Tämä paketti saattaa aiheuttaa konfliktin
    sudo apt-get remove uwsgi-plugin-python

    Muutokset

    - name: Set up PostGRES database for test server
    lc_ctype, lc_collate, template kuntoon

     - name: Downloading language dictionaries
    -           dest=/home/deployment/dict-morpho.zip mode=0644
    +           dest=/tmp/dict-morpho.zip mode=0644


     - name: Voikko | Extract language dictionaries
    -           chdir=/home/deployment
    +           chdir=/tmp




    ansible-playbook -i testing.inventory -u ubuntu -K linkedevents-site.yml


    # As a PostgreSQL super user:
    cd /tmp
    wget  http://api.hel.fi/linkedevents/static/linkedevents.dump.gz
    sudo -u postgres dropdb linkedevents
    sudo -u postgres createdb linkedevents
    zcat linkedevents.dump.gz | sudo -u postgres psql linkedevents


    # start elasticsearch
    sudo /etc/init.d/elasticsearch start

    # Create index
    export DJANGO_SETTINGS_MODULE=linkedevents.settings.prod
    /home/linkedevents/levenv/bin/python manage.py rebuild_index