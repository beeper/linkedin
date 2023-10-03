#!/bin/sh

[ -z $CONFIG_PATH ] && CONFIG_PATH="/data/config.yaml"
[ -z $REGISTRATION_PATH ] && REGISTRATION_PATH="/data/registration.yaml"

# Define functions.
function fixperms {
	chown -R $UID:$GID $CONFIG_PATH $REGISTRATION_PATH
}

cd /opt/linkedin-matrix

if [ ! -f $CONFIG_PATH ]; then
	cp example-config.yaml $CONFIG_PATH
	sed -i "s#hostname: localhost#hostname: 0.0.0.0#" $CONFIG_PATH
	echo "Didn't find a config file."
	echo "Copied default config file to $CONFIG_PATH"
	echo "Modify that config file to your liking."
	echo "Start the container again after that to generate the registration file."
	fixperms
	exit
fi

if [ ! -f $REGISTRATION_PATH ]; then
	python3 -m linkedin_matrix -g -c $CONFIG_PATH -r $REGISTRATION_PATH
	fixperms
	exit
fi

fixperms
exec su-exec $UID:$GID python3 -m linkedin_matrix -c $CONFIG_PATH
