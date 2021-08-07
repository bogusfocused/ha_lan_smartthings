#!/bin/bash
MANIFEST_FILE='ha_config/custom_components/lan_smartthings/manifest.json'
INITIAL_VERSION='v0.0.0'
DEFAULT_BUMP='patch'
SEMVER='./.github/semver'

git fetch --tags

#get highest tag number, and add 1.0.0 if doesn't exist
tag=$(git for-each-ref --sort=-v:refname --format '%(refname:lstrip=2)' | grep -E "^v?[0-9]+\.[0-9]+\.[0-9]+$" | head -n1)
if [ -z "$tag" ]; then
    log=$(git log --pretty='%B')
    tag="$INITIAL_VERSION"
else
    log=$(git log $tag..HEAD --pretty='%B')
    # get current commit hash for tag
    tag_commit=$(git rev-list -n 1 $tag)

    # get current commit hash
    commit=$(git rev-parse HEAD)
    if [ "$tag_commit" == "$commit" ]; then
        echo "No new commits since previous tag. Skipping..."
        exit 0
    fi
fi
echo "Current Version: $tag"

case "$log" in
    *#major* ) new_tag=$($SEMVER bump major $tag) ;;
    *#minor* ) new_tag=$($SEMVER bump minor $tag) ;;
    *#patch* ) new_tag=$($SEMVER bump patch $tag) ;;
    *#none* ) 
        echo "Bump was set to none. Skipping..."; exit 0;;
    * ) 
        if [ "$DEFAULT_BUMP" == "none" ]; then
            echo "Default bump was set to none. Skipping..."; exit 0 
        else 
            new_tag=$($SEMVER bump "${DEFAULT_BUMP}" $tag);
        fi 
        ;;
esac





#create new tag
echo "updating $tag to v$new_tag"

#updated version and commit
sed -i "/\"version\"/c\  \"version\" : \"$new_tag\"," "$MANIFEST_FILE"

git config --local user.name "github-actions"
git config --local user.email "github-actions@github.com"
git commit -m "generated" "$MANIFEST_FILE"
git push

#create tag and push
new_tag="v$new_tag"
git tag -a "$new_tag" -m "version $new_tag"
git push --tags

#create release
cd ha_config
zip -q -r ../release.zip .
cd ..

gh release create -n "release $new_tag" -t "release $new_tag" "$new_tag" smartapp.groovy release.zip 
exit 0
