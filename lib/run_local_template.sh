#!/bin/bash

set -e
umask 0002

echo -e "--- running on `hostname` ---"

GIT_DIR_PATH="{}"
GIT_TAG="{}"
GIT_REMOTE_URL="{}"
OUTPUT_FILE="{}"
CURRENT_JOB_FILE="{}"
QUEUED_FILE="{}"
CONFIG_FILE="{}"
CONFIG_OUT_PATH="{}"

# pre-run commands in form of functions
# (see https://unix.stackexchange.com/questions/444946/how-can-we-run-a-command-stored-in-a-variable ):
{}


# create temporary directory to run from:
TMP_DIR=$(mktemp -d -t ${{GIT_TAG}}-XXXXXXXXXX)
echo "Running from temporary directory: ${{TMP_DIR}}"
trap 'rm -rf "${{TMP_DIR}}"' EXIT
cd ${{TMP_DIR}}


# restore code from git tag:
if [ -n "${{GIT_REMOTE_URL}}" ]; then
  echo "Restoring code with tag ${{GIT_TAG}} from ${{GIT_REMOTE_URL}}"
  git clone -q --depth 1 --branch ${{GIT_TAG}} ${{GIT_REMOTE_URL}} .
else
  echo "Restoring code with tag ${{GIT_TAG}} from file:///${{GIT_DIR_PATH}}"
  git clone -q --depth 1 --branch ${{GIT_TAG}} file:///${{GIT_DIR_PATH}} .
fi


# check that currently no other job is running:
if [ "$(cat ${{CURRENT_JOB_FILE}})" != "" ]; then
    echo "Some other job is running: $(cat ${{CURRENT_JOB_FILE}})"
    echo "Exit."
    exit 1
fi


# register this job in current_job_file:
echo "local:${{HOSTNAME}}" > ${{CURRENT_JOB_FILE}}


# copy current config to last_config path:
cp ${{CONFIG_FILE}} ${{CONFIG_OUT_PATH}}


# run the pre-run commands:
for PRE_FCT in "${{PRE_FCTS[@]}}"
do
  PRE_CMD=$(type $PRE_FCT | sed '1,3d;$d')
  echo
  echo "Now running function ${{PRE_FCT}} from directory ${{PWD}} with commands:"
  echo "${{PRE_CMD}}"
  echo

  $PRE_FCT  # running this in a function because otherwise sequence of command is not handled properly in subshell
done


# run the actual run commands:
set +e
RUN_CMD_CTR=0
should_execute=true
{}


# clean current_job_file and exit:
echo
echo "Cleaning up.."
if [ "${{CURRENT_JOB_FILE}}" != "None" ]; then
    echo "" > ${{CURRENT_JOB_FILE}}
fi

echo "Finished job and exit."
exit 0
