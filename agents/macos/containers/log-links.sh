#!/bin/sh
# Keep /names/<container-name>.log -> that container's json log file
C=/var/lib/docker/containers
while true; do
  new=""
  for d in "$C"/*/; do
    id=$(basename "$d")
    n=$(grep -o '"Name":"/[^"]*"' "$d/config.v2.json" 2>/dev/null | head -1 | sed 's/.*"\///; s/"$//')
    [ -n "$n" ] && [ -e "$d/$id-json.log" ] || continue
    ln -sfn "$d$id-json.log" "/names/$n.log"; new="$new $n.log"
  done
  for l in /names/*.log; do case " $new " in *" $(basename "$l") "*) ;; *) rm -f "$l";; esac; done
  [ "$1" = once ] && exit 0
  sleep 15
done
