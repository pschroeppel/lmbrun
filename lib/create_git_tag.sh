#!/bin/bash
set -e

GIT_DIR_PATH=$1
GIT_TAG=$2
GIT_MESSAGE=$3
GIT_REMOTE_URL=$4

cd ${GIT_DIR_PATH}

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "${CURRENT_BRANCH}" == "tmp_create_tag" ]]; then
    echo "ERROR: HEAD on tmp_create_tag branch"
    exit 1
fi

# delete existing tag with same name:
git tag | grep -F "${GIT_TAG}" | while read -r FULL_TAG_NAME ; do
    git tag -d ${FULL_TAG_NAME}

    echo "WARNING: Tag with id ${FULL_TAG_NAME} already existed locally and was deleted."
done

if [ -n "${GIT_REMOTE_URL}" ]; then
  git ls-remote --tags ${GIT_REMOTE_URL} | grep -o "${GIT_TAG}i*$"  | while read -r FULL_TAG_NAME ; do
    git push --delete ${GIT_REMOTE_URL} ${FULL_TAG_NAME}
    echo "WARNING: Tag with id ${FULL_TAG_NAME} already existed remotely on ${GIT_REMOTE_URL} and was deleted."
  done
fi

# move current code state to new branch temporarily:
git stash --include-untracked
git checkout -B tmp_create_tag  # -B will reset tmp_create_tag branch and create it if it does not exist
git stash apply || true  # will result in useless error if master had no changes to stash

# create new tag for the current code state:
git add -A
git commit --allow-empty -m "${GIT_TAG} ${GIT_MESSAGE}"
git tag -a ${GIT_TAG} -m "${GIT_TAG} ${GIT_MESSAGE}"

# push new tag to remote if available:
if [ -n "$GIT_REMOTE_URL" ]; then
  git push -f ${GIT_REMOTE_URL} ${GIT_TAG}
fi

# go back to actual branch:
git checkout ${CURRENT_BRANCH}
git stash pop || true  # will result in useless error if master had no changes to stash
git branch -D tmp_create_tag