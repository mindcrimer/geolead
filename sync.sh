#!/bin/bash
#
# Скрипт для синхронизации удаленной базы и статики.
# Принимает единственный параметр - имя проекта.
# Если он не указан - используется имя текущего каталога.
#


CONFIG_FILE=~/.projects
LOCAL_HOST="localhost"
LOCAL_DB_PORT=5433
REMOTE_HOST=''
REMOTE_DB_PORT=5433
CORE_COUNT=4

# function for IPv4 validation
is_valid_ipv4() {
  local -a octets=( ${1//\./ } )
  local RETURNVALUE=0

  # return an error if the IP doesn't have exactly 4 octets
  [[ ${#octets[@]} -ne 4 ]] && return 1

  for octet in ${octets[@]}
  do
    if [[ ${octet} =~ ^[0-9]{1,3}$ ]]
    then # shift number by 8 bits, anything larger than 255 will be > 0
      ((RETURNVALUE += octet>>8 ))
    else # octet wasn't numeric, return error
      return 1
    fi
  done
  return ${RETURNVALUE}
}

sudo echo ""

# No arguments supplied - using dirname as project name
if [ $# -eq 0 ]
  then
    PROJECT_NAME=${PWD##*/}
  else
    PROJECT_NAME=$1
fi

# checking config file
if [ -f "$CONFIG_FILE" ]
then
	echo "Reading from $CONFIG_FILE:";
else
	echo "Creating $CONFIG_FILE...";
	touch ${CONFIG_FILE};
fi

echo ""

# trying to read stored values from CONFIG_FILE
while IFS='=' read -r proj_name proj_ip
do
    if [ "$proj_name" = "$PROJECT_NAME" ]
    then
        echo "...using $proj_ip for '$PROJECT_NAME'"
        REMOTE_HOST=${proj_ip}
    fi
done < "$CONFIG_FILE"

if [ -z "$REMOTE_HOST" ]
then
    read -p "...IP for '$PROJECT_NAME' not found. Provide it by yourself: " REMOTE_HOST
    while [ 1 ]; do

    read -p "...invalid IP address. Try again: " REMOTE_HOST
        is_valid_ipv4 ${REMOTE_HOST}
        if [[ $? -gt 0 ]]; then
            continue;
        else
            echo ""${PROJECT_NAME}=${REMOTE_HOST}"" >> ${CONFIG_FILE}
            break
        fi
    done

fi

START_TIME=$(date +%s.%N)

echo "...dumping remote database"
pg_dump -h ${REMOTE_HOST} -p ${REMOTE_DB_PORT} -U postgres -Fc -b ${PROJECT_NAME} > dump.gz

echo "...closing local database connections"
sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND datname = '${PROJECT_NAME}';" >/dev/null 2>&1

echo "...dropping local database"
sudo -u postgres dropdb ${PROJECT_NAME}

echo "...recreating local database role"
sudo -u postgres psql -c "DROP ROLE IF EXISTS ${PROJECT_NAME}; CREATE ROLE ${PROJECT_NAME} LOGIN PASSWORD '${PROJECT_NAME}';" >/dev/null 2>&1

echo "...creating local database"
sudo -u postgres createdb ${PROJECT_NAME} -O ${PROJECT_NAME}

echo "...restoring backup"
pg_restore -h ${LOCAL_HOST} -p ${LOCAL_DB_PORT} -U postgres -d ${PROJECT_NAME} -j ${CORE_COUNT} dump.gz

echo "...removing backup file"
rm -f dump.gz

echo "...media synchronization"
rsync -rqh root@${REMOTE_HOST}:/home/sites/${PROJECT_NAME}/public/media/ public/media/

END_TIME=$(date +%s.%N)
RUN_TIME=$(echo "$END_TIME - $START_TIME" | bc)

echo ""
echo "Done! Execution time is: ${RUN_TIME}"
echo ""
