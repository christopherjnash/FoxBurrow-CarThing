#!/bin/bash

# run the websockify server, which translates the tcp -> websocket for vnc service, to make it accessible from a browser

python3 -m websockify 127.0.0.1:5901 127.0.0.1:5900

