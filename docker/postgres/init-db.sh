#!/bin/bash

# Initialize linkedevents database
# Param 1: db host (if empty, use Unix-domain socket)
# Param 2: db port (if empty, use Unix-domain socket)
# Param 3: db master username
# Param 4: db master password
# Param 5: db migration username
# Param 6: db migration password
# Param 7: db application username
# Param 8: db application password
# Param 9: db name
# Param 10: create application database
# Param 11: create template database
function init-db() {
  local db_host=$1
  local db_port=$2
  local db_master_username=$3
  local db_master_password=$4
  local db_migration_username=$5
  local db_migration_password=$6
  local db_application_username=$7
  local db_application_password=$8
  local db_name=$9
  # Whether to create the app database or not. The postgres Docker image creates a database automatically.
  local create_db=${10:true}
  local create_template_db=${11:true}

  local db_migration_role="${db_migration_username}_role"
  local db_application_role="${db_application_username}_role"
  local db_name_postgis_template="template_postgis"

  local query_runner=("psql" "-v" "ON_ERROR_STOP=1")

  if [[ $db_host != "" && $db_port != "" ]]; then
    query_runner+=("--host=$db_host" "--port=$db_port")
  fi

  local create_db_sql=""
  if [[ $create_db == "true" ]]; then
    create_db_sql=$(cat <<-EOSQL
-- Create a new database for the application. The owner will be the master user.
CREATE DATABASE $db_name WITH OWNER $db_master_username;
EOSQL
  )
  fi

  local create_template_db_sql=""
  if [[ $create_template_db == "true" ]]; then
    # The template database can be useful in local development, e.g., when creating a temporary test database as Django
    # does
    create_template_db_sql=$(cat <<-EOSQL
-- Adapted from https://github.com/City-of-Helsinki/docker-images/blob/44b9e5df569a063eb9f679bc797da0b370a32916/templates/postgis/9.6-2.5/initdb-postgis.sh
-- Create the 'template_postgis' template db
CREATE DATABASE $db_name_postgis_template;
-- Set as a template database
UPDATE pg_database SET datistemplate = TRUE WHERE datname = '$db_name_postgis_template';
EOSQL
  )
  fi

  # Connect to the postgres database as the master user
  PGPASSWORD=$db_master_password "${query_runner[@]}" \
    --username="$db_master_username" \
    --dbname=postgres <<-EOSQL
$create_db_sql

-- Create a new database role for the migration user
CREATE ROLE $db_migration_role;

-- Create a new migration user with the migration role
CREATE ROLE $db_migration_username WITH LOGIN PASSWORD '$db_migration_password' IN ROLE $db_migration_role;

-- Grant all privileges to the migration role and allow the migration user to grant privileges to others
GRANT ALL PRIVILEGES ON DATABASE $db_name TO $db_migration_role WITH GRANT OPTION;

-- Create a new database role for the application user. We use different users for migrations and the application to
-- minimize the privileges required by the application user.
CREATE ROLE $db_application_role;

-- Create a new application user with the application role
CREATE ROLE $db_application_username WITH LOGIN PASSWORD '$db_application_password' IN ROLE $db_application_role;

$create_template_db_sql
EOSQL

  # Connect to the application database as the migration user
  PGPASSWORD=$db_migration_password "${query_runner[@]}" \
    --username="$db_migration_username" \
    --dbname="$db_name" <<-EOSQL
-- The public schema has some security concerns of which it's good to be aware. Therefore, it's recommended to drop it
-- or at least revoke all privileges. For more information, see:
-- https://wiki.postgresql.org/wiki/Database_Schema_Recommendations_for_an_Application
-- https://wiki.postgresql.org/wiki/A_Guide_to_CVE-2018-1058%3A_Protect_Your_Search_Path
-- http://www.artesano.ch/wiki/index.php/PostgreSQL_Security
-- Another option would be too run "DROP SCHEMA public;". However, this might cause some issues with the postgis
-- extensions. See, e.g.:
-- https://postgis.net/2017/11/07/tip-move-postgis-schema/
-- https://dba.stackexchange.com/questions/197201/installing-postgis-in-a-different-schema-causes-topology-extension-to-not-find-g
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- Grant the necessary privileges for the application role
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, TRIGGER, INSERT, UPDATE, DELETE ON TABLES TO $db_application_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO $db_application_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO $db_application_role;
EOSQL

  # Connect to the application database as the master user
  PGPASSWORD=$db_master_password "${query_runner[@]}" \
    --username="$db_master_username" \
    --dbname="$db_name" <<-EOSQL
-- Adapted from https://github.com/City-of-Helsinki/docker-images/blob/44b9e5df569a063eb9f679bc797da0b370a32916/templates/postgis/9.6-2.5/initdb-postgis.sh
-- Load PostGIS into linkedevents database
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS hstore;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
EOSQL

  if [[ $create_template_db == "true" ]]; then
    # Connect to the postgis template database as the master user
    PGPASSWORD=$db_master_password "${query_runner[@]}" \
        --username="$db_master_username" \
        --dbname="$db_name_postgis_template" <<-EOSQL
    -- The public schema has some security concerns of which it's good to be aware. Therefore, it's recommended to drop it
    -- or at least revoke all privileges. For more information, see:
    -- https://wiki.postgresql.org/wiki/Database_Schema_Recommendations_for_an_Application
    -- https://wiki.postgresql.org/wiki/A_Guide_to_CVE-2018-1058%3A_Protect_Your_Search_Path
    -- http://www.artesano.ch/wiki/index.php/PostgreSQL_Security
    -- Another option would be too run "DROP SCHEMA public;". However, this might cause some issues with the postgis
    -- extensions. See, e.g.:
    -- https://postgis.net/2017/11/07/tip-move-postgis-schema/
    -- https://dba.stackexchange.com/questions/197201/installing-postgis-in-a-different-schema-causes-topology-extension-to-not-find-g
    REVOKE ALL ON SCHEMA public FROM PUBLIC;

    -- Adapted from https://github.com/City-of-Helsinki/docker-images/blob/44b9e5df569a063eb9f679bc797da0b370a32916/templates/postgis/9.6-2.5/initdb-postgis.sh
    -- Load PostGIS into postgis_template database
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS hstore;
    CREATE EXTENSION IF NOT EXISTS postgis_topology;
    CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
    CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
EOSQL
  fi
}
