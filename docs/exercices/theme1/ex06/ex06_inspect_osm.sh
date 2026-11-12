#!/bin/bash

if [ -z "$1" ] || [ ! -f "$1" ]; then
	echo "Fichier absent ou inexistant."
	exit 1
fi

if ! command -v osmium &> /dev/null; then
	echo "Erreur: 'osmium' n'est pas installé"
	exit 1
fi

osmium fileinfo -e $1
